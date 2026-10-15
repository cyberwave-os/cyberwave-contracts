"""Write, read, validate and diff ``simulation.replay_trace.v1`` JSON Lines traces.

A replay trace is the evidence that two runs of one scenario -- two Isaac Sim
runs, or Isaac and MuJoCo -- behaved the same, or the exact place they did not.
The first line is a header record; every later line is one ``command``,
``state``, ``lifecycle``, ``readiness``, ``sensor`` or ``camera_frame`` record.
A complete trace ends with a ``lifecycle`` record whose ``event`` is ``stop``.

Standard library only. Traces never hold credentials: :class:`TraceWriter`
refuses credential-like keys and values (tokens, bearer headers, signed-URL
parameters such as ``X-Goog-Signature``), and :func:`read_trace` reports any it
finds.

The diff (:func:`diff_traces`) first checks that the two headers describe the
same experiment (bundle digest, runtime and extension lock, seed, execution
profile, timestep, asset revisions, run-identity completeness). It then aligns
the per-entity streams and reports the **first** divergence, classified as:

- ``contract`` -- an exact (product-contract) field differs: a command payload,
  a sequence number, a kind, an identity, a frame size;
- ``numeric`` -- a numeric field differs by more than the header tolerance;
- ``image`` -- a camera checksum differs where no image tolerance applies;
- ``missing`` -- one trace has a record the other lacks;
- ``reorder`` -- the same records in a different order;
- ``stale_run`` -- a record from another run, stream instance or reset epoch.

CLI::

    python -m cyberwave_contracts.trace validate trace.jsonl
    python -m cyberwave_contracts.trace diff a.jsonl b.jsonl --json out.json --md out.md
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from .simulation import (
    CANONICAL_BACKENDS,
    EXECUTION_PROFILES,
    SHA256_DIGEST,
    RunIdentity,
    SimulationContractError,
    accept,
    find_secret_like,
    normalize_execution_profile,
)

TRACE_CONTRACT_ID = "simulation.replay_trace.v1"
TRACE_VERSION = 1
REPORT_VERSION = 1

RECORD_KINDS: tuple[str, ...] = (
    "command",
    "state",
    "lifecycle",
    "readiness",
    "sensor",
    "camera_frame",
)

#: Lifecycle event that marks a complete trace, and the one that bumps the epoch.
STOP_EVENT = "stop"
RESET_EVENT = "reset"

#: Field patterns that are always compared exactly, on top of the header's
#: ``tolerances.exact_fields``. Patterns are ``fnmatch`` over ``<kind>.<dotted path>``.
DEFAULT_EXACT_FIELDS: tuple[str, ...] = (
    "*.kind",
    "*.seq",
    "*.reset_epoch",
    "*.entity_id",
    "*.sensor_id",
    "command.payload",
    "command.payload.*",
    "state.valid",
    "sensor.sensor_kind",
    "camera_frame.width",
    "camera_frame.height",
    "camera_frame.format",
    "lifecycle.event",
    "readiness.milestone",
)

#: Fields that legitimately differ between two runs and are never compared.
IGNORED_FIELDS = frozenset(
    {"run_id", "stream_instance_id", "workload_uuid", "wall_time", "detail"}
)

#: Issue codes that make a trace unusable as evidence.
INVALID_ISSUES = frozenset(
    {"header_missing", "header_invalid", "record_invalid", "unknown_kind", "secret"}
)

_REQUIRED: Mapping[str, tuple[str, ...]] = {
    "command": ("seq", "entity_id", "sim_time_acq", "sim_time_applied", "payload"),
    "state": ("seq", "entity_id", "sim_time"),
    "lifecycle": ("event", "sim_time"),
    "readiness": ("milestone", "sim_time"),
    "sensor": ("seq", "sensor_id", "sim_time_acq"),
    "camera_frame": (
        "seq",
        "sensor_id",
        "sim_time_acq",
        "width",
        "height",
        "format",
        "checksum",
    ),
}


class TraceFormatError(ValueError):
    """A header or record that does not match ``simulation.replay_trace.v1``."""


class TraceSecretError(ValueError):
    """A header or record carrying something credential-like. Never written."""


# -- validation ---------------------------------------------------------------------


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number_or_none(value: Any) -> bool:
    return value is None or _is_number(value)


def _is_str_or_none(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _is_object_or_none(value: Any) -> bool:
    return value is None or isinstance(value, Mapping)


def _is_vector(value: Any, axes: str) -> bool:
    return isinstance(value, Mapping) and all(_is_number(value.get(a)) for a in axes)


#: Header keys the published schema requires, by parent. Those the diff needs
#: (seed, timestep, physics, bundle_digest, run_id, stream_instance_id) are
#: reported as ``header_incomplete`` instead, so a trace missing one is still read.
_HEADER_REQUIRED: Mapping[str, tuple[str, ...]] = {
    "": ("asset_revisions", "renderer", "duration", "initial_state"),
    "run": ("workload_uuid",),
    "runtime": (
        "execution_profile",
        "image_digest",
        "extension_lock_digest",
        "physics_variant",
    ),
    "tolerances": ("exact_fields", "numeric", "image"),
}

#: Record times the schema types as a number, never null.
_NON_NULL_TIMES: Mapping[str, tuple[str, ...]] = {
    "command": ("sim_time_acq",),
    "state": ("sim_time",),
    "sensor": ("sim_time_acq",),
    "camera_frame": ("sim_time_acq",),
}

#: Record identity fields that must be strings; ``entity_id`` may be null on the
#: sensor kinds, which can be keyed by ``sensor_id`` alone.
_STRING_FIELDS = ("entity_id", "sensor_id", "event", "milestone", "format")
_NULLABLE_ENTITY_KINDS = frozenset({"sensor", "camera_frame"})


def validate_header(header: Any) -> list[dict[str, str]]:
    """Problems with a trace header as ``{"code", "message"}`` dicts.

    ``header_invalid`` marks a malformed header. ``header_incomplete`` marks a
    well-formed header missing a fingerprint field the diff needs (seed, run
    identity, timestep, physics): the trace can be read but not compared.
    """
    issues: list[dict[str, str]] = []

    def bad(message: str) -> None:
        issues.append({"code": "header_invalid", "message": message})

    def incomplete(message: str) -> None:
        issues.append({"code": "header_incomplete", "message": message})

    if not isinstance(header, Mapping):
        return [
            {"code": "header_missing", "message": "first line is not a JSON object"}
        ]
    if header.get("kind") != "header":
        return [
            {"code": "header_missing", "message": "first record is not kind 'header'"}
        ]
    if header.get("contract") != TRACE_CONTRACT_ID:
        bad(f"contract must be {TRACE_CONTRACT_ID!r}")
    if header.get("trace_version") != TRACE_VERSION or isinstance(
        header.get("trace_version"), bool
    ):
        bad(f"trace_version must be {TRACE_VERSION}")

    run = header.get("run")
    if not isinstance(run, Mapping):
        incomplete("run identity missing")
    else:
        for key in ("run_id", "stream_instance_id"):
            if not isinstance(run.get(key), str) or not run.get(key):
                incomplete(f"run.{key} missing")
        if run.get("workload_uuid") is not None and not isinstance(
            run.get("workload_uuid"), str
        ):
            bad("run.workload_uuid must be a string or null")

    digest = header.get("bundle_digest")
    if digest is not None and (
        not isinstance(digest, str) or not SHA256_DIGEST.fullmatch(digest)
    ):
        bad("bundle_digest must be 'sha256:<64 hex>' or null")
    if "bundle_digest" not in header:
        incomplete("bundle_digest missing (use null when there is no bundle)")
    revisions = header.get("asset_revisions", {})
    if not isinstance(revisions, Mapping):
        bad("asset_revisions must be an object")
    elif not all(isinstance(v, str) for v in revisions.values()):
        bad("asset_revisions values must be strings")
    if header.get("source") not in ("local", "cloud", None):
        bad("source must be 'local', 'cloud' or null")
    for key in ("scenario", "created_at"):
        if not _is_str_or_none(header.get(key)):
            bad(f"{key} must be a string or null")
    if not _is_object_or_none(header.get("renderer")):
        bad("renderer must be an object or null")
    if not _is_object_or_none(header.get("initial_state")):
        bad("initial_state must be an object or null")

    runtime = header.get("runtime")
    if not isinstance(runtime, Mapping):
        bad("runtime missing")
    else:
        if runtime.get("backend") not in CANONICAL_BACKENDS:
            bad(f"runtime.backend must be one of {', '.join(CANONICAL_BACKENDS)}")
        profile = runtime.get("execution_profile")
        if profile is not None and profile not in EXECUTION_PROFILES:
            bad(
                f"runtime.execution_profile must be one of {', '.join(EXECUTION_PROFILES)} or null"
            )
        elif runtime.get("backend") in CANONICAL_BACKENDS:
            # Each is valid on its own; the pair must be one a run can have (an
            # Isaac profile under backend mujoco is not). The schema cannot say
            # so -- the generator refuses conditionals -- so it is checked here.
            try:
                normalize_execution_profile(runtime["backend"], profile)
            except SimulationContractError as exc:
                bad(f"runtime: {exc.detail}")
        for key in ("image_digest", "extension_lock_digest"):
            value = runtime.get(key)
            if value is not None and (
                not isinstance(value, str) or not SHA256_DIGEST.fullmatch(value)
            ):
                bad(f"runtime.{key} must be 'sha256:<64 hex>' or null")
        for key in ("physics_variant", "runtime_version"):
            if not _is_str_or_none(runtime.get(key)):
                bad(f"runtime.{key} must be a string or null")

    if "seed" not in header or header.get("seed") is None:
        incomplete("seed missing")
    elif not _is_int(header.get("seed")):
        bad("seed must be an integer")
    timestep = header.get("timestep")
    if timestep is None:
        incomplete("timestep missing")
    elif not _is_number(timestep) or timestep <= 0:
        bad("timestep must be a positive number")
    if "physics" not in header:
        incomplete("physics missing (use null when the runtime reports none)")
    elif header["physics"] is not None and not isinstance(header["physics"], Mapping):
        bad("physics must be an object or null")
    else:
        physics = header["physics"] or {}
        gravity = physics.get("gravity")
        if gravity is not None and (
            not isinstance(gravity, list) or not all(_is_number(g) for g in gravity)
        ):
            bad("physics.gravity must be a list of numbers or null")
        for key, low in (
            ("substeps", 1),
            ("solver_position_iterations", 0),
            ("solver_velocity_iterations", 0),
        ):
            value = physics.get(key)
            if value is not None and (not _is_int(value) or value < low):
                bad(f"physics.{key} must be an integer >= {low} or null")
        if not _is_number_or_none(physics.get("scene_timestep")):
            bad("physics.scene_timestep must be a number or null")
    timing = header.get("timing")
    if not _is_object_or_none(timing):
        bad("timing must be an object or null")
    elif timing is not None:
        if timing.get("realtime") is not None and not isinstance(
            timing.get("realtime"), bool
        ):
            bad("timing.realtime must be a boolean or null")
        for key in (
            "simulation_speed",
            "stream_frequency_hz",
            "range_stream_frequency_hz",
        ):
            if not _is_number_or_none(timing.get(key)):
                bad(f"timing.{key} must be a number or null")
    duration = header.get("duration")
    if duration is not None and (not _is_number(duration) or duration < 0):
        bad("duration must be a non-negative number or null")

    tolerances = header.get("tolerances")
    if not isinstance(tolerances, Mapping):
        bad("tolerances missing")
    else:
        exact = tolerances.get("exact_fields", [])
        if not isinstance(exact, list) or not all(isinstance(p, str) for p in exact):
            bad("tolerances.exact_fields must be a list of strings")
        numeric = tolerances.get("numeric", {})
        if not isinstance(numeric, Mapping):
            bad("tolerances.numeric must be an object")
        else:
            for pattern, tol in numeric.items():
                if not isinstance(tol, Mapping) or not all(
                    _is_number(tol.get(k)) and tol[k] >= 0 for k in ("abs", "rel")
                ):
                    bad(
                        f"tolerances.numeric[{pattern!r}] needs non-negative abs and rel"
                    )
        image = tolerances.get("image", {})
        if not isinstance(image, Mapping):
            bad("tolerances.image must be an object")
        elif not all(isinstance(policy, Mapping) for policy in image.values()):
            bad("tolerances.image values must be objects")

    # The writer must not produce a header the contract it names rejects.
    parents = {"": header, "run": run, "runtime": runtime, "tolerances": tolerances}
    for parent, keys in _HEADER_REQUIRED.items():
        found = parents[parent]
        if isinstance(found, Mapping):
            prefix = f"{parent}." if parent else ""
            for key in keys:
                if key not in found:
                    bad(f"{prefix}{key} missing (use null where the schema allows it)")

    for finding in find_secret_like(header):
        issues.append({"code": "secret", "message": finding})
    return issues


def validate_record(record: Any) -> list[dict[str, str]]:
    """Problems with one non-header record as ``{"code", "message"}`` dicts."""
    if not isinstance(record, Mapping):
        return [{"code": "record_invalid", "message": "record is not a JSON object"}]
    kind = record.get("kind")
    if not isinstance(kind, str) or kind not in _REQUIRED:
        return [{"code": "unknown_kind", "message": f"unknown record kind {kind!r}"}]
    issues = [
        {"code": "record_invalid", "message": f"{kind}: {key} missing"}
        for key in _REQUIRED[kind]
        if key not in record
    ]

    def bad(message: str) -> None:
        issues.append({"code": "record_invalid", "message": f"{kind}: {message}"})

    for key in _STRING_FIELDS:
        if key not in record or isinstance(record[key], str):
            continue
        if not (
            key == "entity_id"
            and kind in _NULLABLE_ENTITY_KINDS
            and record[key] is None
        ):
            bad(f"{key} must be a string")
    for key in ("run_id", "stream_instance_id"):
        if not _is_str_or_none(record.get(key)):
            bad(f"{key} must be a string or null")
    for key in _NON_NULL_TIMES.get(kind, ()):
        if key in record and record[key] is None:
            bad(f"{key} must be a finite number")
    for key in ("values", "summary", "calibration", "detail"):
        if not _is_object_or_none(record.get(key)):
            bad(f"{key} must be an object or null")
    if "seq" in record and (not _is_int(record["seq"]) or record["seq"] < 0):
        issues.append(
            {
                "code": "record_invalid",
                "message": f"{kind}: seq must be a non-negative integer",
            }
        )
    for key in ("sim_time", "sim_time_acq", "sim_time_applied", "wall_time"):
        value = record.get(key)
        if value is not None and not _is_number(value):
            issues.append(
                {
                    "code": "record_invalid",
                    "message": f"{kind}: {key} must be a finite number or null",
                }
            )
    epoch = record.get("reset_epoch")
    if epoch is not None and (not _is_int(epoch) or epoch < 0):
        issues.append(
            {
                "code": "record_invalid",
                "message": f"{kind}: reset_epoch must be a non-negative integer",
            }
        )
    if kind == "command" and not isinstance(record.get("payload"), Mapping):
        issues.append(
            {"code": "record_invalid", "message": "command: payload must be an object"}
        )
    if kind == "state":
        if "valid" in record and not isinstance(record["valid"], bool):
            bad("valid must be a boolean")
        joints = record.get("joints", {})
        if not isinstance(joints, Mapping):
            bad("joints must be an object")
        elif not all(
            isinstance(sample, Mapping)
            and all(
                _is_number_or_none(sample.get(k))
                for k in ("position", "velocity", "effort")
            )
            for sample in joints.values()
        ):
            bad("joints samples must hold numbers or null")
        base = record.get("base")
        if not _is_object_or_none(base):
            bad("base must be an object or null")
        elif base is not None:
            pose = base.get("pose")
            if not (
                isinstance(pose, Mapping)
                and _is_vector(pose.get("position"), "xyz")
                and _is_vector(pose.get("rotation"), "wxyz")
            ):
                bad("base.pose needs a position {x, y, z} and rotation {w, x, y, z}")
            twist = base.get("twist")
            if twist is not None and not (
                isinstance(twist, Mapping)
                and _is_vector(twist.get("linear"), "xyz")
                and _is_vector(twist.get("angular"), "xyz")
            ):
                bad("base.twist needs linear and angular {x, y, z}, or null")
    if kind == "camera_frame":
        for key in ("width", "height"):
            if key in record and (not _is_int(record[key]) or record[key] < 1):
                issues.append(
                    {
                        "code": "record_invalid",
                        "message": f"camera_frame: {key} must be a positive integer",
                    }
                )
        checksum = record.get("checksum")
        if checksum is not None and (
            not isinstance(checksum, str) or not SHA256_DIGEST.fullmatch(checksum)
        ):
            issues.append(
                {
                    "code": "record_invalid",
                    "message": "camera_frame: checksum must be 'sha256:<hex>' or null",
                }
            )
    for finding in find_secret_like(record):
        issues.append({"code": "secret", "message": finding})
    return issues


# -- writing ------------------------------------------------------------------------


def _dumps(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except ValueError as exc:  # NaN / Infinity
        raise TraceFormatError(f"non-finite number in trace record: {exc}") from exc


class TraceWriter:
    """Write a ``simulation.replay_trace.v1`` JSON Lines file, header first.

    ``contract``, ``kind`` and ``trace_version`` are filled in if absent. The
    header and every record are validated before anything is written; a
    malformed one raises :class:`TraceFormatError` and a credential-like one
    :class:`TraceSecretError`, so a refused record never reaches disk. An
    existing file is not overwritten unless ``overwrite=True``. Use as a
    context manager; :meth:`stop` writes the closing lifecycle record.
    """

    def __init__(
        self,
        target: str | os.PathLike[str] | IO[str],
        header: Mapping[str, Any],
        *,
        overwrite: bool = False,
    ) -> None:
        full = {
            "contract": TRACE_CONTRACT_ID,
            "kind": "header",
            "trace_version": TRACE_VERSION,
            **header,
        }
        _raise_for(validate_header(full), "header")
        self.header: dict[str, Any] = dict(full)
        self._owns = not hasattr(target, "write")
        if self._owns:
            path = Path(target)  # type: ignore[arg-type]
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file: IO[str] = path.open("w" if overwrite else "x", encoding="utf-8")
        else:
            self._file = target  # type: ignore[assignment]
        self.records_written = 0
        self._file.write(_dumps(self.header) + "\n")

    def write(self, record: Mapping[str, Any]) -> None:
        """Validate and append one record."""
        if isinstance(record, Mapping) and record.get("kind") == "header":
            raise TraceFormatError("a trace has exactly one header, written first")
        _raise_for(validate_record(record), f"record {self.records_written + 1}")
        self._file.write(_dumps(record) + "\n")
        self.records_written += 1

    def stop(self, *, sim_time: float | None, wall_time: float | None = None) -> None:
        """Write the closing ``lifecycle`` ``stop`` record that marks the trace complete."""
        self.write(
            {
                "kind": "lifecycle",
                "event": STOP_EVENT,
                "sim_time": sim_time,
                "wall_time": wall_time,
            }
        )

    def close(self) -> None:
        self._file.flush()
        if self._owns:
            self._file.close()

    def __enter__(self) -> TraceWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _raise_for(issues: list[dict[str, str]], where: str) -> None:
    secrets = [i["message"] for i in issues if i["code"] == "secret"]
    if secrets:
        raise TraceSecretError(
            f"{where}: refusing credential-like content: {'; '.join(secrets)}"
        )
    if issues:
        raise TraceFormatError(f"{where}: {'; '.join(i['message'] for i in issues)}")


# -- reading ------------------------------------------------------------------------


@dataclass
class Trace:
    """A parsed trace. ``records`` excludes the header; ``lines[i]`` is the
    1-based file line of ``records[i]``. ``stale`` holds the indices of records
    the run fence rejects."""

    header: dict[str, Any] | None
    records: list[dict[str, Any]] = field(default_factory=list)
    lines: list[int] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    stale: dict[int, str] = field(default_factory=dict)
    path: str | None = None

    @property
    def complete(self) -> bool:
        return not any(i["code"] == "incomplete" for i in self.issues)

    @property
    def valid(self) -> bool:
        return not any(i["code"] in INVALID_ISSUES for i in self.issues)


class TraceReader:
    """Iterate a trace file, then :meth:`read` it into a :class:`Trace` with issues.

    Issues are reported, not raised, so a broken trace still yields a useful
    report: ``header_missing``/``header_invalid``/``header_incomplete``,
    ``record_invalid``, ``unknown_kind``, ``secret``, ``incomplete`` (truncated
    line or no closing ``stop``), ``reorder`` (non-increasing ``seq`` within one
    stream) and ``stale_run`` (a record the run fence rejects).
    """

    def __init__(self, source: str | os.PathLike[str] | IO[str]) -> None:
        self.source = source

    def __iter__(self) -> Iterator[tuple[int, str]]:
        if hasattr(self.source, "read"):
            yield from enumerate(self.source, start=1)  # type: ignore[arg-type]
            return
        with Path(self.source).open(encoding="utf-8") as handle:  # type: ignore[arg-type]
            yield from enumerate(handle, start=1)

    def read(self) -> Trace:
        path = None if hasattr(self.source, "read") else os.fspath(self.source)  # type: ignore[arg-type]
        trace = Trace(header=None, path=path)
        raw_lines = list(self)
        if not raw_lines:
            trace.issues.append(
                {"code": "header_missing", "line": 1, "message": "empty trace"}
            )
            return trace

        for index, (number, text) in enumerate(raw_lines):
            last = index == len(raw_lines) - 1
            if not text.strip():
                continue
            try:
                value = json.loads(text, parse_constant=_reject_constant)
            except ValueError as exc:
                code = (
                    "incomplete"
                    if last and not text.endswith("\n")
                    else "record_invalid"
                )
                trace.issues.append(
                    {
                        "code": code,
                        "line": number,
                        "message": f"unparseable line: {exc}",
                    }
                )
                continue
            if trace.header is None and index == 0:
                for issue in validate_header(value):
                    trace.issues.append({**issue, "line": number})
                if isinstance(value, Mapping) and value.get("kind") == "header":
                    trace.header = dict(value)
                    continue
                if not isinstance(value, Mapping):
                    continue
            for issue in validate_record(value):
                trace.issues.append({**issue, "line": number})
            if isinstance(value, Mapping):
                trace.records.append(dict(value))
                trace.lines.append(number)

        if trace.header is not None:
            _fence(trace)
        _check_order(trace)
        if not any(
            r.get("kind") == "lifecycle" and r.get("event") == STOP_EVENT
            for r in trace.records[-1:]
        ):
            if not any(i["code"] == "incomplete" for i in trace.issues):
                trace.issues.append(
                    {
                        "code": "incomplete",
                        "line": trace.lines[-1] if trace.lines else 1,
                        "message": "no closing lifecycle 'stop' record",
                    }
                )
        return trace


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number {name}")


def read_trace(source: str | os.PathLike[str] | IO[str]) -> Trace:
    """Shorthand for ``TraceReader(source).read()``."""
    return TraceReader(source).read()


def _fence(trace: Trace) -> None:
    """Mark records the run fence (:func:`cyberwave_contracts.simulation.accept`) rejects.

    A record without its own identity inherits the header's. A lifecycle
    ``reset`` record advances the expected epoch to its ``reset_epoch`` (or by
    one), so output stamped with the old epoch after it is stale.
    """
    assert trace.header is not None
    run = trace.header.get("run") or {}
    if not isinstance(run, Mapping) or not run.get("run_id"):
        return
    epoch = 0
    for index, record in enumerate(trace.records):
        is_reset = (
            record.get("kind") == "lifecycle" and record.get("event") == RESET_EVENT
        )
        current = RunIdentity(
            run_id=str(run["run_id"]),
            stream_instance_id=run.get("stream_instance_id"),
            workload_uuid=run.get("workload_uuid"),
            reset_epoch=epoch,
        )
        item = {
            "run_id": record.get("run_id") or run["run_id"],
            "stream_instance_id": record.get("stream_instance_id"),
            "workload_uuid": record.get("workload_uuid"),
            "reset_epoch": record.get("reset_epoch"),
        }
        if is_reset:
            # A reset names the epoch it opens, so the epoch comparison cannot
            # apply to the record that bumps it -- but its run identity still
            # must, or a reset from another run silences this one's output.
            item.pop("reset_epoch")
        decision = accept(item, current)
        if is_reset and decision:
            new_epoch = record.get("reset_epoch")
            epoch = new_epoch if _is_int(new_epoch) and new_epoch > epoch else epoch + 1
            continue
        if not decision:
            trace.stale[index] = decision.reason
            trace.issues.append(
                {
                    "code": "stale_run",
                    "line": trace.lines[index],
                    "message": f"{record.get('kind')} rejected by run fence: {decision.reason} {decision.detail}".strip(),
                }
            )


def _stream_key(record: Mapping[str, Any]) -> tuple[str, str]:
    kind = str(record.get("kind"))
    if kind in ("command", "state"):
        return kind, str(record.get("entity_id"))
    if kind in ("sensor", "camera_frame"):
        return kind, str(record.get("sensor_id"))
    return kind, ""


def _check_order(trace: Trace) -> None:
    last: dict[tuple[str, str], int] = {}
    for index, record in enumerate(trace.records):
        if index in trace.stale or not _is_int(record.get("seq")):
            continue
        key = _stream_key(record)
        if key in last and record["seq"] <= last[key]:
            trace.issues.append(
                {
                    "code": "reorder",
                    "line": trace.lines[index],
                    "message": f"{key[0]} {key[1]}: seq {record['seq']} after {last[key]}",
                }
            )
        last[key] = max(record["seq"], last.get(key, record["seq"]))


# -- diff ---------------------------------------------------------------------------

#: Header fields that must match for two traces to be comparable.
#: Header fields without which two traces cannot be shown comparable.
_INCOMPLETE_FIELDS: tuple[str, ...] = ("seed", "timestep", "physics", "bundle_digest")

_FINGERPRINT_FIELDS: tuple[str, ...] = (
    "trace_version",
    "bundle_digest",
    "asset_revisions",
    "runtime.backend",
    "runtime.execution_profile",
    "runtime.image_digest",
    "runtime.extension_lock_digest",
    "runtime.physics_variant",
    "runtime.runtime_version",
    "seed",
    "timestep",
    "physics",
    "initial_state",
    "scenario",
)

#: Header fields that may differ but are worth reporting. ``timing`` is pacing
#: and egress cadence: it changes wall-clock behaviour, not the physics.
_WARN_FIELDS: tuple[str, ...] = (
    "duration",
    "renderer",
    "tolerances",
    "source",
    "timing",
)

_MISSING = object()

_VERDICT_EXIT = {
    "match": 0,
    "within_tolerance": 0,
    "divergent": 1,
    "incomplete": 2,
    "incompatible": 2,
    "invalid": 2,
}


def _get(mapping: Any, dotted: str) -> Any:
    value = mapping
    for part in dotted.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _flatten(value: Any, prefix: str, out: dict[str, Any]) -> None:
    if isinstance(value, Mapping) and value:
        for key, item in value.items():
            if key in IGNORED_FIELDS and prefix.count(".") == 0:
                continue
            _flatten(item, f"{prefix}.{key}", out)
    elif isinstance(value, list) and value:
        for index, item in enumerate(value):
            _flatten(item, f"{prefix}.{index}", out)
    else:
        out[prefix] = value


def _sim_time(record: Mapping[str, Any]) -> float:
    for key in ("sim_time_acq", "sim_time"):
        if _is_number(record.get(key)):
            return float(record[key])
    return math.inf


def _specificity(pattern: str) -> int:
    return sum(1 for ch in pattern if ch not in "*?[]")


def _numeric_tolerance(
    path: str, numeric: Mapping[str, Any]
) -> tuple[str, dict[str, float]] | None:
    matches = [p for p in numeric if fnmatch.fnmatchcase(path, p)]
    if not matches:
        return None
    best = max(matches, key=_specificity)
    tol = numeric[best]
    return best, {"abs": float(tol.get("abs", 0.0)), "rel": float(tol.get("rel", 0.0))}


def _jsonable(value: Any) -> Any:
    return None if value is _MISSING else value


def _context(trace: Trace, index: int | None) -> dict[str, Any]:
    if index is None or index >= len(trace.records):
        return {}
    record = trace.records[index]
    last_command = None
    for prior in reversed(trace.records[: index + 1]):
        if prior.get("kind") == "command" and prior is not record:
            last_command = {
                "seq": prior.get("seq"),
                "entity_id": prior.get("entity_id"),
                "sim_time_acq": prior.get("sim_time_acq"),
            }
            break
    return {
        "line": trace.lines[index],
        "record": record,
        "last_command": last_command,
    }


def compare_headers(
    a: Mapping[str, Any] | None, b: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Fingerprint compatibility of two headers: ``{"compatible", "mismatches", "warnings"}``."""
    if a is None or b is None:
        return {
            "compatible": False,
            "mismatches": [{"field": "header", "a": a is not None, "b": b is not None}],
            "warnings": [],
        }
    mismatches: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for label, header in (("a", a), ("b", b)):
        # validate_header calls these incomplete. Absent on both sides they would
        # compare equal below and pass two runs nobody can show are comparable.
        # physics and bundle_digest may be null; only an absent key is refused.
        for name in _INCOMPLETE_FIELDS:
            if name in ("seed", "timestep"):
                absent = header.get(name) is None
            else:
                absent = name not in header
            if absent:
                mismatches.append(
                    {
                        "field": name,
                        "a": _jsonable(_get(a, name)),
                        "b": _jsonable(_get(b, name)),
                        "reason": f"{name} missing in {label}",
                    }
                )
        run = header.get("run") if isinstance(header.get("run"), Mapping) else {}
        missing = [k for k in ("run_id", "stream_instance_id") if not run.get(k)]
        if missing:
            mismatches.append(
                {
                    "field": "run",
                    "a": None,
                    "b": None,
                    "reason": f"run identity incomplete in {label}: {', '.join(missing)}",
                }
            )
    reported = {m["field"] for m in mismatches}
    for name in _FINGERPRINT_FIELDS:
        if name in reported:
            continue
        va, vb = _get(a, name), _get(b, name)
        if va != vb:
            mismatches.append({"field": name, "a": _jsonable(va), "b": _jsonable(vb)})
    if a.get("bundle_digest") is None and b.get("bundle_digest") is None:
        warnings.append(
            {
                "field": "bundle_digest",
                "reason": "neither trace names a scene bundle; asset identity is unverified",
            }
        )
    for name in _WARN_FIELDS:
        va, vb = _get(a, name), _get(b, name)
        if va != vb:
            warnings.append({"field": name, "a": _jsonable(va), "b": _jsonable(vb)})
    return {
        "compatible": not mismatches,
        "mismatches": mismatches,
        "warnings": warnings,
    }


def _streams(trace: Trace) -> dict[tuple[str, str], list[int]]:
    streams: dict[tuple[str, str], list[int]] = {}
    for index, record in enumerate(trace.records):
        if index in trace.stale:
            continue
        streams.setdefault(_stream_key(record), []).append(index)
    return streams


def _compare_records(
    ra: Mapping[str, Any],
    rb: Mapping[str, Any],
    exact: list[str],
    numeric: Mapping[str, Any],
    image: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Field differences between two aligned records: (divergences, within_tolerance)."""
    kind = str(ra.get("kind"))
    fa: dict[str, Any] = {}
    fb: dict[str, Any] = {}
    _flatten(ra, kind, fa)
    _flatten(rb, kind, fb)
    fa.pop(f"{kind}.kind", None)
    fb.pop(f"{kind}.kind", None)
    divergences: list[dict[str, Any]] = []
    within: list[dict[str, Any]] = []
    for path in sorted(set(fa) | set(fb)):
        va, vb = fa.get(path, _MISSING), fb.get(path, _MISSING)
        # Equal values of different types still differ -- True is not 1 -- but
        # an int and a float are one number JSON spelled two ways, which is a
        # serialiser difference between two runtimes, not a divergence.
        if va == vb and (type(va) is type(vb) or (_is_number(va) and _is_number(vb))):
            continue
        is_exact = any(fnmatch.fnmatchcase(path, p) for p in exact)
        if kind == "camera_frame" and path == "camera_frame.checksum" and not is_exact:
            if any(fnmatch.fnmatchcase(path, p) for p in image):
                within.append(
                    {
                        "class": "image",
                        "field": path,
                        "a": _jsonable(va),
                        "b": _jsonable(vb),
                        "note": "image tolerance applies; compare pixels out of band",
                    }
                )
            else:
                divergences.append(
                    {
                        "class": "image",
                        "field": path,
                        "a": _jsonable(va),
                        "b": _jsonable(vb),
                    }
                )
            continue
        if _is_number(va) and _is_number(vb) and not is_exact:
            delta = abs(float(va) - float(vb))
            found = _numeric_tolerance(path, numeric)
            pattern, tol = found if found else (None, {"abs": 0.0, "rel": 0.0})
            allowed = tol["abs"] + tol["rel"] * abs(float(va))
            entry = {
                "class": "numeric",
                "field": path,
                "a": va,
                "b": vb,
                "delta": delta,
                "tolerance": tol,
                "tolerance_pattern": pattern,
            }
            if delta <= allowed:
                within.append(entry)
            else:
                divergences.append(entry)
            continue
        divergences.append(
            {"class": "contract", "field": path, "a": _jsonable(va), "b": _jsonable(vb)}
        )
    return divergences, within


def diff_traces(a: Trace, b: Trace) -> dict[str, Any]:
    """Compare two traces and return a JSON-serialisable report.

    ``verdict`` is the most severe of: ``invalid`` (unreadable, malformed or
    secret-bearing trace) > ``incompatible`` (headers describe different
    experiments) > ``incomplete`` (either trace truncated) > ``divergent`` >
    ``within_tolerance`` > ``match``. ``first_divergence`` is the earliest
    divergence by simulation time, then by line in trace *a*; tolerances come
    from *a*'s header (the baseline).
    """
    headers = compare_headers(a.header, b.header)
    report: dict[str, Any] = {
        "tool": "cyberwave_contracts.trace",
        "report_version": REPORT_VERSION,
        "contract": TRACE_CONTRACT_ID,
        "a": _side(a),
        "b": _side(b),
        "header": headers,
        "first_divergence": None,
        "summary": {
            "compared_records": 0,
            "divergences": {},
            "within_tolerance": 0,
            "within_tolerance_by_class": {},
            "by_stream": {},
            "max_abs_delta": {},
        },
    }
    if not a.valid or not b.valid or a.header is None or b.header is None:
        report["verdict"] = "invalid"
        return report

    tolerances = a.header.get("tolerances") or {}
    exact = list(DEFAULT_EXACT_FIELDS) + list(tolerances.get("exact_fields") or [])
    numeric = tolerances.get("numeric") or {}
    image = tolerances.get("image") or {}

    candidates: list[dict[str, Any]] = []
    within_entries: list[dict[str, Any]] = []
    max_delta: dict[str, float] = {}
    compared = 0

    for label, trace in (("a", a), ("b", b)):
        for index, reason in trace.stale.items():
            record = trace.records[index]
            candidates.append(
                {
                    "class": "stale_run",
                    "field": "run_identity",
                    "reason": reason,
                    "trace": label,
                    "kind": record.get("kind"),
                    "stream": "/".join(_stream_key(record)),
                    "sim_time": _sim_time(record),
                    "index_a": index if label == "a" else None,
                    "index_b": index if label == "b" else None,
                }
            )

    streams_a, streams_b = _streams(a), _streams(b)
    for key in sorted(set(streams_a) | set(streams_b)):
        ia, ib = streams_a.get(key, []), streams_b.get(key, [])
        seqs_a = [a.records[i].get("seq") for i in ia]
        seqs_b = [b.records[i].get("seq") for i in ib]
        for position in range(max(len(ia), len(ib))):
            xa = ia[position] if position < len(ia) else None
            xb = ib[position] if position < len(ib) else None
            base = {
                "kind": key[0],
                "stream": "/".join(key),
                "position": position,
                "index_a": xa,
                "index_b": xb,
            }
            if xa is None or xb is None:
                present = a.records[xa] if xa is not None else b.records[xb]  # type: ignore[index]
                candidates.append(
                    {
                        **base,
                        "class": "missing",
                        "field": None,
                        "a": "present" if xa is not None else None,
                        "b": "present" if xb is not None else None,
                        "sim_time": _sim_time(present),
                    }
                )
                continue
            compared += 1
            ra, rb = a.records[xa], b.records[xb]
            if (
                ra.get("seq") != rb.get("seq")
                and rb.get("seq") in seqs_a
                and ra.get("seq") in seqs_b
            ):
                candidates.append(
                    {
                        **base,
                        "class": "reorder",
                        "field": f"{key[0]}.seq",
                        "a": ra.get("seq"),
                        "b": rb.get("seq"),
                        "sim_time": min(_sim_time(ra), _sim_time(rb)),
                    }
                )
                continue
            divergences, within = _compare_records(ra, rb, exact, numeric, image)
            within_entries.extend(
                {**entry, "stream": base["stream"]} for entry in within
            )
            for entry in within + [d for d in divergences if d["class"] == "numeric"]:
                if "delta" in entry:
                    max_delta[entry["field"]] = max(
                        max_delta.get(entry["field"], 0.0), entry["delta"]
                    )
            for divergence in divergences:
                candidates.append(
                    {
                        **base,
                        **divergence,
                        "sim_time": min(_sim_time(ra), _sim_time(rb)),
                    }
                )

    counts: dict[str, int] = {}
    within_counts: dict[str, int] = {}
    by_stream: dict[str, dict[str, dict[str, int]]] = {}
    for bucket, entries, totals in (
        ("divergences", candidates, counts),
        ("within_tolerance", within_entries, within_counts),
    ):
        for entry in entries:
            cls = entry["class"]
            totals[cls] = totals.get(cls, 0) + 1
            stream = by_stream.setdefault(
                entry["stream"], {"divergences": {}, "within_tolerance": {}}
            )[bucket]
            stream[cls] = stream.get(cls, 0) + 1
    report["summary"] = {
        "compared_records": compared,
        "divergences": counts,
        "within_tolerance": len(within_entries),
        "within_tolerance_by_class": within_counts,
        "by_stream": dict(sorted(by_stream.items())),
        "max_abs_delta": dict(sorted(max_delta.items())),
    }

    if candidates:

        def order(c: dict[str, Any]) -> tuple[float, int, int]:
            line_a = (
                a.lines[c["index_a"]] if c.get("index_a") is not None else sys.maxsize
            )
            line_b = (
                b.lines[c["index_b"]] if c.get("index_b") is not None else sys.maxsize
            )
            return (c["sim_time"], line_a, line_b)

        first = dict(min(candidates, key=order))
        first["sim_time"] = None if first["sim_time"] == math.inf else first["sim_time"]
        context_a = _context(a, first.pop("index_a", None))
        context_b = _context(b, first.pop("index_b", None))
        first["line_a"] = context_a.get("line")
        first["line_b"] = context_b.get("line")
        first["context"] = {
            "bundle_digest": {
                "a": a.header.get("bundle_digest"),
                "b": b.header.get("bundle_digest"),
            },
            "runtime": {"a": a.header.get("runtime"), "b": b.header.get("runtime")},
            "record_a": context_a.get("record"),
            "record_b": context_b.get("record"),
            "last_command_a": context_a.get("last_command"),
            "last_command_b": context_b.get("last_command"),
        }
        report["first_divergence"] = first

    if not headers["compatible"]:
        report["verdict"] = "incompatible"
    elif not a.complete or not b.complete:
        report["verdict"] = "incomplete"
    elif candidates:
        report["verdict"] = "divergent"
    elif within_entries:
        report["verdict"] = "within_tolerance"
    else:
        report["verdict"] = "match"
    return report


def _side(trace: Trace) -> dict[str, Any]:
    header = trace.header or {}
    return {
        "path": trace.path,
        "records": len(trace.records),
        "complete": trace.complete,
        "valid": trace.valid,
        "source": header.get("source"),
        "run": header.get("run"),
        "issues": trace.issues,
    }


def exit_code(report: Mapping[str, Any]) -> int:
    """0 for match/within_tolerance, 1 for divergent, 2 when the comparison is not conclusive."""
    return _VERDICT_EXIT.get(str(report.get("verdict")), 2)


def _fmt(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, default=str)
    return text if len(text) <= 120 else text[:117] + "..."


def render_markdown(report: Mapping[str, Any]) -> str:
    """A short human summary of a :func:`diff_traces` report."""
    a, b = report["a"], report["b"]
    lines = [
        "# Replay trace diff",
        "",
        f"**Verdict: `{report['verdict']}`**",
        "",
        "| | a | b |",
        "|---|---|---|",
        f"| file | `{a['path']}` | `{b['path']}` |",
        f"| source | {a['source']} | {b['source']} |",
        f"| records | {a['records']} | {b['records']} |",
        f"| complete | {a['complete']} | {b['complete']} |",
        f"| valid | {a['valid']} | {b['valid']} |",
        "",
    ]
    header = report["header"]
    if header["mismatches"]:
        lines += ["## Header mismatches (not comparable)", ""]
        for m in header["mismatches"]:
            reason = f" -- {m['reason']}" if m.get("reason") else ""
            lines.append(
                f"- `{m['field']}`: a={_fmt(m.get('a'))} b={_fmt(m.get('b'))}{reason}"
            )
        lines.append("")
    if header["warnings"]:
        lines += ["## Header warnings", ""]
        for w in header["warnings"]:
            detail = w.get("reason") or f"a={_fmt(w.get('a'))} b={_fmt(w.get('b'))}"
            lines.append(f"- `{w['field']}`: {detail}")
        lines.append("")
    issues = [(label, i) for label in ("a", "b") for i in report[label]["issues"]]
    if issues:
        lines += ["## Trace issues", ""]
        for label, issue in issues[:20]:
            lines.append(
                f"- {label}:{issue.get('line')} `{issue['code']}` {issue['message']}"
            )
        if len(issues) > 20:
            lines.append(f"- ... {len(issues) - 20} more")
        lines.append("")
    first = report.get("first_divergence")
    if first:
        lines += [
            "## First divergence",
            "",
            f"- class: `{first['class']}`",
            f"- stream: `{first.get('stream')}`  sim_time: {first.get('sim_time')}",
            f"- field: `{first.get('field')}`",
            f"- a (line {first.get('line_a')}): {_fmt(first.get('a'))}",
            f"- b (line {first.get('line_b')}): {_fmt(first.get('b'))}",
        ]
        if first.get("tolerance") is not None:
            lines.append(
                f"- delta {first.get('delta')} exceeds tolerance {_fmt(first['tolerance'])} ({first.get('tolerance_pattern')})"
            )
        if first.get("reason"):
            lines.append(f"- reason: `{first['reason']}` (trace {first.get('trace')})")
        context = first.get("context") or {}
        lines.append(
            f"- last command: a={_fmt(context.get('last_command_a'))} b={_fmt(context.get('last_command_b'))}"
        )
        lines.append("")
    summary = report["summary"]
    lines += [
        "## Summary",
        "",
        f"- compared records: {summary['compared_records']}",
        f"- divergences by class: {_fmt(summary['divergences'])}",
        f"- differences within tolerance: {summary['within_tolerance']}"
        f" {_fmt(summary.get('within_tolerance_by_class') or {})}",
    ]
    for stream, counts in (summary.get("by_stream") or {}).items():
        lines.append(
            f"- `{stream}`: divergences {_fmt(counts['divergences'])},"
            f" within tolerance {_fmt(counts['within_tolerance'])}"
        )
    return "\n".join(lines) + "\n"


# -- CLI ----------------------------------------------------------------------------


def _write_output(path: str | None, text: str) -> None:
    if path is None:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cyberwave_contracts.trace", description=__doc__.splitlines()[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser(
        "validate", help="validate one trace; exit 1 on any issue"
    )
    validate.add_argument("trace")
    diff = sub.add_parser(
        "diff", help="compare two traces and report the first divergence"
    )
    diff.add_argument("a")
    diff.add_argument("b")
    diff.add_argument("--json", dest="json_out", help="write the JSON report here")
    diff.add_argument("--md", dest="md_out", help="write the markdown summary here")
    args = parser.parse_args(argv)

    if args.command == "validate":
        trace = read_trace(args.trace)
        result = {
            "path": trace.path,
            "records": len(trace.records),
            "valid": trace.valid,
            "complete": trace.complete,
            "issues": trace.issues,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not trace.issues else 1

    report = diff_traces(read_trace(args.a), read_trace(args.b))
    _write_output(
        args.json_out, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )
    markdown = render_markdown(report)
    _write_output(args.md_out, markdown)
    print(markdown, end="")
    return exit_code(report)


__all__ = [
    "DEFAULT_EXACT_FIELDS",
    "RECORD_KINDS",
    "TRACE_CONTRACT_ID",
    "TRACE_VERSION",
    "Trace",
    "TraceFormatError",
    "TraceReader",
    "TraceSecretError",
    "TraceWriter",
    "compare_headers",
    "diff_traces",
    "exit_code",
    "main",
    "read_trace",
    "render_markdown",
    "validate_header",
    "validate_record",
]

if __name__ == "__main__":
    sys.exit(main())
