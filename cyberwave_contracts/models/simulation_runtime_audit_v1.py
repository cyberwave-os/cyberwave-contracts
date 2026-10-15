# !! GENERATED from simulation.runtime_audit.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean


class SimulationRuntimeAuditV1Gpu(BaseModel):
    """SimulationRuntimeAuditV1Gpu"""

    model_config = ConfigDict(extra="allow")

    driver: str = ...
    name: str = ...
    renderer: str | None = ...


class RuntimeAuditMismatch(BaseModel):
    """RuntimeAuditMismatch"""

    model_config = ConfigDict(extra="allow")

    expected: str | None = ...
    field: str = ...
    reported: str | None = ...
    code: str | None = None


class SimulationRuntimeAuditV1Physics(BaseModel):
    """SimulationRuntimeAuditV1Physics"""

    model_config = ConfigDict(extra="allow")

    device: Literal["cpu", "gpu"] = ...
    engine: str = Field(
        ...,
        description="Engine the runtime actually steps: physx or newton for isaac (see cyberwave_contracts.simulation.EXECUTION_PROFILE_PHYSICS), mujoco for the MuJoCo worker. A string, not an enum, so an unexpected engine is reported as a mismatch rather than rejected.",
    )
    variant: str | None = ...


class SimulationRuntimeAuditV1(BaseModel):
    """Cyberwave Simulation Runtime Audit

    What a running simulation plant reports about itself. ready is true only when the reported backend equals the requested backend, the execution profile and feature profile match the workload, the bundle/image digests match, and every required capability is 'ok' (first valid sample received). mismatches lists every reason it is not. See cyberwave_contracts.simulation.check_runtime_audit.
    """

    model_config = ConfigDict(extra="allow")

    bundle_digest: str | None = Field(
        ..., pattern="^sha256:[0-9a-f]{64}$", description="Loaded scene bundle digest."
    )
    capabilities: dict[str, Literal["ok", "missing", "pending", "failed"]] = Field(
        ..., description="Capability (sensor id, modality or state stream) -> status."
    )
    contract: Literal["simulation.runtime_audit.v1"] = ...
    execution_profile: str | None = Field(
        ..., description="Execution profile the runtime actually runs."
    )
    exporter_version: str | None = ...
    extension_lock_digest: str | None = Field(..., pattern="^sha256:[0-9a-f]{64}$")
    feature_profile_id: str | None = Field(
        ..., description="profile_id@version of the implemented feature profile."
    )
    gpu: SimulationRuntimeAuditV1Gpu | None = ...
    image_digest: str | None = Field(
        ..., pattern="^sha256:[0-9a-f]{64}$", description="Container image digest."
    )
    mismatches: list[RuntimeAuditMismatch] = ...
    physics: SimulationRuntimeAuditV1Physics = ...
    ready: Boolean = ...
    reported_backend: str = Field(
        ...,
        description="Backend the runtime actually runs. A string, not the enum, so an unexpected value can be reported as a mismatch rather than rejected.",
    )
    requested_backend: Literal["mujoco", "mujoco_warp", "isaac"] = ...
    run_id: str = Field(
        ..., description="Execution identity of this run; changes on every start."
    )
    stream_instance_id: str = Field(
        ..., description="Media/stream identity of this run."
    )
    workload_uuid: str = ...
    error_code: str | None = Field(
        None,
        description="Stable error code when not ready, e.g. simulation_backend_runtime_mismatch.",
    )
    reported_at: str | None = Field(None, description="RFC 3339 UTC timestamp.")
    requested_execution_profile: (
        Literal["isaac-cpu-physics", "isaac-gpu-physics", "isaac-newton-physics", None]
        | None
    ) = None
