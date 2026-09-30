"""Fetch NCI PDQ summaries (U.S. public domain) into a local text corpus."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import requests
import yaml

from oncocs.config import DEFAULT_ROOT

REQUEST_TIMEOUT_S = 120

LICENSE_NOTE = (
    "NCI PDQ summaries are U.S. public domain. NCI asks that reproduced "
    "content carry the suggested citation recorded in 'citation'."
)
PDQ_CITATION = ("National Cancer Institute. PDQ(R) Cancer Information Summary. "
                "Bethesda, MD: National Cancer Institute. Retrieved from "
                "cancer.gov.")


class _ParagraphParser(HTMLParser):
    """Collect visible text of <p> and <li> blocks; skip script/style/nav."""

    _SKIP = {"script", "style", "nav", "header", "footer", "noscript", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self._buf: list[str] = []
        self._depth_skip = 0
        self._in_block = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._depth_skip += 1
        elif tag in ("p", "li") and not self._depth_skip:
            self._in_block = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._depth_skip:
            self._depth_skip -= 1
        elif tag in ("p", "li") and self._in_block:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if len(text) >= 40:  # skip crumbs like "Updated:" labels
                self.paragraphs.append(text)
            self._in_block = False
            self._buf = []

    def handle_data(self, data):
        if self._in_block and not self._depth_skip:
            self._buf.append(data)


def html_to_paragraphs(html: str) -> list[str]:
    p = _ParagraphParser()
    p.feed(html)
    return p.paragraphs


def fetch_corpus(root: Path | str = DEFAULT_ROOT) -> dict:
    """Download every rag_docs entry across cohort configs; write corpus files."""
    root = Path(root)
    corpus = root / "rag" / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    docs = {}
    for cfg_path in sorted((root / "cohorts").glob("*.yaml")):
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        for doc in raw.get("rag_docs", []):
            docs[doc["doc_id"]] = doc["url"]

    members = {}
    for doc_id, url in sorted(docs.items()):
        dest = corpus / f"{doc_id}.txt"
        if not dest.exists():
            print(f"Fetching {url} ...")
            resp = requests.get(url, timeout=REQUEST_TIMEOUT_S,
                                headers={"User-Agent": "oncocs-research/0.1"})
            resp.raise_for_status()
            dest.write_text("\n\n".join(html_to_paragraphs(resp.text)),
                            encoding="utf-8")
        text = dest.read_text(encoding="utf-8")
        members[doc_id] = {"url": url, "sha256": hashlib.sha256(
            text.encode()).hexdigest(),
            "fetched_at": datetime.now(UTC).isoformat(),
            "bytes": dest.stat().st_size}

    manifest = {"license": LICENSE_NOTE, "citation": PDQ_CITATION,
                "members": members}
    (corpus / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
