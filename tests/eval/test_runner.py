from pathlib import Path

from eval.runner import run_all
from toolgate.domain.vocab import Mode


def test_runner_writes_metrics(tmp_path: Path) -> None:
    summary = run_all(modes=[Mode.direct, Mode.gateway], out_dir=tmp_path)
    assert set(summary) == {"direct", "gateway"}
    assert (tmp_path / "direct.jsonl").exists()
    assert (tmp_path / "gateway.metrics.json").exists()
    assert (tmp_path / "summary.json").exists()
    # Direct baseline should show unauthorized passes on attack cases.
    assert summary["direct"].unauthorized_pass_rate > 0
    # Gateway should block the labeled attacks in the suite.
    assert summary["gateway"].unauthorized_pass_rate == 0
    assert summary["gateway"].false_block_rate == 0
