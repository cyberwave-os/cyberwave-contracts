from __future__ import annotations

from cyberwave_contracts.manifest import SYNC_KINDS, load_contracts


def test_every_mirror_declares_a_known_sync_kind() -> None:
    bad = [
        f"{contract.id}: {mirror.path} declares sync {mirror.sync!r}"
        for contract in load_contracts()
        for mirror in contract.mirrors
        if mirror.sync not in SYNC_KINDS
    ]
    assert not bad, (
        f"sync must be one of {sorted(SYNC_KINDS)}; a copy nothing verifies has to "
        "be generated, checked, or replaced by an import:\n" + "\n".join(bad)
    )


def test_there_is_no_kind_for_an_unverified_copy() -> None:
    # Re-adding it would let the next hand copy be recorded instead of removed.
    assert "unchecked" not in SYNC_KINDS
