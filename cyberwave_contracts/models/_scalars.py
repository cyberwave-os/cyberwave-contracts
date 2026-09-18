"""Scalar annotations shared by every generated model.

Hand-written, unlike its siblings in this package: the generated modules import
these rather than each carrying a copy. Stamping them into every module made the
two contracts with no boolean field ship an unreachable ``Boolean`` alias, and
forced the generator to patch its own import list afterwards to cover names the
copy introduced.

pydantic's default (lax) mode coerces ``"0.5"`` into a float, which JSON Schema
``"type": "number"`` rejects outright -- so a generated model would be *more*
permissive than the contract it claims to implement. Blanket ``strict=True`` is
the wrong cure: it also rejects ``500.0`` for an integer field, which JSON Schema
accepts (2020-12 counts a number with zero fractional part as an integer) and
which the wire really carries, since JSON has one number type. Rejecting only the
types JSON Schema calls a different type gets both right.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator

__all__ = ["Boolean", "Integer", "Number"]


def _reject_non_numeric(v: object) -> object:
    """Strings and booleans are not numbers, whatever pydantic's lax mode thinks."""
    if isinstance(v, str | bool):
        raise ValueError(f"expected a number, got {type(v).__name__}")
    return v


def _reject_non_boolean(v: object) -> object:
    """Only a real bool is a boolean. Lax mode reads "yes" and 1 as True."""
    if not isinstance(v, bool):
        raise ValueError(f"expected a boolean, got {type(v).__name__}")
    return v


Number = Annotated[float, BeforeValidator(_reject_non_numeric)]
Integer = Annotated[int, BeforeValidator(_reject_non_numeric)]
Boolean = Annotated[bool, BeforeValidator(_reject_non_boolean)]
