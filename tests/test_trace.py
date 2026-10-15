"""Replay trace writer, reader, validation and diff (``cyberwave_contracts.trace``)."""

from __future__ import annotations

import copy
import io
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from cyberwave_contracts import trace as tr

FIXTURES = Path(__file__).parent / "fixtures" / "simulation"
TRACES = FIXTURES / "traces"
TWIN = "6f1c7a52-3d1e-4c0b-9a7e-2b9d6f0c1a11"


def _header(**overrides: object) -> dict:
    header = json.loads(
        (FIXTURES / "replay_trace_header.valid.json").read_text(encoding="utf-8")
    )
    header.update(overrides)
    return header


def _records(
    steps: int = 4,
    *,
    jitter: float = 0.0,
    command_targets: dict[int, float] | None = None,
) -> list[dict]:
    records: list[dict] = [
        {"kind": "lifecycle", "event": "start", "sim_time": 0.0, "wall_time": None},
        {"kind": "readiness", "milestone": "first_state", "sim_time": 0.0},
    ]
    for i in range(steps):
        t = round(i * 0.005, 6)
        target = (command_targets or {}).get(i, 0.1 * (i + 1))
        records.append(
            {
                "kind": "command",
                "seq": i,
                "entity_id": TWIN,
                "sim_time_acq": t,
                "sim_time_applied": t,
                "payload": {
                    "type": "joint_position",
                    "targets": {"wheel_left": target},
                },
            }
        )
        records.append(
            {
                "kind": "state",
                "seq": i,
                "entity_id": TWIN,
                "sim_time": t,
                "joints": {
                    "wheel_left": {
                        "position": 0.1 * i + (jitter if i else 0.0),
                        "velocity": 0.0,
                        "effort": None,
                    }
                },
                "base": None,
            }
        )
    records.append(
        {
            "kind": "lifecycle",
            "event": "stop",
            "sim_time": round(steps * 0.005, 6),
            "wall_time": None,
        }
    )
    return records


def _write(path: Path, header: dict, records: list[dict]) -> Path:
    with tr.TraceWriter(path, header) as writer:
        for record in records:
            writer.write(record)
    return path


def _raw(path: Path, header: dict, records: list[dict]) -> Path:
    """Write without the writer's checks, to build deliberately broken traces."""
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in [header, *records]), encoding="utf-8"
    )
    return path


def _diff(
    tmp_path: Path,
    a: tuple[dict, list[dict]],
    b: tuple[dict, list[dict]],
    raw: bool = False,
) -> dict:
    make = _raw if raw else _write
    pa = make(tmp_path / "a.jsonl", *a)
    pb = make(tmp_path / "b.jsonl", *b)
    return tr.diff_traces(tr.read_trace(pa), tr.read_trace(pb))


# -- writer ------------------------------------------------------------------------


def test_writer_puts_header_first_and_round_trips(tmp_path: Path) -> None:
    path = _write(tmp_path / "t.jsonl", _header(), _records())
    lines = path.read_text().splitlines()
    assert json.loads(lines[0])["kind"] == "header"
    trace = tr.read_trace(path)
    assert trace.valid and trace.complete and trace.issues == []
    assert len(trace.records) == len(_records())


def test_writer_fills_contract_fields_and_refuses_overwrite(tmp_path: Path) -> None:
    header = _header()
    for key in ("contract", "kind", "trace_version"):
        header.pop(key)
    path = _write(tmp_path / "t.jsonl", header, [])
    assert (
        json.loads(path.read_text().splitlines()[0])["contract"]
        == "simulation.replay_trace.v1"
    )
    with pytest.raises(FileExistsError):
        tr.TraceWriter(path, _header())


@pytest.mark.parametrize(
    "secret",
    [
        {"token": "abc"},
        {"uri": "https://storage.googleapis.com/b/o?X-Goog-Signature=deadbeef"},
        {"uri": "https://x/y?Signature=abc&Expires=1"},
        {"uri": "https://x/y?token=abc"},
        {"auth": "Bearer abc"},
    ],
)
def test_writer_refuses_secrets_in_records(secret: dict) -> None:
    buffer = io.StringIO()
    writer = tr.TraceWriter(buffer, _header())
    record = {
        "kind": "command",
        "seq": 0,
        "entity_id": TWIN,
        "sim_time_acq": 0.0,
        "payload": {"type": "x", **secret},
    }
    with pytest.raises(tr.TraceSecretError):
        writer.write(record)
    assert len(buffer.getvalue().splitlines()) == 1  # nothing after the header


def test_writer_refuses_secret_in_header() -> None:
    with pytest.raises(tr.TraceSecretError):
        tr.TraceWriter(io.StringIO(), _header(renderer={"api_key": "x"}))


@pytest.mark.parametrize(
    "record",
    [
        {"kind": "header"},
        {"kind": "telepathy"},
        {"kind": "command", "seq": 0, "entity_id": TWIN, "sim_time_acq": 0.0},
        {
            "kind": "command",
            "seq": -1,
            "entity_id": TWIN,
            "sim_time_acq": 0.0,
            "payload": {},
        },
        {"kind": "state", "seq": 0, "entity_id": TWIN, "sim_time": float("nan")},
        {
            "kind": "camera_frame",
            "seq": 0,
            "sensor_id": "c",
            "sim_time_acq": 0.0,
            "width": 0,
            "height": 1,
            "format": "rgb8",
            "checksum": None,
        },
    ],
)
def test_writer_refuses_malformed_records(record: dict) -> None:
    writer = tr.TraceWriter(io.StringIO(), _header())
    with pytest.raises(tr.TraceFormatError):
        writer.write(record)


def test_writer_refuses_header_missing_seed() -> None:
    header = _header()
    header.pop("seed")
    with pytest.raises(tr.TraceFormatError, match="seed"):
        tr.TraceWriter(io.StringIO(), header)


def test_writer_refuses_a_header_and_record_the_schema_rejects() -> None:
    minimal = {
        "run": {"run_id": "r", "stream_instance_id": "s"},
        "bundle_digest": None,
        "runtime": {"backend": "mujoco"},
        "seed": 1,
        "timestep": 0.01,
        "physics": None,
        "tolerances": {},
    }
    with pytest.raises(tr.TraceFormatError) as refused:
        tr.TraceWriter(io.StringIO(), minimal)
    for key in ("asset_revisions", "run.workload_uuid", "runtime.physics_variant"):
        assert key in str(refused.value)
    writer = tr.TraceWriter(io.StringIO(), _header())
    with pytest.raises(tr.TraceFormatError, match="sim_time"):
        writer.write({"kind": "state", "seq": 0, "entity_id": "e", "sim_time": None})


# -- reader ------------------------------------------------------------------------


def test_reader_reports_truncated_trace(tmp_path: Path) -> None:
    path = _write(tmp_path / "t.jsonl", _header(), _records())
    text = path.read_text()
    path.write_text(text[: len(text) - 20])  # cut mid-line, as a crash would
    trace = tr.read_trace(path)
    assert not trace.complete
    assert any(i["code"] == "incomplete" for i in trace.issues)


def test_reader_reports_missing_header(tmp_path: Path) -> None:
    path = _raw(tmp_path / "t.jsonl", _records()[0], _records()[1:])
    trace = tr.read_trace(path)
    assert trace.header is None and not trace.valid


def test_reader_reports_secret_from_a_hand_written_trace(tmp_path: Path) -> None:
    records = _records()
    records[2]["payload"]["url"] = "https://x/y?X-Goog-Signature=abc"
    trace = tr.read_trace(_raw(tmp_path / "t.jsonl", _header(), records))
    assert not trace.valid and any(i["code"] == "secret" for i in trace.issues)


def test_reader_marks_output_after_reset_with_old_epoch_stale(tmp_path: Path) -> None:
    records = _records()
    records.insert(
        4,
        {
            "kind": "lifecycle",
            "event": "reset",
            "sim_time": 0.005,
            "wall_time": None,
            "reset_epoch": 1,
        },
    )
    records[5]["reset_epoch"] = 0  # queued output from before the reset
    trace = tr.read_trace(_raw(tmp_path / "t.jsonl", _header(), records))
    assert list(trace.stale.values()) == ["stale_reset_epoch"]


def test_reader_fences_a_reset_from_another_run(tmp_path: Path) -> None:
    # A foreign reset must not advance this run's epoch: if it did, the run's
    # own epoch-0 output after it would be thrown away as stale instead.
    records = _records()
    records.insert(
        4,
        {
            "kind": "lifecycle",
            "event": "reset",
            "sim_time": 0.005,
            "wall_time": None,
            "run_id": "RUN-OTHER",
            "workload_uuid": "W-OTHER",
            "reset_epoch": 1,
        },
    )
    records[5]["reset_epoch"] = 0
    records[6]["reset_epoch"] = 0
    trace = tr.read_trace(_raw(tmp_path / "t.jsonl", _header(), records))
    assert trace.stale == {4: "stale_run"}


def test_header_refuses_an_execution_profile_its_backend_cannot_have() -> None:
    runtime = {**_header()["runtime"], "backend": "mujoco"}
    issues = tr.validate_header(_header(runtime=runtime))
    assert [i["code"] for i in issues] == ["header_invalid"]
    assert "only valid with backend 'isaac'" in issues[0]["message"]
    runtime["execution_profile"] = None
    assert tr.validate_header(_header(runtime=runtime)) == []


# -- diff ----------------------------------------------------------------------------


def test_fixture_traces_are_within_tolerance() -> None:
    report = tr.diff_traces(
        tr.read_trace(TRACES / "baseline.local.jsonl"),
        tr.read_trace(TRACES / "candidate.cloud.jsonl"),
    )
    assert report["verdict"] == "within_tolerance"
    assert report["first_divergence"] is None
    assert tr.exit_code(report) == 0


def test_identical_traces_match(tmp_path: Path) -> None:
    report = _diff(tmp_path, (_header(), _records()), (_header(), _records()))
    assert report["verdict"] == "match" and report["summary"][
        "compared_records"
    ] == len(_records())


def test_different_bundle_digest_is_incompatible(tmp_path: Path) -> None:
    report = _diff(
        tmp_path,
        (_header(), _records()),
        (_header(bundle_digest="sha256:" + "0" * 64), _records()),
    )
    assert report["verdict"] == "incompatible"
    assert [m["field"] for m in report["header"]["mismatches"]] == ["bundle_digest"]
    assert tr.exit_code(report) == 2


@pytest.mark.parametrize(
    "dropped",
    [
        ("timestep",),
        ("physics",),
        ("bundle_digest",),
        ("timestep", "physics", "bundle_digest"),
    ],
)
def test_fields_missing_on_both_sides_are_incompatible(
    tmp_path: Path, dropped: tuple[str, ...]
) -> None:
    """Absent on both sides, these compare equal; the runs still are not comparable."""
    header = _header()
    for name in dropped:
        header.pop(name)
    report = _diff(tmp_path, (header, _records()), (header, _records()), raw=True)
    assert report["verdict"] == "incompatible"
    reasons = {m.get("reason") for m in report["header"]["mismatches"]}
    for name in dropped:
        assert {f"{name} missing in a", f"{name} missing in b"} <= reasons


def test_null_physics_and_bundle_digest_on_both_sides_still_match(
    tmp_path: Path,
) -> None:
    header = _header(physics=None, bundle_digest=None)
    report = _diff(tmp_path, (header, _records()), (header, _records()))
    assert report["verdict"] == "match"


def test_missing_seed_is_incompatible(tmp_path: Path) -> None:
    header_b = _header()
    header_b.pop("seed")
    report = _diff(tmp_path, (_header(), _records()), (header_b, _records()), raw=True)
    assert report["verdict"] == "incompatible"
    assert any(
        m.get("reason") == "seed missing in b" for m in report["header"]["mismatches"]
    )


def test_mismatched_execution_profile_is_incompatible(tmp_path: Path) -> None:
    header_b = _header()
    header_b["runtime"] = {
        **header_b["runtime"],
        "execution_profile": "isaac-gpu-physics",
    }
    report = _diff(tmp_path, (_header(), _records()), (header_b, _records()))
    assert report["verdict"] == "incompatible"
    assert [m["field"] for m in report["header"]["mismatches"]] == [
        "runtime.execution_profile"
    ]


def test_mismatched_extension_lock_is_incompatible(tmp_path: Path) -> None:
    header_b = _header()
    header_b["runtime"] = {
        **header_b["runtime"],
        "extension_lock_digest": "sha256:" + "2" * 64,
    }
    report = _diff(tmp_path, (_header(), _records()), (header_b, _records()))
    assert report["verdict"] == "incompatible"


_PHYSICS = {
    "gravity": [0.0, 0.0, -9.81],
    "substeps": 1,
    "solver_position_iterations": 32,
    "solver_velocity_iterations": 1,
    "scene_timestep": 0.001,
}


def test_mismatched_physics_is_incompatible(tmp_path: Path) -> None:
    header_b = _header(physics={**_PHYSICS, "substeps": 4})
    report = _diff(
        tmp_path, (_header(physics=_PHYSICS), _records()), (header_b, _records())
    )
    assert report["verdict"] == "incompatible"
    assert [m["field"] for m in report["header"]["mismatches"]] == ["physics"]


def test_header_without_physics_is_incomplete() -> None:
    header = _header()
    del header["physics"]
    issues = tr.validate_header(header)
    assert [i["code"] for i in issues] == ["header_incomplete"]
    assert tr.validate_header(_header(physics=None)) == []


def test_different_timing_only_warns(tmp_path: Path) -> None:
    report = _diff(
        tmp_path,
        (_header(timing={"realtime": True, "simulation_speed": 1.0}), _records()),
        (_header(timing={"realtime": False, "simulation_speed": None}), _records()),
    )
    assert report["verdict"] == "match"
    assert [w["field"] for w in report["header"]["warnings"]] == ["timing"]


def test_header_schema_accepts_physics_and_timing() -> None:
    header = _header(
        physics=_PHYSICS,
        timing={
            "realtime": True,
            "simulation_speed": 2.0,
            "stream_frequency_hz": 20.0,
            "range_stream_frequency_hz": 10.0,
        },
    )
    from cyberwave_contracts.models.simulation_replay_trace_v1 import (
        SimulationReplayTraceV1,
    )

    model = SimulationReplayTraceV1.model_validate(header)
    assert model.physics is not None and model.physics.substeps == 1
    assert model.timing is not None and model.timing.simulation_speed == 2.0


def test_incomplete_trace(tmp_path: Path) -> None:
    report = _diff(
        tmp_path, (_header(), _records()), (_header(), _records()[:-3]), raw=True
    )
    assert report["verdict"] == "incomplete"
    assert report["b"]["complete"] is False
    assert report["first_divergence"]["class"] == "missing"


def test_stale_run_identity(tmp_path: Path) -> None:
    records_b = _records()
    records_b.insert(
        5, {**records_b[4], "seq": 1, "run_id": "previous-run", "sim_time": 0.0}
    )
    report = _diff(tmp_path, (_header(), _records()), (_header(), records_b), raw=True)
    assert report["verdict"] == "divergent"
    first = report["first_divergence"]
    assert (
        first["class"] == "stale_run"
        and first["reason"] == "stale_run"
        and first["trace"] == "b"
    )


def test_reordered_commands(tmp_path: Path) -> None:
    records_b = _records()
    # Swap commands 1 and 2 (records 4 and 6), keeping sim time order of the lines.
    records_b[4], records_b[6] = records_b[6], records_b[4]
    report = _diff(tmp_path, (_header(), _records()), (_header(), records_b), raw=True)
    assert report["verdict"] == "divergent"
    assert report["first_divergence"]["class"] == "reorder"
    assert any(i["code"] == "reorder" for i in report["b"]["issues"])


def test_numerical_divergence(tmp_path: Path) -> None:
    report = _diff(
        tmp_path, (_header(), _records()), (_header(), _records(jitter=0.01))
    )
    assert report["verdict"] == "divergent"
    first = report["first_divergence"]
    assert first["class"] == "numeric"
    assert first["field"] == "state.joints.wheel_left.position"
    assert first["tolerance_pattern"] == "state.joints.*.position"
    assert first["sim_time"] == 0.005


def test_numeric_difference_within_tolerance(tmp_path: Path) -> None:
    report = _diff(
        tmp_path, (_header(), _records()), (_header(), _records(jitter=5e-5))
    )
    assert report["verdict"] == "within_tolerance"
    assert report["summary"]["within_tolerance"] == 3
    assert report["summary"]["within_tolerance_by_class"] == {"numeric": 3}


def test_summary_counts_each_stream_separately(tmp_path: Path) -> None:
    report = _diff(
        tmp_path, (_header(), _records()), (_header(), _records(jitter=0.01))
    )
    by_stream = report["summary"]["by_stream"]
    assert set(by_stream) == {f"state/{TWIN}"}
    assert by_stream[f"state/{TWIN}"]["divergences"] == report["summary"]["divergences"]


_RECORD_DEFS = {
    "command": "replayTraceCommandRecord",
    "state": "replayTraceStateRecord",
    "lifecycle": "replayTraceLifecycleRecord",
    "readiness": "replayTraceReadinessRecord",
    "sensor": "replayTraceSensorRecord",
    "camera_frame": "replayTraceCameraFrameRecord",
}

#: Values every field is swapped for, one at a time, to probe the schema.
_PROBES: tuple[object, ...] = (None, "x", -1, 0, 1.5, True, [], ["x"], {}, {"k": "x"})

_STAMP = {"run_id": "local-run-0001", "stream_instance_id": "s", "reset_epoch": 0}
_VEC = {"x": 0.0, "y": 0.0, "z": 0.0}
#: One record of each kind with every field the schema describes.
_FULL_RECORDS: tuple[dict, ...] = (
    {
        "kind": "command",
        "seq": 0,
        "entity_id": TWIN,
        "sim_time_acq": 0.0,
        "sim_time_applied": None,
        "payload": {"type": "joint_position"},
        **_STAMP,
    },
    {
        "kind": "state",
        "seq": 0,
        "entity_id": TWIN,
        "sim_time": 0.0,
        "valid": True,
        "joints": {"wheel_left": {"position": 0.0, "velocity": None, "effort": 0.0}},
        "base": {
            "pose": {"position": _VEC, "rotation": {"w": 1.0, **_VEC}},
            "twist": {"linear": _VEC, "angular": _VEC},
        },
        **_STAMP,
    },
    {
        "kind": "lifecycle",
        "event": "start",
        "sim_time": 0.0,
        "wall_time": 1.0,
        "detail": {"why": "test"},
        **_STAMP,
    },
    {
        "kind": "readiness",
        "milestone": "first_state",
        "sim_time": None,
        "wall_time": None,
        **_STAMP,
    },
    {
        "kind": "sensor",
        "seq": 0,
        "sensor_id": "lidar",
        "entity_id": None,
        "sim_time_acq": 0.0,
        "values": {"count": 4},
        "summary": None,
        **_STAMP,
    },
    {
        "kind": "camera_frame",
        "seq": 0,
        "sensor_id": "cam",
        "entity_id": TWIN,
        "sim_time_acq": 0.0,
        "width": 2,
        "height": 2,
        "format": "rgb8",
        "checksum": "sha256:" + "0" * 64,
        "calibration": None,
        **_STAMP,
    },
)


def _full_header() -> dict:
    return _header(
        created_at="2026-01-01T00:00:00Z",
        timing={
            "realtime": True,
            "simulation_speed": 1.0,
            "stream_frequency_hz": 20.0,
            "range_stream_frequency_hz": None,
        },
    )


def _schema_errors(instance: object, definition: str | None = None) -> list:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (
            Path(tr.__file__).parent
            / "schemas"
            / "simulation.replay_trace.v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    if definition is not None:
        schema = {"$ref": f"#/$defs/{definition}", "$defs": schema["$defs"]}
    return list(jsonschema.Draft202012Validator(schema).iter_errors(instance))


def _mutations(sample: dict) -> Iterator[tuple[str, dict]]:
    """``sample`` with one field, at any depth, deleted or swapped for each probe."""

    def paths(node: object, prefix: tuple[str, ...]) -> Iterator[tuple[str, ...]]:
        if isinstance(node, dict):
            for key, value in node.items():
                yield (*prefix, key)
                yield from paths(value, (*prefix, key))

    for path in paths(sample, ()):
        for probe in (_DELETE, *_PROBES):
            mutated = copy.deepcopy(sample)
            parent = mutated
            for key in path[:-1]:
                parent = parent[key]
            if probe is _DELETE:
                del parent[path[-1]]
            else:
                parent[path[-1]] = probe
            yield (
                f"{'.'.join(path)}={'<deleted>' if probe is _DELETE else probe!r}",
                mutated,
            )


_DELETE = object()


def test_writer_refuses_every_header_the_schema_rejects() -> None:
    """Whatever the published schema refuses, the writer refuses too."""
    full = _full_header()
    assert _schema_errors(full) == [] and tr.validate_header(full) == []
    accepted = [
        label
        for label, header in _mutations(full)
        if _schema_errors(header) and not tr.validate_header(header)
    ]
    assert accepted == []


@pytest.mark.parametrize("record", _FULL_RECORDS, ids=lambda r: r["kind"])
def test_writer_refuses_every_record_the_schema_rejects(record: dict) -> None:
    definition = _RECORD_DEFS[record["kind"]]
    assert _schema_errors(record, definition) == []
    assert tr.validate_record(record) == []
    accepted = [
        label
        for label, mutated in _mutations(record)
        if _schema_errors(mutated, definition) and not tr.validate_record(mutated)
    ]
    assert accepted == []


def test_required_fields_match_the_schema() -> None:
    """Every record kind's mandatory fields are the schema's."""
    schema_defs = json.loads(
        (
            Path(tr.__file__).parent
            / "schemas"
            / "simulation.replay_trace.v1.schema.json"
        ).read_text(encoding="utf-8")
    )["$defs"]
    assert set(tr._REQUIRED) == set(_RECORD_DEFS)
    for kind, name in _RECORD_DEFS.items():
        required = set(schema_defs[name]["required"]) - {"kind"}
        assert set(tr._REQUIRED[kind]) == required, kind


def test_fixture_traces_satisfy_the_schema() -> None:
    for path in sorted(TRACES.glob("*.jsonl")):
        header, *records = [json.loads(line) for line in path.read_text().splitlines()]
        assert _schema_errors(header) == [], path.name
        for record in records:
            assert _schema_errors(record, _RECORD_DEFS[record["kind"]]) == [], path.name


def test_plant_records_without_optional_fields_are_valid(tmp_path: Path) -> None:
    """The Isaac plant writes lifecycle records without a wall clock and sensor
    records keyed by ``sensor_id`` alone; both stay valid evidence."""
    path = _write(
        tmp_path / "plant.jsonl",
        _header(),
        [
            {"kind": "lifecycle", "event": "start", "sim_time": 0.0},
            {
                "kind": "sensor",
                "seq": 0,
                "sensor_id": "lidar",
                "sensor_kind": "lidar",
                "sim_time_acq": 0.0,
                "values": {"count": 4},
            },
            {"kind": "lifecycle", "event": "stop", "sim_time": 0.01},
        ],
    )
    trace = tr.read_trace(path)
    assert trace.valid and trace.complete


def test_changed_command_is_the_first_divergence(tmp_path: Path) -> None:
    # The command changes at step 2; the state diverges from step 3 on. The
    # report must point at the command, not at the state it caused.
    records_b = _records(command_targets={2: 0.9})
    for record in records_b:
        if record["kind"] == "state" and record["seq"] >= 3:
            record["joints"]["wheel_left"]["position"] += 0.5
    report = _diff(tmp_path, (_header(), _records()), (_header(), records_b))
    assert report["verdict"] == "divergent"
    first = report["first_divergence"]
    assert first["class"] == "contract"
    assert first["field"] == "command.payload.targets.wheel_left"
    assert (first["a"], first["b"]) == (pytest.approx(0.3), 0.9)
    assert first["context"]["bundle_digest"]["a"] == _header()["bundle_digest"]
    assert report["summary"]["divergences"]["numeric"] >= 1


def test_int_and_float_spellings_of_one_number_match(tmp_path: Path) -> None:
    # Two runtimes' serialisers spell 0 as 0 and 0.0; that is not a divergence,
    # even on an exact field. A bool is still not the number it equals.
    records_a, records_b = _records(), _records()
    records_a[2]["payload"]["position"] = 0
    records_b[2]["payload"]["position"] = 0.0
    report = _diff(tmp_path, (_header(), records_a), (_header(), records_b))
    assert report["verdict"] == "match"
    records_b[2]["payload"]["position"] = False
    (tmp_path / "bool").mkdir()
    report = _diff(tmp_path / "bool", (_header(), records_a), (_header(), records_b))
    assert report["verdict"] == "divergent"
    first = report["first_divergence"]
    assert (first["class"], first["field"]) == ("contract", "command.payload.position")


def test_image_checksum_without_tolerance_is_divergent(tmp_path: Path) -> None:
    frame = {
        "kind": "camera_frame",
        "seq": 0,
        "sensor_id": "front",
        "sim_time_acq": 0.0,
        "width": 4,
        "height": 4,
        "format": "rgb8",
    }
    records_a = [
        *_records()[:-1],
        {**frame, "checksum": "sha256:" + "a" * 64},
        _records()[-1],
    ]
    records_b = [
        *_records()[:-1],
        {**frame, "checksum": "sha256:" + "b" * 64},
        _records()[-1],
    ]
    header = _header()
    header["tolerances"] = {**header["tolerances"], "image": {}}
    report = _diff(tmp_path, (header, records_a), (copy.deepcopy(header), records_b))
    assert report["first_divergence"]["class"] == "image"


def test_run_identity_fields_are_not_compared(tmp_path: Path) -> None:
    header_b = _header(
        run={"workload_uuid": "w", "run_id": "other", "stream_instance_id": "other"}
    )
    records_b = [{**r, "run_id": "other"} for r in _records()]
    report = _diff(tmp_path, (_header(), _records()), (header_b, records_b), raw=True)
    assert report["verdict"] == "match"


def test_invalid_trace_verdict(tmp_path: Path) -> None:
    report = _diff(
        tmp_path,
        (_header(), _records()),
        (_header(), [*_records()[:-1], {"kind": "telepathy"}, _records()[-1]]),
        raw=True,
    )
    assert report["verdict"] == "invalid"


# -- CLI ------------------------------------------------------------------------------


def test_cli_diff_writes_json_and_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = _write(tmp_path / "a.jsonl", _header(), _records())
    b = _write(tmp_path / "b.jsonl", _header(), _records(command_targets={1: 5.0}))
    out_json, out_md = tmp_path / "out" / "diff.json", tmp_path / "out" / "diff.md"
    code = tr.main(
        ["diff", str(a), str(b), "--json", str(out_json), "--md", str(out_md)]
    )
    assert code == 1
    report = json.loads(out_json.read_text())
    assert (
        report["verdict"] == "divergent"
        and report["first_divergence"]["class"] == "contract"
    )
    markdown = out_md.read_text()
    assert (
        "First divergence" in markdown
        and "command.payload.targets.wheel_left" in markdown
    )
    assert "Verdict" in capsys.readouterr().out


def test_cli_validate(tmp_path: Path) -> None:
    assert tr.main(["validate", str(TRACES / "baseline.local.jsonl")]) == 0
    broken = _raw(tmp_path / "t.jsonl", _header(), _records()[:-1])
    assert tr.main(["validate", str(broken)]) == 1
