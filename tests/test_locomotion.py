"""The locomotion module: its public surface, its imports, and its agreement with
the generated models.

The module is hand-written behavior (normalising, clamping, building, stopping)
sitting beside schemas and generated models that describe the same payloads, so
the three can disagree. These tests are where they are made to agree, from inside
the package -- a copy of the tree outside the monorepo runs them too.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from cyberwave_contracts import locomotion
from cyberwave_contracts.models.aerial_velocity_command_v1 import (
    AerialVelocityCommandV1,
)
from cyberwave_contracts.models.locomotion_velocity_command_v1 import (
    LocomotionVelocityCommandV1,
)

_SOURCE = Path(locomotion.__file__)


def _tree() -> ast.Module:
    return ast.parse(_SOURCE.read_text(encoding="utf-8"))


#: What other trees import from this module. This is the 0.1.0 promise, and it is
#: pinned here rather than in an ``__all__`` because the module's source cannot take
#: cosmetic edits (see its header). Changing this set is a public API change.
_PUBLIC_API = frozenset(
    {
        "AERIAL_VELOCITY_COMMAND_CONTRACT",
        "AERIAL_VELOCITY_COMMAND_REQUIRED_FIELDS",
        "LOCOMOTION_VELOCITY_COMMAND_CONTRACT",
        "LOCOMOTION_VELOCITY_COMMAND_REQUIRED_FIELDS",
        "MAX_ACTIVE_HOLD_SECONDS",
        "MIN_ACTIVE_HOLD_SECONDS",
        "BodyVelocityCommand",
        "LocomotionVelocityCommand",
        "LocomotionVelocityCommandError",
        "build_locomotion_velocity_command",
        "hold_seconds_for_velocity_command",
        "normalize_body_velocity_command",
        "normalize_locomotion_velocity_command",
        "stop_aerial_velocity_command",
        "stop_locomotion_velocity_command",
    }
)


def _public_definitions() -> set[str]:
    defined = set()
    for node in _tree().body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            defined.update(
                target.id
                for target in node.targets
                if isinstance(target, ast.Name) and target.id.isupper()
            )
    return {name for name in defined if not name.startswith("_")}


def test_the_public_surface_is_pinned() -> None:
    """A helper added without an underscore would be importable, and used by a
    consumer, long before anyone noticed it was never part of the promise."""
    defined = _public_definitions()
    assert defined == _PUBLIC_API, (
        f"public but not in the pinned API: {sorted(defined - _PUBLIC_API)}; "
        f"pinned but not defined: {sorted(_PUBLIC_API - defined)}. Underscore a "
        "helper, or add the name to _PUBLIC_API on purpose."
    )
    assert all(hasattr(locomotion, name) for name in _PUBLIC_API)


def test_the_module_imports_only_the_standard_library() -> None:
    """The SDK still carries a generated copy of this file (python-sdk-gen.sh).

    A copy cannot import the package it is a copy of, so a third-party or
    package-relative import here would break ``import cyberwave`` for every
    consumer of the SDK, not just of this package.
    """
    allowed = set(sys.stdlib_module_names) | {"__future__"}
    offenders = []
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            offenders += [
                a.name for a in node.names if a.name.split(".")[0] not in allowed
            ]
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in allowed:
                offenders.append(f"{'.' * node.level}{node.module}")
    assert offenders == [], f"non-standard-library imports: {offenders}"


def test_built_and_stop_commands_satisfy_the_generated_locomotion_model() -> None:
    built = locomotion.build_locomotion_velocity_command(
        linear_x=0.4, linear_y=-0.1, angular_z=0.2, duration_ms=500, gait="trot"
    )
    for payload in (
        built.to_payload(),
        locomotion.stop_locomotion_velocity_command(),
    ):
        model = LocomotionVelocityCommandV1.model_validate(payload)
        assert model.contract == locomotion.LOCOMOTION_VELOCITY_COMMAND_CONTRACT
        # The normalizer accepts what it emits.
        again = locomotion.normalize_locomotion_velocity_command(payload)
        assert again.duration_ms == payload["duration_ms"]


def test_the_stop_command_is_a_stop() -> None:
    stop = locomotion.normalize_locomotion_velocity_command(
        locomotion.stop_locomotion_velocity_command()
    )
    assert stop.is_stop
    assert (stop.linear_x, stop.linear_y, stop.angular_z) == (0.0, 0.0, 0.0)
    assert locomotion.hold_seconds_for_velocity_command(stop) == (
        locomotion.MIN_ACTIVE_HOLD_SECONDS
    )


def test_aerial_commands_satisfy_the_generated_aerial_model() -> None:
    payload = {
        "contract": locomotion.AERIAL_VELOCITY_COMMAND_CONTRACT,
        "linear_x": 0.5,
        "linear_y": 0.0,
        "linear_z": -0.2,
        "angular_z": 0.1,
        "duration_ms": 250,
        "origin": "ai_policy",
    }
    AerialVelocityCommandV1.model_validate(payload)
    command = locomotion.normalize_body_velocity_command(payload)
    assert command.vertical_control is True
    assert command.linear_z == -0.2

    stop = locomotion.stop_aerial_velocity_command()
    AerialVelocityCommandV1.model_validate(stop)
    assert locomotion.normalize_body_velocity_command(stop).duration_ms == 0


def test_required_field_tuples_match_the_models() -> None:
    """The tuples are what other trees check themselves against."""
    for required, model in (
        (
            locomotion.LOCOMOTION_VELOCITY_COMMAND_REQUIRED_FIELDS,
            LocomotionVelocityCommandV1,
        ),
        (
            locomotion.AERIAL_VELOCITY_COMMAND_REQUIRED_FIELDS,
            AerialVelocityCommandV1,
        ),
    ):
        required_by_model = {
            name for name, field in model.model_fields.items() if field.is_required()
        }
        assert set(required) == required_by_model


@pytest.mark.parametrize(
    "override",
    [
        {"duration_ms": 10},
        {"duration_ms": 30001},
        {"gait": "skip"},
        {"origin": "hacker"},
    ],
    ids=["duration-too-short", "duration-too-long", "unknown-gait", "unknown-origin"],
)
def test_the_normalizer_rejects_what_the_model_rejects(override: dict) -> None:
    payload = {
        "contract": locomotion.LOCOMOTION_VELOCITY_COMMAND_CONTRACT,
        "linear_x": 0.3,
        "linear_y": 0.0,
        "angular_z": 0.0,
        "duration_ms": 500,
        "gait": "walk",
        "origin": "teleop",
        **override,
    }
    with pytest.raises(ValidationError):
        LocomotionVelocityCommandV1.model_validate(payload)
    with pytest.raises(locomotion.LocomotionVelocityCommandError):
        locomotion.normalize_locomotion_velocity_command(payload)
