from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github/scripts/check_source_type_conformance.py"
# The monitor is a monorepo script that checks consumers this package cannot see.
# The public mirror (cyberwave-os/cyberwave-contracts) ships these tests without
# it, so there is nothing to exercise there.
if not SCRIPT.is_file():
    pytest.skip(
        "monorepo-only: the conformance monitor is not in this checkout",
        allow_module_level=True,
    )
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


def test_rust_const_sets_resolve_names_and_literals(tmp_path: Path) -> None:
    source = tmp_path / "source_type.rs"
    source.write_text(
        'pub const SOURCE_TYPE_SIM: &str = "sim";\n'
        "pub const ACCEPTED: [&str; 2] = [\n"
        "    SOURCE_TYPE_SIM,\n"
        '    "tele",\n'
        "];\n",
        encoding="utf-8",
    )

    assert monitor._literal_set(source, "ACCEPTED", {}) == {"sim", "tele"}
    with pytest.raises(ValueError, match="was not found"):
        monitor._literal_set(source, "MISSING", {})


def test_media_service_sets_track_the_contract_predicates() -> None:
    """Drift either way blocks: the SFU's copy must equal the contract predicate."""
    path = ROOT / "media-service/video-streaming/src/mqtt/source_type.rs"
    canonical = monitor._canonical_names(monitor._load_contract())

    assert monitor._literal_set(
        path, "WEBRTC_COMMAND_SOURCE_TYPES", canonical
    ) == monitor.source_types_where(substrate=("hardware", "sim"), role=None)
    assert monitor._literal_set(
        path, "SIM_SUBSTRATE_SOURCE_TYPES", canonical
    ) == monitor.source_types_where(substrate="sim")


def test_a_rust_set_missing_a_value_no_longer_matches(tmp_path: Path) -> None:
    """The check `collect_findings` runs, on a copy that dropped `sim_tele`."""
    original = ROOT / "media-service/video-streaming/src/mqtt/source_type.rs"
    drifted = tmp_path / "source_type.rs"
    text = original.read_text(encoding="utf-8")
    last_member = "    SOURCE_TYPE_SIM_TELE,\n];"
    assert last_member in text
    drifted.write_text(text.replace(last_member, "];"), encoding="utf-8")
    canonical = monitor._canonical_names(monitor._load_contract())

    actual = monitor._literal_set(drifted, "WEBRTC_COMMAND_SOURCE_TYPES", canonical)

    assert actual == {"edge", "tele", "sim"}
    assert actual != monitor.source_types_where(
        substrate=("hardware", "sim"), role=None
    )


#: A stand-in ledger. These tests exercise the exemption mechanics, which have to
#: keep working whether or not the repository currently has a divergence to
#: excuse -- reading the real ledger made them vacuous the moment it emptied.
_SAMPLE_LEDGER = (("consumer.py", "example divergence"),)


@pytest.fixture
def sample_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(monitor, "KNOWN_DIVERGENCE", _SAMPLE_LEDGER)


def test_the_ledger_is_empty() -> None:
    """The PREVIEW exemptions retired with the enums that carried them.

    A new entry is a decision, not a default.
    """
    assert monitor.KNOWN_DIVERGENCE == ()


@pytest.mark.usefixtures("sample_ledger")
def test_ledger_entries_are_reported_but_do_not_block() -> None:
    ledger = _ledger_findings()

    blocking, exempt = monitor.partition(ledger)

    assert exempt == ledger
    assert blocking == []
    assert monitor.exit_code(blocking, strict=True) == 0
    assert "Known divergence" in monitor.render_report(
        blocking, strict=True, exempt=exempt
    )


@pytest.mark.usefixtures("sample_ledger")
def test_a_ledger_entry_that_matches_nothing_blocks() -> None:
    """Clearing a divergence has to retire its exemption, not leave it rotting."""
    blocking, exempt = monitor.partition([])

    assert exempt == []
    assert len(blocking) == len(_SAMPLE_LEDGER)
    assert all("no longer applies" in f.message for f in blocking)
    assert monitor.exit_code(blocking, strict=True) == 1


@pytest.mark.usefixtures("sample_ledger")
def test_drift_outside_the_ledger_blocks() -> None:
    finding = monitor.Finding(monitor.REPO_ROOT / "consumer.py", "example drift")

    blocking, _ = monitor.partition([finding])

    assert finding in blocking
    assert monitor.exit_code(blocking, strict=True) == 1


def test_the_repository_is_clean_under_strict_today() -> None:
    """Pins the `--strict` gate: no drift, and nothing left on the ledger to exempt."""
    blocking, _ = monitor.partition(monitor.collect_findings())

    assert blocking == [], [f"{f.path}: {f.message}" for f in blocking]


def _ledger_findings() -> list:
    return [
        monitor.Finding(monitor.REPO_ROOT / path, message)
        for path, message in monitor.KNOWN_DIVERGENCE
    ]
