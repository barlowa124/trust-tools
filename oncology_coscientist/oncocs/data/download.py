"""Download cohort archive and record a SHA-256 manifest."""
from __future__ import annotations

import hashlib
import json
import tarfile
import time
from pathlib import Path

import requests

from oncocs.config import DEFAULT_ROOT, CohortConfig

ARCHIVE_TIMEOUT_S = 120   # cohort archive GET
FILE_TIMEOUT_S = 600      # per-file downloads (large expression matrices)
API_TIMEOUT_S = 300       # cBioPortal mutation fetch
MAX_FETCH_ATTEMPTS = 5
RETRY_DELAY_S = 10


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_lfs_pointer(data: bytes) -> bool:
    return data[:60].startswith(b"version https://git-lfs.github.com/spec/v1")


def download_cohort(cfg: CohortConfig, root: Path | str = DEFAULT_ROOT) -> dict:
    """Fetch the cohort archive, extract it under data/<cohort>/raw/, write manifest.json."""
    root = Path(root)
    raw_dir = root / "data" / cfg.cohort / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    used_names = [v for v in cfg.files.values()]
    member_sha = {}
    archive_sha = None
    source = "archive"
    archive_path = raw_dir / Path(cfg.archive_url).name if cfg.archive_url else None

    fetched = archive_path is not None and archive_path.exists()
    if not fetched and cfg.archive_url:
        print(f"Downloading {cfg.archive_url} ...")
        try:
            resp = requests.get(cfg.archive_url, stream=True, timeout=ARCHIVE_TIMEOUT_S)
            resp.raise_for_status()
            with open(archive_path, "wb") as fh:
                for chunk in resp.iter_content(1 << 20):
                    fh.write(chunk)
            fetched = True
        except requests.RequestException as exc:
            print(f"Archive download failed ({exc}); falling back to per-file download.")

    if fetched:
        with tarfile.open(archive_path, "r:gz") as tar:
            names = {}
            for member in tar.getmembers():
                base = Path(member.name).name
                match = next((v for v in used_names
                              if member.name.endswith("/" + v) or base == v), None)
                if match:
                    fh = tar.extractfile(member)
                    data = fh.read()
                    dest = raw_dir / match
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    member_sha[match] = _sha256_bytes(data)
                    names[match] = member.name
            missing = [n for n in used_names if n not in names]
            if missing:
                raise FileNotFoundError(
                    f"Expected members not found in archive: {missing}. "
                    f"Archive contains e.g. {[m.name for m in tar.getmembers()][:20]}"
                )
        archive_sha = _sha256_file(archive_path)
    else:
        if not cfg.file_base_url:
            raise FileNotFoundError(
                "Archive unavailable and no file_base_url configured for per-file download."
            )
        source = "files"
        for key, name in cfg.files.items():
            dest = raw_dir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                url = f"{cfg.file_base_url.rstrip('/')}/{name}"
                print(f"Downloading {url} ...")
                done = False
                try:
                    resp = requests.get(url, timeout=FILE_TIMEOUT_S)
                    resp.raise_for_status()
                    if not _is_lfs_pointer(resp.content):
                        dest.write_bytes(resp.content)
                        done = True
                except requests.RequestException:
                    pass
                if not done and cfg.file_base_url_alt:
                    alt = f"{cfg.file_base_url_alt.rstrip('/')}/{name}"
                    try:
                        resp = requests.get(alt, timeout=FILE_TIMEOUT_S)
                        resp.raise_for_status()
                        if not _is_lfs_pointer(resp.content):
                            dest.write_bytes(resp.content)
                            done = True
                    except requests.RequestException:
                        pass
                if not done:
                    if key == "mutations":
                        print("  unavailable via datahub; fetching mutations via cBioPortal API.")
                        _fetch_mutations_api(cfg, dest)
                    else:
                        raise FileNotFoundError(
                            f"Could not download {name} from {url}"
                            + (f" or {cfg.file_base_url_alt}" if cfg.file_base_url_alt else "")
                        )
            elif _is_lfs_pointer(dest.read_bytes()):
                # A previous run stored a Git LFS pointer instead of real data.
                dest.unlink()
                if key == "mutations":
                    _fetch_mutations_api(cfg, dest)
                else:
                    raise FileNotFoundError(f"{dest} is a Git LFS pointer, not data")
            member_sha[name] = _sha256_file(dest)
        missing = [n for n in used_names if not (raw_dir / n).exists()]
        if missing:
            raise FileNotFoundError(f"Expected files not downloaded: {missing}")

    manifest = {
        "cohort": cfg.cohort,
        "archive_url": cfg.archive_url,
        "source": source,
        "archive_sha256": archive_sha,
        "members": member_sha,
    }
    manifest["manifest_sha256"] = _sha256_bytes(
        json.dumps(manifest, sort_keys=True).encode()
    )
    manifest_path = root / "data" / cfg.cohort / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest written to {manifest_path}")
    return manifest


CBIOPORTAL_API = "https://www.cbioportal.org/api"


def _fetch_mutations_api(cfg: CohortConfig, dest: Path) -> None:
    """Fetch mutations for the configured genes via the cBioPortal API and write
    a minimal MAF-style TSV (Hugo_Symbol, Tumor_Sample_Barcode, Variant_Classification)."""
    study = Path(cfg.archive_url).stem.removesuffix(".tar") if cfg.archive_url else ""
    profile = f"{study}_mutations"
    entrez = {g: cfg.entrez_ids[g] for g in cfg.mutation_genes if g in cfg.entrez_ids}
    body = {"entrezGeneIds": list(entrez.values()), "sampleListId": f"{study}_all"}
    for attempt in range(MAX_FETCH_ATTEMPTS):
        try:
            r = requests.post(
                f"{CBIOPORTAL_API}/molecular-profiles/{profile}/mutations/fetch",
                params={"projection": "DETAILED"},
                json=body,
                timeout=API_TIMEOUT_S,
            )
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == MAX_FETCH_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_DELAY_S)
    rows = r.json()
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("Hugo_Symbol\tTumor_Sample_Barcode\tVariant_Classification\n")
        for m in rows:
            fh.write(
                f"{m['gene']['hugoGeneSymbol']}\t{m['sampleId']}\t{m.get('mutationType', '')}\n"
            )


def load_manifest(cfg: CohortConfig, root: Path | str = DEFAULT_ROOT) -> dict:
    path = Path(root) / "data" / cfg.cohort / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))
