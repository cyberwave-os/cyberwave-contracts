"""The frontend's TypeScript generator understands the same keywords as this one.

Both generators read the same schema files. If one learns a keyword the other
does not, a schema using it is either refused on one side or, worse, typed
looser there than the contract says. The script lives outside this package, so
the test runs only in a monorepo checkout.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cyberwave_contracts._generate import _MODELLED_KEYWORDS

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "cyberwave-frontend"
    / "scripts"
    / "generate-contract-types.mjs"
)


@pytest.mark.skipif(not _SCRIPT.is_file(), reason="needs the monorepo checkout")
def test_both_generators_model_the_same_keywords() -> None:
    block = re.search(
        r"const MODELLED = new Set\(\[(.*?)\]\);",
        _SCRIPT.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert block, f"MODELLED not found in {_SCRIPT}"
    assert set(re.findall(r'"([^"]+)"', block.group(1))) == _MODELLED_KEYWORDS
