"""Section upgrades: registered only for sections, pure and idempotent."""

from __future__ import annotations

from copy import deepcopy

import pytest
from cyberwave_contracts import load_contracts
from cyberwave_contracts import upgrades as module


def test_upgrades_are_registered_only_for_section_contracts() -> None:
    sections = {c.id for c in load_contracts() if c.kind == "section"}
    assert set(module.UPGRADES) <= sections


def test_a_section_without_an_upgrade_is_already_canonical() -> None:
    value = {"a": 1}
    assert module.upgrade("environment.settings.geo.v1", value) is value


@pytest.fixture
def registered(monkeypatch):
    monkeypatch.setattr(module, "UPGRADES", {})

    @module.register("demo.v1")
    def rename(value):
        if "old" in value:
            value["new"] = value.pop("old")
        return value

    return rename


def test_the_callers_value_is_never_modified(registered) -> None:
    value = {"old": 1}
    original = deepcopy(value)
    assert module.upgrade("demo.v1", value) == {"new": 1}
    assert value == original


def test_registering_twice_is_refused(registered) -> None:
    with pytest.raises(ValueError, match="already"):
        module.register("demo.v1")(lambda v: v)
