"""Bring a stored section value to its contract's current shape.

A section contract describes data that is already in databases, so its shape can
only move forward by migrating rows. Each step is one pure function per contract,
``upgrade(value) -> value``, registered here. The same function serves twice:
readers apply it during the window in which both shapes exist, and the backend's
``migrate_entity_section`` command applies it to every stored row, so the read
path and the migration can never disagree about what the canonical form is.

The rules an upgrade must follow, checked by the tests:

* **Pure.** No I/O, no clock, no randomness: the same input gives the same output
  on every tier and every run.
* **Non-mutating.** The caller's value is left untouched; return a new one.
* **Idempotent.** ``upgrade(upgrade(v)) == upgrade(v)``, so a migration that is
  re-run, or a reader that meets an already migrated row, changes nothing.
* **Total on what it does not recognise.** A value the function does not know how
  to upgrade is returned as it came, not raised on: the census, not the reader,
  reports rows that stay invalid.

A section without a registered function is already canonical: :func:`upgrade`
returns its value unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

Upgrade = Callable[[Any], Any]

#: Contract id -> its upgrade. Only section contracts may appear here.
UPGRADES: dict[str, Upgrade] = {}


def register(contract_id: str) -> Callable[[Upgrade], Upgrade]:
    """Register the decorated function as *contract_id*'s upgrade."""

    def decorate(function: Upgrade) -> Upgrade:
        if contract_id in UPGRADES:
            raise ValueError(f"{contract_id} already has an upgrade registered")
        UPGRADES[contract_id] = function
        return function

    return decorate


def upgrade(contract_id: str, value: Any) -> Any:
    """*value* in *contract_id*'s current shape; *value* itself is never modified."""
    function = UPGRADES.get(contract_id)
    if function is None:
        return value
    return function(deepcopy(value))
