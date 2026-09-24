from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github/scripts/check_source_type_conformance.py"
SPEC = importlib.util.spec_from_file_location("source_type_conformance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
monitor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = monitor
SPEC.loader.exec_module(monitor)


def test_advisory_mode_does_not_block_on_findings() -> None:
    finding = monitor.Finding(ROOT / "consumer.py", "example drift")

    assert monitor.exit_code([finding], strict=False) == 0
    assert "advisory mode" in monitor.render_report([finding], strict=False)


def test_strict_mode_can_promote_the_same_findings_to_a_gate() -> None:
    finding = monitor.Finding(ROOT / "consumer.py", "example drift")

    assert monitor.exit_code([finding], strict=True) == 1
    assert "blocking mode" in monitor.render_report([finding], strict=True)


def test_assignment_scanner_ignores_comparisons(tmp_path: Path) -> None:
    source = tmp_path / "consumer.py"
    source.write_text(
        'SOURCE_TYPE_SIM_TELE = "sim_tele"\n'
        'if source_type == SOURCE_TYPE_SIM_TELE and command != "stop":\n'
        '    pass\n',
        encoding="utf-8",
    )

    assert monitor._assignments(source) == {"SOURCE_TYPE_SIM_TELE": "sim_tele"}


def test_ledger_entries_are_reported_but_do_not_block() -> None:
    ledger = _ledger_findings()

    blocking, exempt = monitor.partition(ledger)

    assert exempt == ledger
    assert blocking == []
    assert monitor.exit_code(blocking, strict=True) == 0
    assert "Known divergence" in monitor.render_report(
        blocking, strict=True, exempt=exempt
    )


def test_a_ledger_entry_that_matches_nothing_blocks() -> None:
    """Clearing a divergence has to retire its exemption, not leave it rotting."""
    blocking, exempt = monitor.partition([])

    assert exempt == []
    assert len(blocking) == len(monitor.KNOWN_DIVERGENCE)
    assert all("no longer applies" in f.message for f in blocking)
    assert monitor.exit_code(blocking, strict=True) == 1


def test_drift_outside_the_ledger_blocks() -> None:
    finding = monitor.Finding(monitor.REPO_ROOT / "consumer.py", "example drift")

    blocking, _ = monitor.partition([finding, *_ledger_findings()])

    assert finding in blocking
    assert monitor.exit_code(blocking, strict=True) == 1


def test_the_repository_is_clean_under_strict_today() -> None:
    """Pins the `--strict` flip: every divergence left is on the ledger."""
    blocking, _ = monitor.partition(monitor.collect_findings())

    assert blocking == [], [f"{f.path}: {f.message}" for f in blocking]


def _ledger_findings() -> list:
    return [
        monitor.Finding(monitor.REPO_ROOT / path, message)
        for path, message in monitor.KNOWN_DIVERGENCE
    ]
