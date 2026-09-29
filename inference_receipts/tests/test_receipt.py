import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from llmreceipt import receipt as R  # noqa: E402
from llmreceipt import verify as V  # noqa: E402


def mk(output="hello", prompt="say hi", prev=None):
    return R.make_receipt(
        backend={"kind": "hf-transformers", "torch": "2.8.0"},
        model={"id": "org/model", "revision": "abc",
               "weights_sha256": "w" * 64},
        input_text=prompt,
        generation={"do_sample": False, "temperature": 0.0,
                    "max_new_tokens": 8},
        output_text=output, gen_time_s=0.5, n_new_tokens=2,
        prev_receipt=prev)


def test_receipt_id_is_content_hash():
    r = mk()
    assert R.receipt_hash(r) == r["receipt_id"]
    assert r["receipt_id"].startswith("rcpt-")


def test_receipt_changes_with_output():
    assert mk(output="a")["receipt_id"] != mk(output="b")["receipt_id"]


def test_chain_links_prev():
    r1, r2 = mk(), mk(prev=mk())
    assert r1["chain_prev"] == "genesis"
    assert r2["chain_prev"] != "genesis"


def test_chain_check_clean(tmp_path):
    r1 = mk("first")
    r2 = mk("second", prev=r1)
    log = tmp_path / "r.jsonl"
    R.append_log(str(log), r1)
    R.append_log(str(log), r2)
    assert R.check_chain(R.load_log(str(log))) == []


def test_chain_detects_tampered_body(tmp_path):
    r1 = mk("first")
    r2 = mk("second", prev=r1)
    r2 = dict(r2, output={**r2["output"], "text": "edited later"})
    log = tmp_path / "r.jsonl"
    for r in (r1, r2):
        R.append_log(str(log), r)
    problems = R.check_chain(R.load_log(str(log)))
    assert any("tampered" in p for p in problems)


def test_chain_detects_reorder(tmp_path):
    r1 = mk("first")
    r2 = mk("second", prev=r1)
    log = tmp_path / "r.jsonl"
    for r in (r2, r1):  # reversed
        R.append_log(str(log), r)
    problems = R.check_chain(R.load_log(str(log)))
    assert any("chain break" in p for p in problems)


def test_verify_log_flags_tamper(tmp_path):
    r1 = mk("first")
    r2 = mk("second", prev=r1)
    r2["output"]["text"] = "forged output"
    rep = V.verify_log([r1, r2], replay=False)
    assert not rep["ok"]
    assert any("hash" in p for p in rep["problems"])


def test_canonical_json_stable():
    a = {"b": 1, "a": [1, 2]}
    assert R.canonical_json(a) == R.canonical_json({"a": [1, 2], "b": 1})
