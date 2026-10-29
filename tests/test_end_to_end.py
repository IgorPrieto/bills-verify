import json

from bills_verify import cli
from bills_verify.synth import EXPECTED_RULE


def test_demo_detects_every_planted_problem_without_false_positives(tmp_path):
    assert cli.main(["demo", "--out", str(tmp_path), "--n", "300", "--seed", "11"]) == 0
    truth = json.loads((tmp_path / "truth.json").read_text())
    result = json.loads((tmp_path / "informe.json").read_text())
    hits = {}
    for f in result["findings"]:
        hits.setdefault(f["conversation_id"], set()).add(f["rule"])
    for cid, cat in truth.items():
        expected = EXPECTED_RULE.get(cat)
        got = hits.get(cid, set())
        if expected:
            assert got == {expected}, (cid, cat, got)
        else:
            assert not got, (cid, cat, got)
    html = (tmp_path / "informe.html").read_text()
    assert "son discutibles" in html and "<script" not in html


def test_fail_above_threshold_for_ci(tmp_path):
    cli.main(["demo", "--out", str(tmp_path)])
    rc = cli.main(["verify", "--source", "intercom", "--conversations", str(tmp_path / "intercom.json"),
                   "--billing", str(tmp_path / "billing.csv"), "--out", str(tmp_path / "r.html"),
                   "--fail-above", "5"])
    assert rc == 1
