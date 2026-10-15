# !! GENERATED from simulation.replay_trace.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Integer, Number


class SimulationReplayTraceV1Physics(BaseModel):
    """SimulationReplayTraceV1Physics

    Effective physics settings the plant applied (part of the replay fingerprint), or null when the runtime reports none.
    """

    model_config = ConfigDict(extra="allow")

    gravity: list[Number] | None = Field(
        None, description="World gravity vector in m/s^2."
    )
    scene_timestep: Number | None = Field(
        None,
        description="Timestep authored in the scene bundle, before any per-run override.",
    )
    solver_position_iterations: Integer | None = Field(
        None,
        ge=0,
        description="PhysX solver position iterations (null when the engine has none).",
    )
    solver_velocity_iterations: Integer | None = Field(
        None,
        ge=0,
        description="PhysX solver velocity iterations (null when the engine has none).",
    )
    substeps: Integer | None = Field(
        None,
        ge=1,
        description="Physics sub-steps per plant step (timestep / substeps is the solver step).",
    )


class SimulationReplayTraceV1Run(BaseModel):
    """SimulationReplayTraceV1Run"""

    model_config = ConfigDict(extra="allow")

    run_id: str = ...
    stream_instance_id: str = ...
    workload_uuid: str | None = Field(
        ..., description="Null for a run captured outside a Cyberwave workload."
    )


class SimulationReplayTraceV1Runtime(BaseModel):
    """SimulationReplayTraceV1Runtime"""

    model_config = ConfigDict(extra="allow")

    backend: Literal["mujoco", "mujoco_warp", "isaac"] = ...
    execution_profile: Literal[
        "isaac-cpu-physics", "isaac-gpu-physics", "isaac-newton-physics", None
    ] = ...
    extension_lock_digest: str | None = Field(..., pattern="^sha256:[0-9a-f]{64}$")
    image_digest: str | None = Field(..., pattern="^sha256:[0-9a-f]{64}$")
    physics_variant: str | None = ...
    runtime_version: str | None = None


class ReplayTraceNumericTolerance(BaseModel):
    """ReplayTraceNumericTolerance

    Passes when |a-b| <= abs + rel*|a|.
    """

    model_config = ConfigDict(extra="allow")

    abs: Number = Field(..., ge=0)
    rel: Number = Field(..., ge=0)


class SimulationReplayTraceV1Tolerances(BaseModel):
    """SimulationReplayTraceV1Tolerances"""

    model_config = ConfigDict(extra="allow")

    exact_fields: list[str] = Field(
        ...,
        description="Dotted field patterns that must match exactly (product contract), added to the built-in exact fields.",
    )
    image: dict[str, dict[str, Any]] = Field(
        ..., description="Field pattern -> image comparison policy."
    )
    numeric: dict[str, ReplayTraceNumericTolerance] = ...


class SimulationReplayTraceV1Timing(BaseModel):
    """SimulationReplayTraceV1Timing

    Effective per-run pacing and egress cadence (reported, not fingerprinted).
    """

    model_config = ConfigDict(extra="allow")

    range_stream_frequency_hz: Number | None = None
    realtime: Boolean | None = None
    simulation_speed: Number | None = Field(
        None,
        description="Simulated seconds per wall second when paced; null when free-running.",
    )
    stream_frequency_hz: Number | None = None


class SimulationReplayTraceV1(BaseModel):
    """Cyberwave Simulation Replay Trace

    A JSON Lines replay trace of an Isaac Sim run (and usable for MuJoCo). The first line is this header record (kind 'header'); every later line is one record whose shape is the $defs entry for its kind: command, state, lifecycle, readiness, sensor, camera_frame. A complete trace ends with a lifecycle 'stop' record. Never contains credentials or signed URLs. tolerances declares exact-match (product contract) fields and per-field numerical/image tolerances as dotted field patterns, e.g. 'state.joints.*.position'.
    """

    model_config = ConfigDict(extra="allow")

    asset_revisions: dict[str, str] = Field(..., description="asset_uuid -> revision.")
    bundle_digest: str | None = Field(..., pattern="^sha256:[0-9a-f]{64}$")
    contract: Literal["simulation.replay_trace.v1"] = ...
    duration: Number | None = Field(
        ...,
        ge=0,
        description="Scenario duration in simulated seconds, or null for an open-ended (live) run.",
    )
    initial_state: dict[str, Any] | None = Field(
        ...,
        description="Initial state (joint positions, base poses) per entity, or null when the runtime does not capture one.",
    )
    kind: Literal["header"] = ...
    physics: SimulationReplayTraceV1Physics | None = Field(
        ...,
        description="Effective physics settings the plant applied (part of the replay fingerprint), or null when the runtime reports none.",
    )
    renderer: dict[str, Any] | None = Field(
        ..., description="Renderer name/version/settings, or null when nothing renders."
    )
    run: SimulationReplayTraceV1Run = ...
    runtime: SimulationReplayTraceV1Runtime = ...
    seed: Integer = Field(
        ..., description="Seed of every stochastic source (noise, scenario)."
    )
    timestep: Number = Field(..., gt=0, description="Physics timestep in seconds.")
    tolerances: SimulationReplayTraceV1Tolerances = ...
    trace_version: Integer = Field(
        ..., ge=1, le=1, description="Always 1 for this contract version."
    )
    created_at: str | None = None
    scenario: str | None = Field(None, description="Deterministic scenario driver id.")
    source: Literal["local", "cloud", None] | None = Field(
        None, description="Where the trace was captured."
    )
    timing: SimulationReplayTraceV1Timing | None = Field(
        None,
        description="Effective per-run pacing and egress cadence (reported, not fingerprinted).",
    )


class ReplayTraceCameraFrameRecord(BaseModel):
    """ReplayTraceCameraFrameRecord

    Camera frame metadata; pixels are never inlined.
    """

    model_config = ConfigDict(extra="allow")

    checksum: str | None = Field(
        ...,
        pattern="^sha256:[0-9a-f]{64}$",
        description="'sha256:' + hex of the frame bytes, or null.",
    )
    format: str = ...
    height: Integer = Field(..., ge=1)
    kind: Literal["camera_frame"] = ...
    sensor_id: str = ...
    seq: Integer = Field(..., ge=0)
    sim_time_acq: Number = ...
    width: Integer = Field(..., ge=1)
    calibration: dict[str, Any] | None = None
    entity_id: str | None = None
    reset_epoch: Integer | None = Field(
        None,
        ge=0,
        description="Reset generation within the run; increments on every reset lifecycle event.",
    )
    run_id: str | None = Field(
        None,
        description="Run the record was produced under. Absent means the header run; a value different from the header run is a stale-run record.",
    )
    stream_instance_id: str | None = None


class ReplayTraceCommandRecord(BaseModel):
    """ReplayTraceCommandRecord

    A command applied to the plant, in application order.
    """

    model_config = ConfigDict(extra="allow")

    entity_id: str = Field(..., description="Cyberwave twin/entity id.")
    kind: Literal["command"] = ...
    payload: dict[str, Any] = Field(
        ..., description="The existing Cyberwave command payload, unchanged."
    )
    seq: Integer = Field(..., ge=0)
    sim_time_acq: Number = Field(
        ..., description="Simulation time the command was accepted."
    )
    sim_time_applied: Number | None = Field(
        ..., description="Simulation time the command took effect."
    )
    reset_epoch: Integer | None = Field(
        None,
        ge=0,
        description="Reset generation within the run; increments on every reset lifecycle event.",
    )
    run_id: str | None = Field(
        None,
        description="Run the record was produced under. Absent means the header run; a value different from the header run is a stale-run record.",
    )
    stream_instance_id: str | None = None


class ReplayTraceJointSample(BaseModel):
    """ReplayTraceJointSample"""

    model_config = ConfigDict(extra="allow")

    effort: Number | None = None
    position: Number | None = None
    velocity: Number | None = None


class ReplayTraceLifecycleRecord(BaseModel):
    """ReplayTraceLifecycleRecord

    load, start, ready, reset, pause, resume, stop or error.
    """

    model_config = ConfigDict(extra="allow")

    event: str = ...
    kind: Literal["lifecycle"] = ...
    sim_time: Number | None = ...
    detail: dict[str, Any] | None = None
    reset_epoch: Integer | None = Field(
        None,
        ge=0,
        description="Reset generation within the run; increments on every reset lifecycle event.",
    )
    run_id: str | None = Field(
        None,
        description="Run the record was produced under. Absent means the header run; a value different from the header run is a stale-run record.",
    )
    stream_instance_id: str | None = None
    wall_time: Number | None = Field(
        None, description="Unix seconds; informational, never compared exactly."
    )


class ReplayTraceReadinessRecord(BaseModel):
    """ReplayTraceReadinessRecord

    A readiness milestone (e.g. bundle_loaded, physics_ready, first_sample:<id>, ready).
    """

    model_config = ConfigDict(extra="allow")

    kind: Literal["readiness"] = ...
    milestone: str = ...
    sim_time: Number | None = ...
    reset_epoch: Integer | None = Field(
        None,
        ge=0,
        description="Reset generation within the run; increments on every reset lifecycle event.",
    )
    run_id: str | None = Field(
        None,
        description="Run the record was produced under. Absent means the header run; a value different from the header run is a stale-run record.",
    )
    stream_instance_id: str | None = None
    wall_time: Number | None = None


class ReplayTraceSensorRecord(BaseModel):
    """ReplayTraceSensorRecord

    A numerical sensor sample (imu, range, lidar, depth summary). Carries values or a summary; bulk arrays belong in a sidecar, not the trace.
    """

    model_config = ConfigDict(extra="allow")

    kind: Literal["sensor"] = ...
    sensor_id: str = ...
    seq: Integer = Field(..., ge=0)
    sim_time_acq: Number = ...
    entity_id: str | None = None
    reset_epoch: Integer | None = Field(
        None,
        ge=0,
        description="Reset generation within the run; increments on every reset lifecycle event.",
    )
    run_id: str | None = Field(
        None,
        description="Run the record was produced under. Absent means the header run; a value different from the header run is a stale-run record.",
    )
    stream_instance_id: str | None = None
    summary: dict[str, Any] | None = None
    values: dict[str, Any] | None = None


class ReplayTraceStateRecordBasePosePosition(BaseModel):
    """ReplayTraceStateRecordBasePosePosition"""

    model_config = ConfigDict(extra="allow")

    x: Number = ...
    y: Number = ...
    z: Number = ...


class ReplayTraceStateRecordBasePoseRotation(BaseModel):
    """ReplayTraceStateRecordBasePoseRotation"""

    model_config = ConfigDict(extra="allow")

    w: Number = ...
    x: Number = ...
    y: Number = ...
    z: Number = ...


class ReplayTraceStateRecordBasePose(BaseModel):
    """ReplayTraceStateRecordBasePose"""

    model_config = ConfigDict(extra="allow")

    position: ReplayTraceStateRecordBasePosePosition = ...
    rotation: ReplayTraceStateRecordBasePoseRotation = ...


class ReplayTraceStateRecordBaseTwistAngular(BaseModel):
    """ReplayTraceStateRecordBaseTwistAngular"""

    model_config = ConfigDict(extra="allow")

    x: Number = ...
    y: Number = ...
    z: Number = ...


class ReplayTraceStateRecordBaseTwistLinear(BaseModel):
    """ReplayTraceStateRecordBaseTwistLinear"""

    model_config = ConfigDict(extra="allow")

    x: Number = ...
    y: Number = ...
    z: Number = ...


class ReplayTraceStateRecordBaseTwist(BaseModel):
    """ReplayTraceStateRecordBaseTwist"""

    model_config = ConfigDict(extra="allow")

    angular: ReplayTraceStateRecordBaseTwistAngular = ...
    linear: ReplayTraceStateRecordBaseTwistLinear = ...


class ReplayTraceStateRecordBase(BaseModel):
    """ReplayTraceStateRecordBase

    Free/floating base pose and twist (world frame, meters, radians).
    """

    model_config = ConfigDict(extra="allow")

    pose: ReplayTraceStateRecordBasePose = ...
    twist: ReplayTraceStateRecordBaseTwist | None = None


class ReplayTraceStateRecord(BaseModel):
    """ReplayTraceStateRecord

    A joint/base state sample at acquisition simulation time.
    """

    model_config = ConfigDict(extra="allow")

    entity_id: str = ...
    kind: Literal["state"] = ...
    seq: Integer = Field(..., ge=0)
    sim_time: Number = Field(..., description="Acquisition simulation time.")
    base: ReplayTraceStateRecordBase | None = Field(
        None,
        description="Free/floating base pose and twist (world frame, meters, radians).",
    )
    joints: dict[str, ReplayTraceJointSample] | None = Field(
        None, description="joint name -> sample."
    )
    reset_epoch: Integer | None = Field(
        None,
        ge=0,
        description="Reset generation within the run; increments on every reset lifecycle event.",
    )
    run_id: str | None = Field(
        None,
        description="Run the record was produced under. Absent means the header run; a value different from the header run is a stale-run record.",
    )
    stream_instance_id: str | None = None
    valid: Boolean | None = None
