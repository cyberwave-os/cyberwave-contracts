from __future__ import annotations

import dataclasses

import pytest

from cyberwave_contracts.manifest import (
    MERGE_STRATEGIES,
    SECTION_KINDS,
    SECTIONS_DIR,
    SECTIONS_RELATIVE,
    SYNC_KINDS,
    Contract,
    load_contracts,
    validate_section,
)


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


# --- sections ------------------------------------------------------------

_SECTION = Contract(
    id="asset.metadata.drivers.v1",
    kind="section",
    owner="backend",
    schema_owner="json_schema",
    id_field=None,
    python_source=None,
    mirrors=(),
    schema=f"{SECTIONS_RELATIVE}/asset.metadata.drivers.v1.schema.json",
    location="Asset.metadata.drivers",
    section_kind="catalog",
    merge="replace",
)


def _section(**changes: object) -> Contract:
    return dataclasses.replace(_SECTION, **changes)


def test_every_indexed_contract_obeys_the_section_rules() -> None:
    bad = {
        contract.id: reasons
        for contract in load_contracts()
        if (reasons := validate_section(contract))
    }
    assert not bad, bad


def test_every_section_schema_file_is_indexed_as_a_section() -> None:
    on_disk = {
        p.name.removesuffix(".schema.json") for p in SECTIONS_DIR.glob("*.schema.json")
    }
    indexed = {c.id for c in load_contracts() if c.kind == "section" and c.has_schema}
    assert on_disk == indexed


def test_a_section_schema_resolves_to_the_sections_directory() -> None:
    sections = [c for c in load_contracts() if c.kind == "section" and c.has_schema]
    assert sections, "the pilot section should be indexed"
    for contract in sections:
        assert contract.schema_path.parent == SECTIONS_DIR
        assert contract.schema_path.is_file()


def test_a_well_formed_section_passes() -> None:
    assert validate_section(_SECTION) == []


def test_merge_is_optional_on_an_asset_section() -> None:
    assert validate_section(_section(merge=None)) == []


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"id_field": "contract"}, "must not declare an id_field"),
        ({"location": None}, "must declare its location"),
        ({"location": "asset.metadata.drivers"}, "must read Entity.field"),
        ({"location": "Robot.metadata.drivers"}, "not one of"),
        ({"section_kind": "settings"}, "section_kind must be one of"),
        ({"section_kind": None}, "section_kind must be one of"),
        ({"merge": "deep_merge"}, "merge must be one of"),
        (
            {"location": "Environment.settings.geo", "merge": "replace"},
            "only Asset.* sections",
        ),
        (
            {
                "schema": "cyberwave-contracts/cyberwave_contracts/schemas/x.v1.schema.json"
            },
            "lives in",
        ),
    ],
)
def test_a_malformed_section_is_rejected(changes: dict, fragment: str) -> None:
    reasons = validate_section(_section(**changes))
    assert any(fragment in reason for reason in reasons), reasons


def test_section_keys_are_refused_on_a_payload() -> None:
    payload = _section(kind="payload", id_field="contract", merge=None)
    reasons = validate_section(payload)
    assert any("location is only meaningful on a section" in r for r in reasons)
    assert any("section_kind is only meaningful" in r for r in reasons)


def test_a_payload_schema_may_not_live_in_sections() -> None:
    payload = _section(
        kind="payload",
        id_field="contract",
        location=None,
        section_kind=None,
        merge=None,
    )
    assert any("holds section contracts only" in r for r in validate_section(payload))


def test_the_vocabularies_match_the_spec() -> None:
    """Changing these is a design decision recorded in entity-contracts.md."""
    assert SECTION_KINDS == {
        "configuration",
        "catalog",
        "reported",
        "derived",
        "bookkeeping",
    }
    assert MERGE_STRATEGIES == {
        "instance_only",
        "replace",
        "narrow_only",
        "seed_once",
        "precedence_chain",
    }
