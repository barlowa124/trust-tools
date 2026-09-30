"""oncocs command line: download / split / run / verify."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sksurv.util import Surv

from oncocs import checks, evidence, schemas
from oncocs.config import DEFAULT_ROOT, load_cohort
from oncocs.data.download import download_cohort, load_manifest
from oncocs.data.harmonize import harmonize
from oncocs.data.load import (
    _read_clinical,
    load_cases_sequenced,
    load_clinical_patient,
    load_clinical_sample,
    load_expression,
    load_mutations,
)
from oncocs.models.cox import cox_summary, cox_survival, fit_cox
from oncocs.models.metrics import evaluate
from oncocs.models.rsf import fit_rsf, rsf_risk, rsf_survival
from oncocs.prep import prepare_features
from oncocs.splits import load_split, make_split


def _harmonized(cfg, root):
    patients, expr, report = harmonize(
        cfg,
        load_clinical_patient(cfg, root),
        load_clinical_sample(cfg, root),
        load_expression(cfg, root),
        load_mutations(cfg, root),
        load_cases_sequenced(cfg, root),
    )
    return patients, expr, report


def cmd_download(args):
    cfg = load_cohort(args.cohort, args.data_dir)
    manifest = download_cohort(cfg, args.data_dir)
    print(json.dumps({"cohort": cfg.cohort,
                      "manifest_sha256": manifest["manifest_sha256"]}, indent=2))


def cmd_split(args):
    cfg = load_cohort(args.cohort, args.data_dir)
    patients, _, report = _harmonized(cfg, args.data_dir)
    manifest = load_manifest(cfg, args.data_dir)
    split = make_split(patients, cfg, seed=args.seed, test_fraction=args.test_fraction,
                       data_manifest_sha256=manifest["manifest_sha256"],
                       root=args.data_dir, force=args.force)
    keys = ("cohort", "seed", "n_train", "n_test", "split_sha256")
    print(json.dumps({k: split[k] for k in keys}, indent=2))


def _run_pipeline(cfg, root, seed):
    """Full pipeline; returns (record_dict, patients)."""
    patients, expr, report = _harmonized(cfg, root)
    manifest = load_manifest(cfg, root)
    split = load_split(cfg, root)
    train_ids, test_ids = split["train_ids"], split["test_ids"]

    record = evidence.build_record(cfg.cohort, seed, Path(root),
                                   manifest["manifest_sha256"], split["split_sha256"],
                                   cfg.config_sha256)
    record["missingness"] = report["missingness"]
    record["dropped"] = report["dropped"]
    record["n_patients"] = report.get("n_patients_final")
    record["n_patients_with_expression"] = report.get("n_patients_with_expression")
    record["n_unsequenced_patients"] = report.get("n_unsequenced_patients")
    record["omitted_covariates"] = report.get("omitted_covariates") or []

    run_checks = [
        checks.check_split_integrity(split, patients.index),
        checks.check_min_events(patients.loc[train_ids, "event"], patients.loc[test_ids, "event"]),
    ]

    kinds = report["covariates_used"]
    max_t = float(patients.loc[test_ids, "os_months"].max())
    grid = np.linspace(0, max_t, 200)
    y_train = Surv.from_arrays(patients.loc[train_ids, "event"].astype(bool),
                               patients.loc[train_ids, "os_months"])
    y_test = Surv.from_arrays(patients.loc[test_ids, "event"].astype(bool),
                              patients.loc[test_ids, "os_months"])

    models = {}
    cox_clinical = None
    if not kinds:
        run_checks.append({"name": "covariates", "passed": False,
                           "detail": {"reason": "no covariates survived the missingness filter"},
                           "affects": "all"})
        abstain = {"abstained": True,
                   "reason": "no covariates survived the missingness filter"}
        models = {f"{m}/{fs}": {"metrics": dict(abstain)}
                  for m in ("cox", "rsf") for fs in ("clinical", "clinical_expression")}
    for fs in (() if not kinds else ("clinical", "clinical_expression")):
        include_expr = fs == "clinical_expression"
        X_tr, X_te, meta = prepare_features(
            patients, expr if include_expr else None, train_ids, test_ids,
            kinds, cfg.n_expression_genes if include_expr else 0, include_expr,
            cfg.excluded_genes, cfg.excluded_gene_patterns)

        train_df = X_tr.assign(os_months=patients.loc[train_ids, "os_months"],
                               event=patients.loc[train_ids, "event"])

        # Cox
        try:
            cph = fit_cox(train_df)
            cox_metrics = evaluate(y_train, y_test,
                                   np.asarray(cph.predict_partial_hazard(X_te)).ravel(),
                                   cox_survival(cph, X_te, grid), grid)
            cox_out = {"metrics": cox_metrics}
            if fs == "clinical":
                cox_clinical = cph
                cox_clinical_df = train_df
                cox_out["hazard_ratios"] = cox_summary(cph)
                cox_out["reference_levels"] = meta["reference_levels"]
        except Exception as exc:
            cox_out = {"metrics": {"abstained": True, "reason": f"fit/eval failed: {exc}"}}
        models[f"cox/{fs}"] = cox_out

        # RSF
        try:
            rsf = fit_rsf(train_df, seed)
            rsf_metrics = evaluate(y_train, y_test, rsf_risk(rsf, X_te),
                                   rsf_survival(rsf, X_te, grid), grid)
            models[f"rsf/{fs}"] = {"metrics": rsf_metrics}
            if include_expr:
                models[f"rsf/{fs}"]["gene_cols"] = meta["gene_cols"]
                cox_out["gene_cols"] = meta["gene_cols"]
        except Exception as exc:
            models[f"rsf/{fs}"] = {"metrics": {"abstained": True,
                                               "reason": f"fit/eval failed: {exc}"}}
            if include_expr:
                models[f"rsf/{fs}"]["gene_cols"] = meta["gene_cols"]
                cox_out["gene_cols"] = meta["gene_cols"]

        # recompute-compare imputation/selection/scaling for every feature
        # set, not only the expression one
        chk = checks.check_leakage(
            patients.loc[train_ids],
            expr.loc[train_ids] if include_expr else None,
            kinds,
            cfg.n_expression_genes if include_expr else 0,
            meta["gene_cols"], meta["impute"], meta["scale"],
            cfg.excluded_genes, cfg.excluded_gene_patterns)
        chk["name"] = f"leakage_{fs}"
        run_checks.append(chk)

    if cox_clinical is not None:
        run_checks.append(checks.check_proportional_hazards(cox_clinical, cox_clinical_df))
        run_checks.append(checks.check_convergence(cox_clinical))
    else:
        run_checks.append({"name": "proportional_hazards", "passed": False,
                           "detail": {"reason": "clinical Cox model did not fit"},
                           "affects": "cox_clinical"})
        run_checks.append({"name": "convergence", "passed": False,
                           "detail": {"converged": False}, "affects": "cox"})
    record["checks"] = run_checks

    # Apply abstentions
    failed = [c for c in run_checks if not c["passed"]]
    for name, out in models.items():
        reasons = []
        for c in failed:
            if c["affects"] == "all":
                reasons.append(f"{c['name']} failed")
            elif c["affects"] == "cox_clinical" and name == "cox/clinical":
                reasons.append(f"{c['name']} failed")
            elif c["affects"] == "cox" and name.startswith("cox/"):
                reasons.append(f"{c['name']} failed")
        if reasons:
            out["metrics"] = {"abstained": True, "reason": "; ".join(reasons)}
            out.pop("hazard_ratios", None)
    record["models"] = models
    return record


def cmd_run(args):
    cfg = load_cohort(args.cohort, args.data_dir)
    record = _run_pipeline(cfg, args.data_dir, args.seed)
    if record.get("git_dirty"):
        print("WARNING: git working tree is dirty; results are not bound to a clean commit.",
              file=sys.stderr)
    path = evidence.write_results(record, Path(args.data_dir))
    print(f"Results written to {path}")
    for c in record["checks"]:
        print(f"  check {c['name']}: {'PASS' if c['passed'] else 'FAIL'}")
    for name, out in record["models"].items():
        m = out["metrics"]
        tag = "ABSTAINED" if m.get("abstained") else f"C={m.get('harrell_c'):.3f}"
        print(f"  {name}: {tag}")


MISSING_TOKENS_FOR_QC = {"", "NA", "N/A", "[Not Available]", "[Not Evaluated]",
                         "[Unknown]", "[Pending]", "[Discrepancy]", "NaN"}


def _missing_counts(df):
    """Per-column count/fraction of missing tokens or NA."""
    out = {}
    for col in df.columns:
        s = df[col]
        m = s.isna() | s.astype("string").isin(MISSING_TOKENS_FOR_QC)
        if int(m.sum()):
            out[col] = {"missing": int(m.sum()), "fraction": round(float(m.mean()), 4)}
    return out


def cmd_qc(args):
    root = Path(args.data_dir)
    cfg = load_cohort(args.cohort, root)
    raw = root / "data" / cfg.cohort / "raw"

    frames = {
        "clinical_patient": _read_clinical(raw / cfg.files["clinical_patient"]),
        "clinical_sample": _read_clinical(raw / cfg.files["clinical_sample"]),
        "mutations": pd.read_csv(raw / cfg.files["mutations"], sep="\t", comment="#",
                                 dtype=str, low_memory=False),
    }
    expr_path = raw / cfg.files["expression"]
    if not expr_path.exists():
        expr_path = raw / cfg.files.get("expression_fallback", "")
    frames["expression"] = pd.read_csv(expr_path, sep="\t", comment="#",
                                       dtype=str, low_memory=False)

    schema_fns = {
        "clinical_patient": schemas.clinical_patient_schema,
        "clinical_sample": schemas.clinical_sample_schema,
        "mutations": schemas.mutations_schema,
        "expression": schemas.expression_schema,
    }
    qc = {"cohort": cfg.cohort,
          "schema_conformance": {},
          "missingness": {},
          "domain_violations": {},
          "duplicates": {},
          "sample_patient_conflicts": {},
          "split_integrity": {}}
    for name, df in frames.items():
        try:
            schema_fns[name](cfg).validate(df)
            qc["schema_conformance"][name] = {"ok": True}
        except Exception as exc:  # pandera SchemaError or subclass
            qc["schema_conformance"][name] = {"ok": False,
                                              "error": f"{type(exc).__name__}: {exc}"}
    for name in ("clinical_patient", "clinical_sample"):
        qc["missingness"][name] = _missing_counts(frames[name])

    cp = frames["clinical_patient"]
    pid, sid = cfg.patient_id, cfg.columns["sample_id"]
    spid = cfg.columns["sample_patient_id"]

    # value-domain violations on mapped categoricals
    allowed = {
        cfg.os_status: set(cfg.os_status_map.values()),
    }
    if cfg.covariates.get("stage"):
        allowed[cfg.covariates["stage"]] = set(cfg.stage_map)
    for col, ok_vals in allowed.items():
        if col not in cp.columns:
            continue
        s = cp[col].fillna("").astype(str).str.strip()
        bad = s[~s.isin(ok_vals) & ~s.isin(MISSING_TOKENS_FOR_QC)]
        if len(bad):
            qc["domain_violations"][col] = bad.value_counts().to_dict()

    qc["duplicates"] = {
        "clinical_patient_patient_id": int(cp[pid].duplicated().sum()),
        "clinical_sample_sample_id": int(frames["clinical_sample"][sid].duplicated().sum()),
    }

    cs = frames["clinical_sample"]
    valid_pid = set(cp[pid].dropna())
    qc["sample_patient_conflicts"] = {
        "sample_patient_id_not_in_patient_table":
            int((~cs[spid].isin(valid_pid)).sum()),
        "patients_with_multiple_primary_samples":
            int((cs[cs[sid].astype(str).str.endswith(cfg.sample_type_suffix)]
                 .groupby(spid).size() > 1).sum()),
    }

    try:
        seq = load_cases_sequenced(cfg, root)
        qc["n_unsequenced_patients"] = int(
            (~cs[cs[sid].astype(str).str.endswith(cfg.sample_type_suffix)][sid]
             .isin(seq)).sum())
    except Exception:
        qc["n_unsequenced_patients"] = None

    try:
        split = load_split(cfg, root)
        chk = checks.check_split_integrity(split, set(cp[pid].dropna()))
        data_ids = set(cp[pid].dropna())
        chk["detail"]["test_ids_all_in_data"] = \
            all(t in data_ids for t in split["test_ids"])
        qc["split_integrity"] = chk
    except Exception as exc:
        qc["split_integrity"] = {"passed": None, "detail": {"error": str(exc)}}

    runs = [d for d in (root / "results" / cfg.cohort).glob("*")
            if (d / "results.json").exists()]
    runs.sort(key=lambda d: (d / "results.json").stat().st_mtime)
    out = (runs[-1] if runs else root / "results" / cfg.cohort / "qc") / "qc.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(qc, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"QC {cfg.cohort}: wrote {out}")
    for name, s in qc["schema_conformance"].items():
        print(f"  schema {name}: {'OK' if s['ok'] else 'FAIL ' + s['error'][:80]}")
    for frame, cols in qc["missingness"].items():
        print(f"  missingness {frame}: {len(cols)} columns with missing values")
    for col, viols in qc["domain_violations"].items():
        print(f"  domain violations {col}: {viols}")
    print(f"  duplicates: {qc['duplicates']}")
    print(f"  sample->patient conflicts: {qc['sample_patient_conflicts']}")
    print(f"  unsequenced primary samples: {qc['n_unsequenced_patients']}")
    si = qc["split_integrity"]
    print(f"  split integrity: {si.get('passed')} {si.get('detail', {})}")
    return 0


def cmd_verify(args):
    root = Path(args.data_dir)
    record = json.loads(Path(args.results).read_text())
    cfg = load_cohort(record["cohort"], root)

    # recompute data manifest
    manifest_path = root / "data" / record["cohort"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    from oncocs.data.download import _sha256_file
    ok = True
    for name, sha in manifest["members"].items():
        actual = _sha256_file(root / "data" / record["cohort"] / "raw" / name)
        if actual != sha:
            print(f"FAIL: member {name} sha mismatch")
            ok = False
    canon = json.dumps({k: v for k, v in manifest.items() if k != "manifest_sha256"},
                       sort_keys=True).encode()
    import hashlib
    if hashlib.sha256(canon).hexdigest() != manifest["manifest_sha256"]:
        print("FAIL: manifest hash mismatch")
        ok = False
    if manifest["manifest_sha256"] != record["data_manifest_sha256"]:
        print("FAIL: manifest hash does not match recorded run")
        ok = False

    # recompute split hash
    split = load_split(cfg, root)
    from oncocs.splits import split_sha256
    if split_sha256(split["train_ids"], split["test_ids"]) != record["split_sha256"]:
        print("FAIL: split hash mismatch")
        ok = False

    # rerun with recorded seed and compare
    rerun = _run_pipeline(cfg, root, record["seed"])
    rec_s, rer_s = evidence.strip_volatile(record), evidence.strip_volatile(rerun)
    if rec_s == rer_s:
        print("PASS" if ok else "FAIL")
        return 0 if ok else 1
    print("FAIL: rerun results differ from recorded results")
    for k in sorted(set(rec_s) | set(rer_s)):
        if rec_s.get(k) != rer_s.get(k):
            print(f"  field differs: {k}")
    return 1


def cmd_agent_run(args):
    from oncocs.agents.graph import run_agent
    cfg = load_cohort(args.cohort, args.data_dir)
    results_path = Path(args.results)
    if args.backend == "scripted-demo":
        from oncocs.agents.demo import demo_backend
        from oncocs.splits import load_split
        backend = demo_backend(json.loads(results_path.read_text()),
                               load_split(cfg, args.data_dir))
    else:
        from oncocs.llm.ollama import OllamaBackend
        backend = OllamaBackend(model=args.model)
    record = run_agent(args.cohort, results_path, backend, args.seed,
                       Path(args.data_dir))
    agent_dir = (Path(record["results_path"]).parent / "agent"
                 / record["agent_run_id"])
    print(f"Agent run written to {agent_dir / 'agent_run.json'}")
    print(f"  status: {record['status']}  attempts: {len(record['drafts'])}")


def cmd_agent_replay(args):
    import json as _json

    from oncocs.agents.replay import replay_agent
    status, msg = replay_agent(Path(args.agent_run))
    if status == "FROZEN":
        rec = _json.loads(Path(args.agent_run).read_text(encoding="utf-8"))
        print(f"FROZEN: transcript mismatch at call {msg}, prompts changed "
              f"since this run was recorded (recorded under commit "
              f"{rec.get('git_commit')}); drafts and verification remain as "
              f"preserved evidence.")
        return 2
    print(f"{status}: {msg}")
    return 0 if status == "PASS" else 1


def cmd_approve(args):
    from oncocs.agents.approve import approve
    try:
        path = approve(Path(args.agent_run), by=args.by, note=args.note or "")
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"Approved. Report updated: {path}")
    return 0


def cmd_agent_summarize(args):
    """Scan all agent/*/agent_run.json; write results/agent_model_comparison.json."""
    from oncocs.agents.replay import replay_agent
    root = Path(args.data_dir)
    entries = []
    for p in sorted(root.glob("results/*/*/agent/*/agent_run.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        if args.replay:
            rec["_replay_status"], _ = replay_agent(p)
        findings = []
        for d in rec.get("drafts", []):
            counts = {}
            for k, val in d.get("verification", {}).items():
                if isinstance(val, list) and val:
                    counts[k] = len(val)
                elif isinstance(val, bool) and val:
                    counts[k] = 1
            findings.append({"attempt": d.get("attempt"), "findings": counts})
        entries.append({
            "cohort": rec.get("cohort"), "run_id": p.parents[2].name,
            "agent_run_id": rec.get("agent_run_id"),
            "model_id": rec.get("model_id"), "status": rec.get("status"),
            "attempts": len(rec.get("drafts", [])),
            "analysis_plan_fallback": rec.get("analysis_plan_fallback"),
            "findings_per_attempt": findings,
            "replay": rec.get("_replay_status") if args.replay else None,
            "human_review": rec.get("human_review"),
            "path": str(p.relative_to(root)),
        })
    out = root / "results" / "agent_model_comparison.json"
    out.write_text(json.dumps({"runs": entries}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(entries)} agent runs)")


def cmd_rag_fetch(args):
    from oncocs.rag.fetch import fetch_corpus
    m = fetch_corpus(args.data_dir)
    print(json.dumps({"documents": sorted(m["members"]),
                      "bytes": sum(v["bytes"] for v in m["members"].values())}, indent=2))


def cmd_rag_compare(args):
    """Compare retrieval modes on the same queries; writes
    results/rag_mode_comparison.json."""
    from oncocs.rag.retrieve import retrieve
    root = Path(args.data_dir)
    queries = [q.strip() for q in args.queries.split(";") if q.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    out = {"queries": queries, "modes": modes, "per_query": []}
    for q in queries:
        entry = {"query": q, "per_mode": {}}
        tag_sets = {}
        for m in modes:
            hits = retrieve(q, root, top_k=args.top_k, mode=m)
            entry["per_mode"][m] = list(hits)
            tag_sets[m] = set(hits)
        entry["overlap_with_first_mode"] = {
            m: sorted(tag_sets[m] & tag_sets[modes[0]]) for m in modes[1:]}
        out["per_query"].append(entry)
    dest = root / "results" / "rag_mode_comparison.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {dest}")


def cmd_serve(args):
    import uvicorn

    from oncocs.api.app import create_app
    uvicorn.run(create_app(Path(args.data_dir)), host=args.host, port=args.port)


def cmd_reject(args):
    from oncocs.agents.approve import reject
    try:
        path = reject(Path(args.agent_run), by=args.by, reason=args.reason)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"Rejected. Report updated: {path}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="oncocs")
    p.add_argument("--data-dir", default=str(DEFAULT_ROOT),
                   help="project root containing cohorts/, data/, splits/, results/")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("download")
    d.add_argument("--cohort", required=True)
    d.set_defaults(fn=cmd_download)

    s = sub.add_parser("split")
    s.add_argument("--cohort", required=True)
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--test-fraction", type=float, default=0.3)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_split)

    r = sub.add_parser("run")
    r.add_argument("--cohort", required=True)
    r.add_argument("--seed", type=int, required=True)
    r.set_defaults(fn=cmd_run)

    q = sub.add_parser("qc")
    q.add_argument("--cohort", required=True)
    q.set_defaults(fn=cmd_qc)

    v = sub.add_parser("verify")
    v.add_argument("results")
    v.set_defaults(fn=cmd_verify)

    ag = sub.add_parser("agent")
    ags = ag.add_subparsers(dest="agent_command", required=True)
    ar = ags.add_parser("run")
    ar.add_argument("--cohort", required=True)
    ar.add_argument("--results", required=True)
    ar.add_argument("--backend", choices=["ollama", "scripted-demo"], default="ollama")
    ar.add_argument("--model", default="gemma3:4b")
    ar.add_argument("--seed", type=int, default=None)
    ar.set_defaults(fn=cmd_agent_run)
    rp = ags.add_parser("replay")
    rp.add_argument("agent_run")
    rp.set_defaults(fn=cmd_agent_replay)
    sm = ags.add_parser("summarize")
    sm.add_argument("--replay", action="store_true",
                    help="replay each run and record PASS/FAIL/FROZEN")
    sm.set_defaults(fn=cmd_agent_summarize)

    rg = sub.add_parser("rag")
    rgs = rg.add_subparsers(dest="rag_command", required=True)
    rf = rgs.add_parser("fetch")
    rf.set_defaults(fn=cmd_rag_fetch)
    rc = rgs.add_parser("compare")
    rc.add_argument("--queries", required=True,
                    help="semicolon-separated queries to compare")
    rc.add_argument("--modes", default="bm25,tfidf")
    rc.add_argument("--top-k", type=int, default=5)
    rc.set_defaults(fn=cmd_rag_compare)

    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(fn=cmd_serve)

    ap = sub.add_parser("approve")
    ap.add_argument("agent_run")
    ap.add_argument("--by", required=True)
    ap.add_argument("--note", default="")
    ap.set_defaults(fn=cmd_approve)

    rj = sub.add_parser("reject")
    rj.add_argument("agent_run")
    rj.add_argument("--by", required=True)
    rj.add_argument("--reason", required=True)
    rj.set_defaults(fn=cmd_reject)

    args = p.parse_args(argv)
    args.data_dir = Path(args.data_dir)
    rc = args.fn(args)
    return rc if isinstance(rc, int) else 0


if __name__ == "__main__":
    sys.exit(main())
