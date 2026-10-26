"""Simulation backend identity, scene bundles, runtime readiness and run fencing.

The behaviour that goes with the ``simulation.*`` contracts, defined once so the
backend, the Isaac plant and the Isaac cloud node import it instead of
re-deriving it. Standard library only, like :mod:`cyberwave_contracts.locomotion`: nothing
here reads the environment, touches the network or imports a simulator.

- **Backend identity** -- :data:`CANONICAL_BACKENDS`, :func:`normalize_backend`
  and :func:`normalize_execution_profile`. An omitted backend keeps the default;
  an explicit unknown one fails closed with ``simulation_backend_unsupported``
  and is never mapped to MuJoCo. :func:`physics_for_execution_profile` and
  :func:`execution_profile_for_physics` map an Isaac execution profile to the
  physics engine and device it runs and back.
- **Simulation parameters** -- :func:`normalize_timing` (the per-run
  ``timing`` block, per backend), :func:`normalize_isaac_physics` (the
  ``isaac_physics`` solver extension) and :func:`normalize_gravity`. Keys a
  backend cannot honour fail closed with ``simulation_parameter_unsupported``.
- **Hardware qualification** -- :func:`check_hardware_qualification` for
  ``simulation.hardware_qualification.v1``, the record a worker must hold
  before it receives Isaac workloads: a VRAM floor, with no GPU-model list
  and no driver pin.
- **Scene bundles** -- :func:`compute_bundle_digest`, :func:`hash_bundle_files`,
  :func:`is_confined_relative_path` and :func:`validate_bundle_manifest` for
  ``simulation.scene_bundle_manifest.v1``.
- **Runtime readiness** -- :func:`check_runtime_audit` for
  ``simulation.runtime_audit.v1``.
- **Run fencing** -- :class:`RunIdentity` and :func:`accept`, the reference rule
  every command ingress, sample egress and media path applies so that nothing
  from run A is accepted or presented as run B.
- **Secret scanning** -- :func:`find_secret_like`, shared with
  :mod:`cyberwave_contracts.trace`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# -- identifiers ---------------------------------------------------------------

BACKEND_MUJOCO = "mujoco"
BACKEND_MUJOCO_WARP = "mujoco_warp"
BACKEND_ISAAC = "isaac"

#: Every backend a caller may name. Order is presentation order, not preference.
CANONICAL_BACKENDS: tuple[str, ...] = (
    BACKEND_MUJOCO,
    BACKEND_MUJOCO_WARP,
    BACKEND_ISAAC,
)

#: Documented aliases only. A new alias is a product decision, not a convenience.
BACKEND_ALIASES: Mapping[str, str] = {"mjwarp": BACKEND_MUJOCO_WARP}

#: What an *omitted* backend means. An explicit unknown value never falls back.
DEFAULT_BACKEND = BACKEND_MUJOCO

EXECUTION_PROFILE_ISAAC_CPU = "isaac-cpu-physics"
EXECUTION_PROFILE_ISAAC_GPU = "isaac-gpu-physics"
EXECUTION_PROFILE_ISAAC_NEWTON = "isaac-newton-physics"
#: Every Isaac execution profile. All of them run on a qualified RT-core GPU
#: node (the renderer needs one whatever the physics); the profile only selects
#: the physics engine and the device it steps on.
EXECUTION_PROFILES: tuple[str, ...] = (
    EXECUTION_PROFILE_ISAAC_CPU,
    EXECUTION_PROFILE_ISAAC_GPU,
    EXECUTION_PROFILE_ISAAC_NEWTON,
)
DEFAULT_ISAAC_EXECUTION_PROFILE = EXECUTION_PROFILE_ISAAC_CPU
#: Profiles NVIDIA itself marks experimental. Selectable, labelled as such.
EXPERIMENTAL_EXECUTION_PROFILES: frozenset[str] = frozenset(
    {EXECUTION_PROFILE_ISAAC_NEWTON}
)

PHYSICS_ENGINE_PHYSX = "physx"
PHYSICS_ENGINE_NEWTON = "newton"
#: Physics engines an Isaac execution profile can select.
PHYSICS_ENGINES: tuple[str, ...] = (PHYSICS_ENGINE_PHYSX, PHYSICS_ENGINE_NEWTON)

PHYSICS_DEVICE_CPU = "cpu"
PHYSICS_DEVICE_GPU = "gpu"
PHYSICS_DEVICES: tuple[str, ...] = (PHYSICS_DEVICE_CPU, PHYSICS_DEVICE_GPU)


@dataclass(frozen=True)
class PhysicsSelection:
    """The physics engine an execution profile runs and the device it steps on."""

    engine: str
    device: str


#: Profile -> physics. The engine is part of the profile, so a Newton
#: attestation never stands in for a PhysX one and vice versa.
EXECUTION_PROFILE_PHYSICS: Mapping[str, PhysicsSelection] = {
    EXECUTION_PROFILE_ISAAC_CPU: PhysicsSelection(
        PHYSICS_ENGINE_PHYSX, PHYSICS_DEVICE_CPU
    ),
    EXECUTION_PROFILE_ISAAC_GPU: PhysicsSelection(
        PHYSICS_ENGINE_PHYSX, PHYSICS_DEVICE_GPU
    ),
    EXECUTION_PROFILE_ISAAC_NEWTON: PhysicsSelection(
        PHYSICS_ENGINE_NEWTON, PHYSICS_DEVICE_GPU
    ),
}

#: Cloud-node workload profile slugs per backend family. The MuJoCo profile was
#: ``cyberwave-sim`` before the rename; that slug is now deprovision-only.
CLOUD_NODE_PROFILE_MUJOCO = "mujoco-sim"
CLOUD_NODE_PROFILE_ISAAC = "isaac-sim"

#: Stable error codes. Wire values; never rename.
ERROR_BACKEND_UNSUPPORTED = "simulation_backend_unsupported"
ERROR_BACKEND_NOT_ENABLED = "simulation_backend_not_enabled"
ERROR_BACKEND_INCOMPATIBLE = "simulation_backend_incompatible"
ERROR_BACKEND_RUNTIME_MISMATCH = "simulation_backend_runtime_mismatch"
#: ``isaac`` was admitted but no worker holds a current passing hardware
#: qualification. Never answered by falling back to MuJoCo or a CPU node.
ERROR_BACKEND_CAPACITY_UNAVAILABLE = "simulation_backend_capacity_unavailable"
#: A simulation parameter the selected backend (or execution profile) has no
#: equivalent for. Refused, never silently dropped.
ERROR_PARAMETER_UNSUPPORTED = "simulation_parameter_unsupported"
#: A simulation parameter with the wrong type or outside its range.
ERROR_PARAMETER_INVALID = "simulation_parameter_invalid"

ERROR_CODES: tuple[str, ...] = (
    ERROR_BACKEND_UNSUPPORTED,
    ERROR_BACKEND_NOT_ENABLED,
    ERROR_BACKEND_INCOMPATIBLE,
    ERROR_BACKEND_RUNTIME_MISMATCH,
    ERROR_BACKEND_CAPACITY_UNAVAILABLE,
    ERROR_PARAMETER_UNSUPPORTED,
    ERROR_PARAMETER_INVALID,
)


class SimulationContractError(ValueError):
    """A simulation contract violation carrying a stable machine-readable ``code``."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class UnsupportedSimulationBackendError(SimulationContractError):
    """An explicit backend value that is neither canonical nor a documented alias."""

    def __init__(self, value: object) -> None:
        super().__init__(
            ERROR_BACKEND_UNSUPPORTED,
            f"Unsupported simulation backend {value!r}; expected one of "
            f"{', '.join(CANONICAL_BACKENDS)}.",
        )
        self.value = value


def normalize_backend(value: str | None) -> str:
    """Return the canonical backend for *value*, failing closed.

    ``None`` (omitted) returns :data:`DEFAULT_BACKEND`. Surrounding whitespace
    and letter case are ignored. Any other value -- including ``""`` and a
    misspelling -- raises :class:`UnsupportedSimulationBackendError` (a
    ``ValueError`` with ``code == "simulation_backend_unsupported"``); it is
    never mapped to MuJoCo.
    """
    if value is None:
        return DEFAULT_BACKEND
    if not isinstance(value, str):
        raise UnsupportedSimulationBackendError(value)
    key = value.strip().lower()
    if key in CANONICAL_BACKENDS:
        return key
    if key in BACKEND_ALIASES:
        return BACKEND_ALIASES[key]
    raise UnsupportedSimulationBackendError(value)


def normalize_execution_profile(backend: str, value: str | None) -> str | None:
    """Return the execution profile for an already-normalised *backend*.

    ``isaac`` defaults to :data:`DEFAULT_ISAAC_EXECUTION_PROFILE`. Every other
    backend has no execution profile; naming one for them is an error rather
    than something silently dropped.
    """
    if backend not in CANONICAL_BACKENDS:
        raise UnsupportedSimulationBackendError(backend)
    if backend != BACKEND_ISAAC:
        if value is None:
            return None
        raise SimulationContractError(
            ERROR_BACKEND_UNSUPPORTED,
            f"execution_profile {value!r} is only valid with backend 'isaac'.",
        )
    if value is None:
        return DEFAULT_ISAAC_EXECUTION_PROFILE
    if isinstance(value, str) and value.strip().lower() in EXECUTION_PROFILES:
        return value.strip().lower()
    raise SimulationContractError(
        ERROR_BACKEND_UNSUPPORTED,
        f"Unsupported execution_profile {value!r}; expected one of "
        f"{', '.join(EXECUTION_PROFILES)}.",
    )


def physics_for_execution_profile(profile: str) -> PhysicsSelection:
    """The physics engine and device an Isaac execution *profile* runs.

    Raises ``simulation_backend_unsupported`` for anything that is not an
    Isaac execution profile (normalise it first with
    :func:`normalize_execution_profile`).
    """
    selection = EXECUTION_PROFILE_PHYSICS.get(profile)
    if selection is None:
        raise SimulationContractError(
            ERROR_BACKEND_UNSUPPORTED,
            f"Unsupported execution_profile {profile!r}; expected one of "
            f"{', '.join(EXECUTION_PROFILES)}.",
        )
    return selection


def execution_profile_for_physics(engine: str | None, device: str | None) -> str | None:
    """The Isaac execution profile a runtime running *engine* on *device* is in.

    The inverse of :func:`physics_for_execution_profile`, for a plant reporting
    what it actually runs. ``None`` when no profile matches (for example
    Newton on the CPU) -- a runtime in no known profile is a mismatch, never
    rounded to the nearest one.
    """
    for profile, selection in EXECUTION_PROFILE_PHYSICS.items():
        if selection.engine == engine and selection.device == device:
            return profile
    return None


# -- simulation parameters ----------------------------------------------------------
#
# One parameter surface for every backend: the per-run ``timing`` block of the
# start request (what the Sim tab's Advanced settings and the SDK send) and the
# environment's authored physics. MuJoCo reads solver settings from the MJCF
# (``Physics.extensions["mjcf_option"]``); Isaac reads its PhysX equivalents
# from ``Physics.extensions["isaac_physics"]``. Each backend accepts only what
# it can honour -- a key it has no equivalent for is refused with
# ``simulation_parameter_unsupported``, never dropped.

TIMING_DT = "dt"
TIMING_REALTIME = "realtime"
TIMING_SIMULATION_SPEED = "simulation_speed"
TIMING_STREAM_FREQUENCY_HZ = "stream_frequency_hz"
TIMING_RANGE_STREAM_FREQUENCY_HZ = "range_stream_frequency_hz"
TIMING_RANGE_SELF_HIT_FALLBACK = "range_self_hit_fallback"
#: MuJoCo only: render colour cameras at the size their sensor declares instead
#: of fitting them into the plant's ``CAMERA_MAX_WIDTH x CAMERA_MAX_HEIGHT`` box
#: (640x480). Off by default, because frames are software-rendered and a large
#: camera costs real-time factor; only ``true`` is ever sent.
TIMING_FULL_CAMERA_RESOLUTION = "full_camera_resolution"
#: Isaac only: simulated seconds between rendered frames. Cameras render on
#: one shared clock at ``1 / rendering_dt`` (a camera authored slower keeps
#: its own rate), decoupled from the physics ``dt`` -- the plant's
#: counterpart of Isaac's ``SimulationContext(rendering_dt=...)``.
TIMING_RENDERING_DT = "rendering_dt"

#: ``Physics.extensions`` key carrying Isaac solver settings (the Isaac
#: counterpart of ``mjcf_option``).
ISAAC_PHYSICS_EXTENSION_KEY = "isaac_physics"
ISAAC_SOLVER_POSITION_ITERATIONS = "solver_position_iterations"
ISAAC_SOLVER_VELOCITY_ITERATIONS = "solver_velocity_iterations"
ISAAC_SUBSTEPS = "substeps"

#: Every per-run timing field, in wire order. The solver fields are the
#: per-run override of the environment's ``isaac_physics`` extension.
TIMING_FIELDS: tuple[str, ...] = (
    TIMING_DT,
    TIMING_REALTIME,
    TIMING_SIMULATION_SPEED,
    TIMING_STREAM_FREQUENCY_HZ,
    TIMING_RANGE_STREAM_FREQUENCY_HZ,
    TIMING_RANGE_SELF_HIT_FALLBACK,
    TIMING_FULL_CAMERA_RESOLUTION,
    TIMING_RENDERING_DT,
    ISAAC_SUBSTEPS,
    ISAAC_SOLVER_POSITION_ITERATIONS,
    ISAAC_SOLVER_VELOCITY_ITERATIONS,
)

#: Inclusive numeric bounds; ``None`` is an open side. ``simulation_speed`` is
#: strictly positive (checked separately). The backend's
#: ``SimulationTimingOptionsSchema`` imports the first three for its 422 checks;
#: ``rendering_dt`` is bounded here only.
TIMING_DT_RANGE: tuple[float, float] = (1e-6, 0.1)
TIMING_STREAM_FREQUENCY_RANGE: tuple[float, float] = (0.1, 1000.0)
#: ``0`` is meaningful: publish range on every state-stream pass.
TIMING_RANGE_STREAM_FREQUENCY_RANGE: tuple[float, float] = (0.0, 1000.0)
#: 1 ms .. 1 s between rendered frames (1000 Hz .. 1 Hz).
TIMING_RENDERING_DT_RANGE: tuple[float, float] = (1e-3, 1.0)

#: Timing fields only the Isaac plant honours: PhysX sub-stepping and solver
#: iterations, and a render clock decoupled from physics. MuJoCo reads its
#: solver settings from the MJCF and renders per camera.
ISAAC_ONLY_TIMING_FIELDS: frozenset[str] = frozenset(
    {
        TIMING_RENDERING_DT,
        ISAAC_SUBSTEPS,
        ISAAC_SOLVER_POSITION_ITERATIONS,
        ISAAC_SOLVER_VELOCITY_ITERATIONS,
    }
)

#: The timing fields each backend honours. Isaac has no range "self-hit
#: fallback": its ray sensors are RTX/PhysX scene queries that already exclude
#: the emitting body, so the MuJoCo re-cast switch has no meaning there. Nor does
#: it have the colour-camera size cap: Isaac renders each camera on its own
#: clock at the size the sensor declares.
TIMING_FIELDS_BY_BACKEND: Mapping[str, frozenset[str]] = {
    BACKEND_MUJOCO: frozenset(TIMING_FIELDS) - ISAAC_ONLY_TIMING_FIELDS,
    BACKEND_MUJOCO_WARP: frozenset(TIMING_FIELDS) - ISAAC_ONLY_TIMING_FIELDS,
    BACKEND_ISAAC: frozenset(TIMING_FIELDS)
    - {TIMING_RANGE_SELF_HIT_FALLBACK, TIMING_FULL_CAMERA_RESOLUTION},
}

#: Field -> inclusive integer bounds. The iteration bounds are PhysX's own
#: (``PhysxSceneAPI`` min/max iteration counts are uint, max 255; a position
#: pass of 0 is not a solve). ``substeps`` splits each plant step into equal
#: physics sub-steps with commands re-applied on each; 64 caps the cost.
ISAAC_PHYSICS_FIELDS: Mapping[str, tuple[int, int]] = {
    ISAAC_SOLVER_POSITION_ITERATIONS: (1, 255),
    ISAAC_SOLVER_VELOCITY_ITERATIONS: (0, 255),
    ISAAC_SUBSTEPS: (1, 64),
}

#: Isaac physics fields an execution profile cannot honour. Newton is not a
#: PhysX TGS/PGS solver: the PhysX iteration counts have no equivalent there.
ISAAC_PHYSICS_UNSUPPORTED_BY_PROFILE: Mapping[str, frozenset[str]] = {
    EXECUTION_PROFILE_ISAAC_NEWTON: frozenset(
        {ISAAC_SOLVER_POSITION_ITERATIONS, ISAAC_SOLVER_VELOCITY_ITERATIONS}
    ),
}


def _number(field_name: str, value: object) -> float:
    # ``bool`` is an ``int`` subclass; ``True`` is not a timestep.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationContractError(
            ERROR_PARAMETER_INVALID, f"{field_name} must be a number, got {value!r}."
        )
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise SimulationContractError(
            ERROR_PARAMETER_INVALID, f"{field_name} must be finite."
        )
    return number


def _bounded(field_name: str, value: object, bounds: tuple[float, float]) -> float:
    number = _number(field_name, value)
    low, high = bounds
    if not low <= number <= high:
        raise SimulationContractError(
            ERROR_PARAMETER_INVALID,
            f"{field_name} must be between {low:g} and {high:g}, got {number:g}.",
        )
    return number


def normalize_timing(
    backend: str,
    timing: Mapping[str, Any] | None,
    *,
    execution_profile: str | None = None,
) -> dict[str, Any]:
    """Validate a per-run ``timing`` block for *backend*; return it normalised.

    ``None`` values mean "not set" and are dropped. A key the backend does not
    honour raises ``simulation_parameter_unsupported``, as does a solver
    setting the *execution_profile*'s engine has no equivalent for (Newton
    iterations); a wrong type or a value out of range raises
    ``simulation_parameter_invalid``. Numbers come back as ``float`` except the
    Isaac solver fields (``int``); nothing is clamped.
    """
    canonical = normalize_backend(backend)
    if timing is None:
        return {}
    if not isinstance(timing, Mapping):
        raise SimulationContractError(
            ERROR_PARAMETER_INVALID, "timing must be an object."
        )
    allowed = TIMING_FIELDS_BY_BACKEND[canonical]
    unknown = sorted(str(k) for k in timing if k not in TIMING_FIELDS)
    if unknown:
        raise SimulationContractError(
            ERROR_PARAMETER_UNSUPPORTED,
            f"Unknown timing parameter(s) {', '.join(unknown)}; expected "
            f"{', '.join(TIMING_FIELDS)}.",
        )
    unsupported = sorted(
        k for k, v in timing.items() if v is not None and k not in allowed
    )
    if unsupported:
        raise SimulationContractError(
            ERROR_PARAMETER_UNSUPPORTED,
            f"timing parameter(s) {', '.join(unsupported)} are not supported by "
            f"backend {canonical!r}.",
        )
    out: dict[str, Any] = normalize_isaac_physics(
        {k: timing.get(k) for k in ISAAC_PHYSICS_FIELDS if k in timing},
        execution_profile=execution_profile,
    )
    for key in TIMING_FIELDS:
        value = timing.get(key)
        if value is None or key in ISAAC_PHYSICS_FIELDS:
            continue
        if key in (
            TIMING_REALTIME,
            TIMING_RANGE_SELF_HIT_FALLBACK,
            TIMING_FULL_CAMERA_RESOLUTION,
        ):
            if not isinstance(value, bool):
                raise SimulationContractError(
                    ERROR_PARAMETER_INVALID, f"{key} must be true or false."
                )
            out[key] = value
        elif key == TIMING_DT:
            out[key] = _bounded(key, value, TIMING_DT_RANGE)
        elif key == TIMING_SIMULATION_SPEED:
            speed = _number(key, value)
            if speed <= 0:
                raise SimulationContractError(
                    ERROR_PARAMETER_INVALID, f"{key} must be positive."
                )
            out[key] = speed
        elif key == TIMING_STREAM_FREQUENCY_HZ:
            out[key] = _bounded(key, value, TIMING_STREAM_FREQUENCY_RANGE)
        elif key == TIMING_RENDERING_DT:
            out[key] = _bounded(key, value, TIMING_RENDERING_DT_RANGE)
        else:
            out[key] = _bounded(key, value, TIMING_RANGE_STREAM_FREQUENCY_RANGE)
    return out


def normalize_isaac_physics(
    options: Mapping[str, Any] | None, *, execution_profile: str | None = None
) -> dict[str, int]:
    """Validate ``Physics.extensions["isaac_physics"]``; return it normalised.

    Unknown keys raise ``simulation_parameter_unsupported``, as do solver
    iteration counts under an *execution_profile* whose engine has no such
    setting (Newton). An *execution_profile* that is not an Isaac profile
    raises ``simulation_backend_unsupported``. Non-integers and out-of-range
    values raise ``simulation_parameter_invalid``. ``None`` values are dropped.
    """
    if options is None:
        return {}
    if not isinstance(options, Mapping):
        raise SimulationContractError(
            ERROR_PARAMETER_INVALID, f"{ISAAC_PHYSICS_EXTENSION_KEY} must be an object."
        )
    unknown = sorted(str(k) for k in options if k not in ISAAC_PHYSICS_FIELDS)
    if unknown:
        raise SimulationContractError(
            ERROR_PARAMETER_UNSUPPORTED,
            f"Unknown {ISAAC_PHYSICS_EXTENSION_KEY} parameter(s) {', '.join(unknown)}; "
            f"expected {', '.join(ISAAC_PHYSICS_FIELDS)}.",
        )
    if execution_profile is not None:
        # An unknown profile fails closed rather than refusing nothing. No case
        # or whitespace folding here: normalise first with
        # :func:`normalize_execution_profile`.
        if execution_profile not in EXECUTION_PROFILE_PHYSICS:
            raise SimulationContractError(
                ERROR_BACKEND_UNSUPPORTED,
                f"Unsupported execution_profile {execution_profile!r}; expected "
                f"one of {', '.join(EXECUTION_PROFILES)}.",
            )
        refused = ISAAC_PHYSICS_UNSUPPORTED_BY_PROFILE.get(
            execution_profile, frozenset()
        )
        named = sorted(k for k, v in options.items() if v is not None and k in refused)
        if named:
            raise SimulationContractError(
                ERROR_PARAMETER_UNSUPPORTED,
                f"{', '.join(named)} are not supported by execution_profile "
                f"{execution_profile!r}.",
            )
    out: dict[str, int] = {}
    for key, (low, high) in ISAAC_PHYSICS_FIELDS.items():
        value = options.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise SimulationContractError(
                ERROR_PARAMETER_INVALID, f"{key} must be an integer, got {value!r}."
            )
        if not low <= value <= high:
            raise SimulationContractError(
                ERROR_PARAMETER_INVALID,
                f"{key} must be between {low} and {high}, got {value}.",
            )
        out[key] = value
    return out


def normalize_gravity(value: object) -> tuple[float, float, float]:
    """A gravity vector: exactly three finite numbers (m/s^2, world frame)."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise SimulationContractError(
            ERROR_PARAMETER_INVALID, "gravity must be a list of three numbers."
        )
    items = list(value)
    if len(items) != 3:
        raise SimulationContractError(
            ERROR_PARAMETER_INVALID, "gravity must be a list of three numbers."
        )
    x, y, z = (_number("gravity", item) for item in items)
    return (x, y, z)


# -- secret scanning -------------------------------------------------------------

#: Keys whose value is a credential whatever it looks like. Compared after
#: lower-casing and mapping '-' to '_'.
_SECRET_KEYS = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "auth_token",
        "session_token",
        "authorization",
        "password",
        "passwd",
        "secret",
        "client_secret",
        "api_key",
        "apikey",
        "x_api_key",
        "cookie",
        "set_cookie",
        "credential",
        "credentials",
        "signature",
        "private_key",
        "bearer",
        "x_goog_signature",
        "x_amz_signature",
        "x_amz_security_token",
        "x_goog_credential",
    }
)
_SECRET_KEY_SUFFIXES = ("_token", "_secret", "_password", "_api_key", "_credentials")

#: Value fragments that mark a signed URL, a bearer header or a JWT.
_SECRET_VALUE = re.compile(
    r"(?i)("
    r"[?&](x-goog-signature|x-goog-credential|x-amz-signature|x-amz-credential|"
    r"x-amz-security-token|signature|sig|token|access_token|auth|key)="
    r"|^\s*bearer\s+\S"
    r"|\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\."
    r"|[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"
    r")"
)

_URL = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://")


def _is_secret_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return normalized in _SECRET_KEYS or normalized.endswith(_SECRET_KEY_SUFFIXES)


def find_secret_like(
    value: Any, *, forbid_urls: bool = False, _path: str = "$"
) -> list[str]:
    """Return a description of every credential-like key or value in *value*.

    Walks mappings and sequences. Flags credential keys (``token``,
    ``authorization``, ``*_secret`` ...), signed-URL query parameters
    (``X-Goog-Signature=``, ``Signature=``, ``token=`` ...), bearer headers,
    JWTs and URLs with embedded user info. With ``forbid_urls`` any
    ``scheme://`` string is flagged too -- the bundle manifest carries no URLs.
    An empty list means nothing was found; it is not proof of absence.
    """
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{_path}.{key}"
            if isinstance(key, str) and _is_secret_key(key):
                found.append(f"{path}: credential-like key")
                continue
            found.extend(find_secret_like(item, forbid_urls=forbid_urls, _path=path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(
                find_secret_like(
                    item, forbid_urls=forbid_urls, _path=f"{_path}[{index}]"
                )
            )
    elif isinstance(value, str):
        if _SECRET_VALUE.search(value):
            found.append(f"{_path}: credential-like value")
        elif forbid_urls and _URL.search(value):
            found.append(f"{_path}: URL not allowed")
    return found


# -- scene bundles --------------------------------------------------------------

SHA256_HEX = re.compile(r"[0-9a-f]{64}")
SHA256_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_SEGMENT = re.compile(r"\.?[A-Za-z0-9_+@=-][A-Za-z0-9_.+@=-]*")
_PRIM_PATH = re.compile(r"(/[A-Za-z_][A-Za-z0-9_]*)+")

#: Name of the manifest file at the bundle root. Not listed in its own files.
BUNDLE_MANIFEST_FILENAME = "manifest.json"


def is_confined_relative_path(path: object) -> bool:
    """True when *path* is a relative POSIX path that cannot leave the bundle root.

    Rejects a leading ``/``, any ``.`` or ``..`` segment, empty segments, a
    scheme or drive (``:`` is not allowed at all), backslashes and whitespace.
    Mirrors the ``pattern`` in the manifest schema; uses ``fullmatch`` so a
    trailing newline cannot slip past ``$``.
    """
    if not isinstance(path, str) or not path:
        return False
    return all(_SEGMENT.fullmatch(segment) for segment in path.split("/"))


def validate_bundle_path(path: object) -> str:
    """Return *path* if confined, else raise ``ValueError``."""
    if not is_confined_relative_path(path):
        raise ValueError(f"bundle path {path!r} is not a confined relative path")
    assert isinstance(path, str)
    return path


def compute_bundle_digest(files: Iterable[Mapping[str, Any]]) -> str:
    """``sha256:<hex>`` over the canonical form of a bundle's file list.

    Each entry needs ``path``, ``sha256`` and ``size``. The canonical form sorts
    entries by the UTF-8 bytes of ``path`` and hashes one line per file::

        <sha256 hex> <size> <path>\\n

    Input order therefore does not matter, while any change to a path, a byte
    of content or a size does. Invalid paths, hashes, sizes and duplicate paths
    raise ``ValueError`` instead of producing a digest for an ambiguous bundle.
    """
    lines: list[tuple[bytes, bytes]] = []
    seen: set[str] = set()
    for entry in files:
        path = validate_bundle_path(entry.get("path"))
        sha = entry.get("sha256")
        size = entry.get("size")
        if not isinstance(sha, str) or not SHA256_HEX.fullmatch(sha):
            raise ValueError(f"{path}: sha256 must be 64 lowercase hex characters")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f"{path}: size must be a non-negative integer")
        if path in seen:
            raise ValueError(f"duplicate bundle path {path!r}")
        seen.add(path)
        encoded = path.encode("utf-8")
        lines.append((encoded, b"%s %d %s\n" % (sha.encode("ascii"), size, encoded)))
    digest = hashlib.sha256()
    for _, line in sorted(lines):
        digest.update(line)
    return f"sha256:{digest.hexdigest()}"


def hash_bundle_files(
    root: str | os.PathLike[str],
    *,
    exclude: Iterable[str] = (BUNDLE_MANIFEST_FILENAME,),
) -> list[dict[str, Any]]:
    """Build the ``files`` list for the bundle directory *root*.

    Every regular file below *root* is hashed, except the paths in *exclude*
    (the manifest by default). Symlinks are refused rather than followed -- a
    link is how a bundle reaches outside itself -- as is any file whose relative
    path is not confined. Sorted by path.
    """
    base = Path(root)
    excluded = set(exclude)
    entries: list[dict[str, Any]] = []
    for directory, dirnames, filenames in os.walk(base, followlinks=False):
        here = Path(directory)
        for name in sorted(dirnames):
            if (here / name).is_symlink():
                raise ValueError(
                    f"symlinked directory in bundle: {(here / name).relative_to(base)}"
                )
        for name in sorted(filenames):
            full = here / name
            relative = full.relative_to(base).as_posix()
            if relative in excluded:
                continue
            if full.is_symlink() or not full.is_file():
                raise ValueError(f"bundle entry is not a regular file: {relative}")
            validate_bundle_path(relative)
            digest = hashlib.sha256()
            with full.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
            entries.append(
                {
                    "path": relative,
                    "sha256": digest.hexdigest(),
                    "size": full.stat().st_size,
                }
            )
    entries.sort(key=lambda entry: entry["path"].encode("utf-8"))
    return entries


def _duplicates(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    dupes: list[Any] = []
    for value in values:
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    return dupes


def validate_bundle_manifest(manifest: Mapping[str, Any]) -> list[str]:
    """Problems with a ``simulation.scene_bundle_manifest.v1`` beyond its schema.

    Checks what a JSON Schema cannot: every path confined, no duplicate or
    case-colliding paths, ``root_layer`` listed in ``files``, ``bundle_digest``
    equal to :func:`compute_bundle_digest` of ``files``, unique twin/sensor/
    joint identities and prim paths, and no URL or credential anywhere. Empty
    when the manifest is acceptable. Does not read the bundle files; pair it
    with :func:`hash_bundle_files` to verify contents on disk.
    """
    problems: list[str] = []
    if manifest.get("contract") != "simulation.scene_bundle_manifest.v1":
        problems.append("contract: not simulation.scene_bundle_manifest.v1")

    files = manifest.get("files")
    if not isinstance(files, list):
        return [*problems, "files: missing or not a list"]
    paths: list[str] = []
    for index, entry in enumerate(files):
        if not isinstance(entry, Mapping):
            problems.append(f"files[{index}]: not an object")
            continue
        path = entry.get("path")
        if not is_confined_relative_path(path):
            problems.append(
                f"files[{index}].path {path!r}: not a confined relative path"
            )
        else:
            paths.append(str(path))
    for dupe in _duplicates(paths):
        problems.append(f"files: duplicate path {dupe!r}")
    for dupe in _duplicates(p.casefold() for p in paths):
        problems.append(f"files: paths collide case-insensitively ({dupe!r})")

    root_layer = manifest.get("root_layer")
    if not is_confined_relative_path(root_layer):
        problems.append(f"root_layer {root_layer!r}: not a confined relative path")
    elif root_layer not in paths:
        problems.append(f"root_layer {root_layer!r}: not listed in files")

    try:
        expected = compute_bundle_digest(files)
    except ValueError as exc:
        problems.append(f"files: cannot compute bundle digest ({exc})")
    else:
        if manifest.get("bundle_digest") != expected:
            problems.append(
                f"bundle_digest {manifest.get('bundle_digest')!r} does not match the file list ({expected})"
            )

    identity = manifest.get("identity_map") or {}
    if isinstance(identity, Mapping):
        checks = {
            "twins": lambda e: e.get("twin_uuid"),
            "links": lambda e: (e.get("twin_uuid"), e.get("link")),
            "joints": lambda e: (e.get("twin_uuid"), e.get("joint")),
            "sensors": lambda e: e.get("sensor_id"),
            "cameras": lambda e: e.get("camera_id"),
        }
        prim_paths: list[str] = []
        for section, key in checks.items():
            entries = [e for e in identity.get(section) or [] if isinstance(e, Mapping)]
            for dupe in _duplicates(key(e) for e in entries):
                problems.append(f"identity_map.{section}: duplicate identity {dupe!r}")
            for e in entries:
                usd_path = e.get("usd_path")
                if not isinstance(usd_path, str) or not _PRIM_PATH.fullmatch(usd_path):
                    problems.append(
                        f"identity_map.{section}: invalid prim path {usd_path!r}"
                    )
                elif section != "cameras":
                    # A camera may share its prim with the sensor it renders.
                    prim_paths.append(usd_path)
        for dupe in _duplicates(prim_paths):
            problems.append(
                f"identity_map: prim path {dupe!r} mapped to more than one identity"
            )

    problems.extend(find_secret_like(manifest, forbid_urls=True))
    return problems


# -- runtime readiness ------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeAuditCheck:
    """Verdict of :func:`check_runtime_audit`. Truthy only when ready."""

    ready: bool
    mismatches: tuple[dict[str, str | None], ...] = ()

    def __bool__(self) -> bool:
        return self.ready

    @property
    def error_code(self) -> str | None:
        """The stable code of the mismatches, if any carries one.

        Read off the mismatches themselves rather than re-derived from a field
        allowlist, so a field added to :func:`check_runtime_audit` cannot report
        a code the verdict then drops. A runtime mismatch outranks the rest.
        """
        codes = [m["code"] for m in self.mismatches if m["code"]]
        if ERROR_BACKEND_RUNTIME_MISMATCH in codes:
            return ERROR_BACKEND_RUNTIME_MISMATCH
        return codes[0] if codes else None


def check_runtime_audit(
    audit: Mapping[str, Any],
    *,
    requested_backend: str | None = None,
    requested_execution_profile: str | None = None,
    expected_bundle_digest: str | None = None,
    expected_image_digest: str | None = None,
    expected_feature_profile_id: str | None = None,
    required_capabilities: Iterable[str] | None = None,
    verify_physics: bool = True,
) -> RuntimeAuditCheck:
    """Decide whether a ``simulation.runtime_audit.v1`` describes a ready runtime.

    Ready only if: the reported backend equals the requested backend (the
    ``requested_backend`` argument, else the audit's own ``requested_backend``);
    the execution profile matches the requested one (the argument, else the
    audit's ``requested_execution_profile``, else the backend default); every
    expected digest/feature profile given matches; and every required
    capability is ``"ok"``. ``required_capabilities`` defaults to every
    capability the audit lists, and an audit listing none is not ready. The
    audit's own ``ready`` flag is never trusted -- a runtime claiming ready
    while a check fails is reported as a mismatch.

    With ``verify_physics`` an Isaac audit's ``physics.engine`` and
    ``physics.device`` must also be the ones the expected execution profile
    selects (:func:`physics_for_execution_profile`), so a plant cannot run
    PhysX while claiming the Newton profile. On by
    default; only a test runtime that reports a stand-in engine passes
    ``verify_physics=False``.
    """
    mismatches: list[dict[str, str | None]] = []

    def mismatch(
        name: str, expected: Any, reported: Any, code: str | None = None
    ) -> None:
        mismatches.append(
            {
                "field": name,
                "expected": None if expected is None else str(expected),
                "reported": None if reported is None else str(reported),
                "code": code,
            }
        )

    wanted = (
        requested_backend
        if requested_backend is not None
        else audit.get("requested_backend")
    )
    try:
        wanted_backend = normalize_backend(wanted)
    except SimulationContractError:
        mismatch(
            "requested_backend",
            "|".join(CANONICAL_BACKENDS),
            wanted,
            ERROR_BACKEND_UNSUPPORTED,
        )
        wanted_backend = None
    if wanted is None:
        mismatch(
            "requested_backend", "explicit backend", None, ERROR_BACKEND_UNSUPPORTED
        )
    reported = audit.get("reported_backend")
    if wanted_backend is not None and reported != wanted_backend:
        mismatch(
            "reported_backend", wanted_backend, reported, ERROR_BACKEND_RUNTIME_MISMATCH
        )
    if audit.get("requested_backend") is not None and wanted_backend is not None:
        if audit.get("requested_backend") != wanted_backend:
            mismatch(
                "requested_backend",
                wanted_backend,
                audit.get("requested_backend"),
                ERROR_BACKEND_RUNTIME_MISMATCH,
            )

    if wanted_backend is not None:
        wanted_profile = (
            requested_execution_profile
            if requested_execution_profile is not None
            else audit.get("requested_execution_profile")
        )
        try:
            expected_profile = normalize_execution_profile(
                wanted_backend, wanted_profile
            )
        except SimulationContractError:
            mismatch(
                "requested_execution_profile",
                "|".join(EXECUTION_PROFILES),
                wanted_profile,
                ERROR_BACKEND_UNSUPPORTED,
            )
        else:
            if audit.get("execution_profile") != expected_profile:
                mismatch(
                    "execution_profile",
                    expected_profile,
                    audit.get("execution_profile"),
                    ERROR_BACKEND_RUNTIME_MISMATCH,
                )
            if verify_physics and expected_profile is not None:
                physics = audit.get("physics")
                physics = physics if isinstance(physics, Mapping) else {}
                selection = EXECUTION_PROFILE_PHYSICS[expected_profile]
                for name, expected_value in (
                    ("engine", selection.engine),
                    ("device", selection.device),
                ):
                    if physics.get(name) != expected_value:
                        mismatch(
                            f"physics.{name}",
                            expected_value,
                            physics.get(name),
                            ERROR_BACKEND_RUNTIME_MISMATCH,
                        )

    for name, expected in (
        ("bundle_digest", expected_bundle_digest),
        ("image_digest", expected_image_digest),
        ("feature_profile_id", expected_feature_profile_id),
    ):
        if expected is not None and audit.get(name) != expected:
            mismatch(name, expected, audit.get(name), ERROR_BACKEND_RUNTIME_MISMATCH)
    if wanted_backend == BACKEND_ISAAC and audit.get("bundle_digest") is None:
        mismatch(
            "bundle_digest",
            "a loaded scene bundle",
            None,
            ERROR_BACKEND_RUNTIME_MISMATCH,
        )

    capabilities = audit.get("capabilities")
    capabilities = capabilities if isinstance(capabilities, Mapping) else {}
    required = (
        list(capabilities)
        if required_capabilities is None
        else list(required_capabilities)
    )
    if not required:
        mismatch("capabilities", "at least one required capability", None)
    for name in required:
        status = capabilities.get(name)
        if status != "ok":
            mismatch(
                f"capabilities.{name}",
                "ok",
                status if status is not None else "missing",
            )

    return RuntimeAuditCheck(ready=not mismatches, mismatches=tuple(mismatches))


# -- hardware qualification ------------------------------------------------------
#
# The rule is a contract floor only: a VRAM minimum, with no GPU-model list and
# no driver pin.

HARDWARE_QUALIFICATION_CONTRACT = "simulation.hardware_qualification.v1"
#: Where a worker's latest qualification record lives in its node metadata
#: (``CloudNodeInstance.metadata[HARDWARE_QUALIFICATION_METADATA_KEY]``).
HARDWARE_QUALIFICATION_METADATA_KEY = "hardware_qualification"
HARDWARE_QUALIFICATION_PASS = "pass"
HARDWARE_QUALIFICATION_FAIL = "fail"
#: NVIDIA's published VRAM floor for Isaac Sim is a 16 GB card, on the GPU
#: assigned to the workload. The driver reports a 16 GB card's total below
#: 16384 MiB (RTX 5070 Ti: 16303 MiB, RTX 4080: 16376 MiB), so the floor is
#: 15.5 GiB: every 16 GB card passes, a 12 GB one (about 12282 MiB) does not.
MIN_ISAAC_VRAM_MIB = 15872
#: A passing probe older than this is stale; the worker must re-probe.
DEFAULT_HARDWARE_QUALIFICATION_MAX_AGE_S = 24 * 60 * 60
#: Tolerated clock skew for a ``checked_at`` that lies in the future.
_QUALIFICATION_CLOCK_SKEW_S = 300


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


#: ``mode`` of a record produced by the node's GPU-less CI test mode.
FAKE_RUNTIME_MODE = "ci-fake-runtime"


def check_hardware_qualification(
    record: object,
    *,
    now: datetime,
    max_age_s: float = DEFAULT_HARDWARE_QUALIFICATION_MAX_AGE_S,
    expected_image_digest: str | None = None,
    execution_profile: str | None = None,
    allow_provisional: bool = False,
    allow_fake_runtime: bool = False,
) -> list[str]:
    """Why *record* does not qualify a worker for Isaac; empty when it does.

    *record* is a ``simulation.hardware_qualification.v1`` body. Fails closed:
    a missing record, a ``status`` other than ``"pass"``, no RT cores, less than
    :data:`MIN_ISAAC_VRAM_MIB` (a 16 GB card), a missing driver/probe version/image digest, an
    unparseable or naive ``checked_at``, or one older than *max_age_s* each
    disqualify. There is no GPU-model list and no driver pin: any GPU with RT
    cores that meets the VRAM floor qualifies, on the driver it probed with. When
    *expected_image_digest* is given, the probed image must match it exactly.
    When the record lists the ``execution_profiles`` its runtime probe stepped,
    *execution_profile* must be one of them. A ``provisional`` record (a
    development-mode probe that waived production checks) qualifies only with
    *allow_provisional*. A ``fake_runtime`` record (the GPU-less CI test mode,
    whose RT cores, VRAM and driver are placeholders, not measurements) is a
    separate decision and qualifies only with *allow_fake_runtime*, so admitting
    a waived development-mode probe never also admits a GPU-less one.
    """
    if not isinstance(record, Mapping):
        return ["no hardware qualification record"]
    reasons: list[str] = []
    fake = record.get("fake_runtime") is True or record.get("mode") == FAKE_RUNTIME_MODE
    if fake and not allow_fake_runtime:
        reasons.append("record is from a GPU-less test-mode probe")
    if record.get("provisional") is True and not allow_provisional:
        reasons.append("record is provisional (development-mode probe)")
    if record.get("contract") != HARDWARE_QUALIFICATION_CONTRACT:
        reasons.append(
            f"contract is {record.get('contract')!r}, not "
            f"{HARDWARE_QUALIFICATION_CONTRACT!r}"
        )
    if record.get("status") != HARDWARE_QUALIFICATION_PASS:
        reasons.append(f"qualification status is {record.get('status')!r}")
    if record.get("rt_cores") is not True:
        reasons.append("GPU has no RT cores")
    vram = record.get("vram_mib")
    if isinstance(vram, bool) or not isinstance(vram, int) or vram < MIN_ISAAC_VRAM_MIB:
        reasons.append(f"VRAM {vram!r} MiB is below {MIN_ISAAC_VRAM_MIB} MiB")
    for name in ("gpu_model", "driver", "probe_version"):
        if not isinstance(record.get(name), str) or not record.get(name):
            reasons.append(f"{name} missing")
    image_digest = record.get("image_digest")
    if not isinstance(image_digest, str) or not SHA256_DIGEST.fullmatch(image_digest):
        reasons.append("image_digest missing or not a sha256 digest")
    elif expected_image_digest is not None and image_digest != expected_image_digest:
        reasons.append(
            f"probed image {image_digest} is not the pinned {expected_image_digest}"
        )
    checked_at = _parse_utc(record.get("checked_at"))
    if checked_at is None:
        reasons.append("checked_at missing or not a timezone-aware ISO 8601 time")
    else:
        current = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        age = (current - checked_at).total_seconds()
        if age > max_age_s:
            reasons.append(f"qualification is stale ({int(age)}s old)")
        elif age < -_QUALIFICATION_CLOCK_SKEW_S:
            reasons.append("checked_at is in the future")
    probed = record.get("execution_profiles")
    if execution_profile is not None and probed is not None:
        if not isinstance(probed, list) or execution_profile not in probed:
            reasons.append(f"execution profile {execution_profile!r} was not probed")
    return reasons


def attestation_key_digest(key: Mapping[str, Any]) -> str:
    """``sha256:<hex>`` of the canonical JSON of an attestation ``key``.

    Canonical: keys sorted, no insignificant whitespace, UTF-8, no NaN. Two keys
    that differ in any field -- a runtime, an extension lock, a test-suite
    revision -- digest differently, which is how invalidation finds stale
    attestations.
    """
    encoded = json.dumps(
        key, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


# -- run fencing ------------------------------------------------------------------


@dataclass(frozen=True)
class RunIdentity:
    """The execution identity a plant is currently running under.

    ``run_id`` changes on every start. ``stream_instance_id`` is the media/stream
    identity of the run. ``reset_epoch`` increments on every reset within the
    run, so output acquired before a reset is distinguishable from output after.
    """

    run_id: str
    stream_instance_id: str | None = None
    workload_uuid: str | None = None
    reset_epoch: int = 0

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunIdentity:
        return cls(
            run_id=str(value["run_id"]),
            stream_instance_id=value.get("stream_instance_id"),
            workload_uuid=value.get("workload_uuid"),
            reset_epoch=int(value.get("reset_epoch") or 0),
        )


@dataclass(frozen=True)
class FenceDecision:
    """Verdict of :func:`accept`. Truthy only when accepted -- never a bare tuple,
    whose truthiness would accept everything."""

    accepted: bool
    reason: str
    detail: str = field(default="", compare=False)

    def __bool__(self) -> bool:
        return self.accepted


#: Stable reasons :func:`accept` returns.
FENCE_REASONS: tuple[str, ...] = (
    "ok",
    "no_active_run",
    "missing_run_identity",
    "foreign_workload",
    "stale_run",
    "stale_stream_instance",
    "stale_reset_epoch",
    "future_reset_epoch",
)


def accept(
    item: Mapping[str, Any], current_run: RunIdentity | Mapping[str, Any] | None
) -> FenceDecision:
    """Reference run-fencing rule for a command, sample or media frame.

    *item* carries the identity it was produced/addressed under: ``run_id``
    (required), and optionally ``workload_uuid``, ``stream_instance_id`` and
    ``reset_epoch``. Fails closed: no active run, or an item with no
    ``run_id``, is rejected. A different workload, run or stream instance is
    stale. An item from an earlier reset epoch is queued output from before a
    reset; one from a later epoch is not something this run produced. A
    reconnecting publisher that kept the current identity is accepted -- a
    reconnect is not a new run.

    Pure: no clock, no state. Sequence de-duplication and ordering are the
    caller's queue policy, not identity.
    """
    if current_run is None:
        return FenceDecision(False, "no_active_run")
    run = (
        current_run
        if isinstance(current_run, RunIdentity)
        else RunIdentity.from_mapping(current_run)
    )

    run_id = item.get("run_id")
    if not run_id:
        return FenceDecision(False, "missing_run_identity", "item carries no run_id")

    workload = item.get("workload_uuid")
    if (
        workload is not None
        and run.workload_uuid is not None
        and workload != run.workload_uuid
    ):
        return FenceDecision(
            False, "foreign_workload", f"{workload} != {run.workload_uuid}"
        )
    if run_id != run.run_id:
        return FenceDecision(False, "stale_run", f"{run_id} != {run.run_id}")

    stream = item.get("stream_instance_id")
    if (
        stream is not None
        and run.stream_instance_id is not None
        and stream != run.stream_instance_id
    ):
        return FenceDecision(
            False, "stale_stream_instance", f"{stream} != {run.stream_instance_id}"
        )

    epoch = item.get("reset_epoch")
    if epoch is not None:
        if isinstance(epoch, bool) or not isinstance(epoch, int):
            return FenceDecision(
                False,
                "missing_run_identity",
                f"reset_epoch {epoch!r} is not an integer",
            )
        if epoch < run.reset_epoch:
            return FenceDecision(
                False, "stale_reset_epoch", f"{epoch} < {run.reset_epoch}"
            )
        if epoch > run.reset_epoch:
            return FenceDecision(
                False, "future_reset_epoch", f"{epoch} > {run.reset_epoch}"
            )
    return FenceDecision(True, "ok")


__all__ = [
    "BACKEND_ALIASES",
    "BACKEND_ISAAC",
    "BACKEND_MUJOCO",
    "BACKEND_MUJOCO_WARP",
    "BUNDLE_MANIFEST_FILENAME",
    "CANONICAL_BACKENDS",
    "CLOUD_NODE_PROFILE_ISAAC",
    "CLOUD_NODE_PROFILE_MUJOCO",
    "DEFAULT_BACKEND",
    "DEFAULT_HARDWARE_QUALIFICATION_MAX_AGE_S",
    "DEFAULT_ISAAC_EXECUTION_PROFILE",
    "ERROR_BACKEND_CAPACITY_UNAVAILABLE",
    "ERROR_BACKEND_INCOMPATIBLE",
    "ERROR_BACKEND_NOT_ENABLED",
    "ERROR_BACKEND_RUNTIME_MISMATCH",
    "ERROR_BACKEND_UNSUPPORTED",
    "ERROR_CODES",
    "ERROR_PARAMETER_INVALID",
    "ERROR_PARAMETER_UNSUPPORTED",
    "EXECUTION_PROFILES",
    "EXECUTION_PROFILE_ISAAC_CPU",
    "EXECUTION_PROFILE_ISAAC_GPU",
    "EXECUTION_PROFILE_ISAAC_NEWTON",
    "EXECUTION_PROFILE_PHYSICS",
    "EXPERIMENTAL_EXECUTION_PROFILES",
    "FENCE_REASONS",
    "FenceDecision",
    "HARDWARE_QUALIFICATION_CONTRACT",
    "HARDWARE_QUALIFICATION_FAIL",
    "HARDWARE_QUALIFICATION_METADATA_KEY",
    "HARDWARE_QUALIFICATION_PASS",
    "ISAAC_PHYSICS_EXTENSION_KEY",
    "ISAAC_ONLY_TIMING_FIELDS",
    "ISAAC_PHYSICS_FIELDS",
    "ISAAC_PHYSICS_UNSUPPORTED_BY_PROFILE",
    "ISAAC_SOLVER_POSITION_ITERATIONS",
    "ISAAC_SOLVER_VELOCITY_ITERATIONS",
    "ISAAC_SUBSTEPS",
    "MIN_ISAAC_VRAM_MIB",
    "PHYSICS_DEVICES",
    "PHYSICS_DEVICE_CPU",
    "PHYSICS_DEVICE_GPU",
    "PHYSICS_ENGINES",
    "PHYSICS_ENGINE_NEWTON",
    "PHYSICS_ENGINE_PHYSX",
    "PhysicsSelection",
    "RunIdentity",
    "RuntimeAuditCheck",
    "TIMING_DT",
    "TIMING_DT_RANGE",
    "TIMING_FIELDS",
    "TIMING_FIELDS_BY_BACKEND",
    "TIMING_RANGE_SELF_HIT_FALLBACK",
    "TIMING_RANGE_STREAM_FREQUENCY_HZ",
    "TIMING_RANGE_STREAM_FREQUENCY_RANGE",
    "TIMING_REALTIME",
    "TIMING_RENDERING_DT",
    "TIMING_RENDERING_DT_RANGE",
    "TIMING_SIMULATION_SPEED",
    "TIMING_STREAM_FREQUENCY_HZ",
    "TIMING_STREAM_FREQUENCY_RANGE",
    "SimulationContractError",
    "UnsupportedSimulationBackendError",
    "accept",
    "attestation_key_digest",
    "check_hardware_qualification",
    "check_runtime_audit",
    "compute_bundle_digest",
    "execution_profile_for_physics",
    "find_secret_like",
    "hash_bundle_files",
    "is_confined_relative_path",
    "normalize_backend",
    "normalize_execution_profile",
    "normalize_gravity",
    "normalize_isaac_physics",
    "normalize_timing",
    "physics_for_execution_profile",
    "validate_bundle_manifest",
    "validate_bundle_path",
]
