"""The authoritative decomposition of the legacy ``source_type`` enum.

The data is package-owned because it is a cross-project wire contract.  Consumers
must not locate it through a monorepo checkout: released SDKs, edge nodes, and
partners only have the installed ``cyberwave-contracts`` wheel.
"""

from __future__ import annotations

from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any, Literal, get_args

import yaml

SourceType = Literal[
    "edge",
    "edge_leader",
    "edge_follower",
    "tele",
    "edit",
    "sim",
    "sim_tele",
]

#: The seven values, in wire-table order. Derived rather than restated so the
#: ``Literal`` and the tuple cannot disagree.
SOURCE_TYPE_VALUES: tuple[SourceType, ...] = get_args(SourceType)

SOURCE_TYPE_AXES_PATH = Path(__file__).resolve().parent / "source_type_axes.yml"


@cache
def _source_type_axes() -> dict[str, Any]:
    document = yaml.safe_load(SOURCE_TYPE_AXES_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("source_type_axes.yml must contain a mapping")
    return document


def load_source_type_axes() -> dict[str, Any]:
    """Return a fresh copy of the packaged source-type axes document."""
    return deepcopy(_source_type_axes())


#: Sentinel for "role unconstrained", distinct from ``role=None`` (role absent).
_ANY_ROLE: Any = object()


def source_types_where(
    *,
    substrate: str | tuple[str, ...] | None = None,
    direction: str | None = None,
    role: str | None | Any = _ANY_ROLE,
    role_not: str | None = None,
) -> frozenset[str]:
    """Source-type values whose axes match every stated constraint.

    ``role=None`` filters for an absent role; omitting ``role`` matches any. The
    two are different questions, and the self-echo and measured-plant guards turn
    on the difference.
    """
    wanted = (substrate,) if isinstance(substrate, str) else substrate
    return frozenset(
        value
        for value, row in _source_type_axes()["values"].items()
        if (wanted is None or row["substrate"] in wanted)
        and (direction is None or row["direction"] == direction)
        and (role is _ANY_ROLE or row["role"] == role)
        and (role_not is None or row["role"] != role_not)
    )
