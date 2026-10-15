# !! GENERATED from simulation.hardware_qualification.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Integer


class SimulationHardwareQualificationV1Checks(BaseModel):
    """SimulationHardwareQualificationV1Checks"""

    model_config = ConfigDict(extra="allow")

    driver: Literal["pass", "fail", "skipped"] | None = Field(
        None, description="nvidia-smi reported a valid driver version."
    )
    runtime_probe: Literal["pass", "fail", "skipped"] | None = Field(
        None,
        description="NVIDIA compatibility checker, headless Kit start, RTX render, physics steps, encode and clean shutdown.",
    )
    vram: Literal["pass", "fail", "skipped"] | None = None


class SimulationHardwareQualificationV1(BaseModel):
    """Cyberwave Simulation Hardware Qualification

    The hardware fingerprint an Isaac Sim worker's qualification probe records. A worker joins the Isaac pool only while its latest record has status 'pass', an RT-core NVIDIA GPU with a 16 GB card (at least 15872 MiB reported total VRAM, see MIN_ISAAC_VRAM_MIB), a resolved plant image digest (matching the expected one where the platform sets it), and a checked_at within the freshness window. There is no GPU-model list and no driver pin. The worker stores its latest record in its cloud-node metadata under 'hardware_qualification'. The schema accepts failing records so a probe can report why it failed; cyberwave_contracts.simulation.check_hardware_qualification decides whether a record qualifies, failing closed. Contains no credentials, hostnames or URLs.
    """

    model_config = ConfigDict(extra="allow")

    checked_at: str = Field(
        ...,
        description="RFC 3339 UTC timestamp of the probe run. A record older than the freshness window is stale.",
    )
    contract: Literal["simulation.hardware_qualification.v1"] = ...
    driver: str = Field(..., description="NVIDIA Linux driver version, e.g. '580.178'.")
    gpu_model: str = Field(
        ...,
        description="GPU model as the driver reports it, e.g. 'NVIDIA GeForce RTX 5070 Ti'.",
    )
    image_digest: str | None = Field(
        ...,
        pattern="^sha256:[0-9a-f]{64}$",
        description="Digest of the Isaac plant image the runtime probe ran. A record without one never qualifies.",
    )
    probe_version: str = Field(
        ..., description="Version of the qualification probe that produced this record."
    )
    rt_cores: Boolean = Field(
        ...,
        description="Whether the GPU has RT cores. Isaac Sim does not run without them (e.g. A100, H100).",
    )
    status: Literal["pass", "fail"] = Field(
        ..., description="'pass' only when every check passed."
    )
    vram_mib: Integer = Field(
        ...,
        ge=0,
        description="Total VRAM of the GPU assigned to Isaac workloads, in MiB.",
    )
    checks: SimulationHardwareQualificationV1Checks | None = None
    execution_profiles: (
        list[Literal["isaac-cpu-physics", "isaac-gpu-physics", "isaac-newton-physics"]]
        | None
    ) = Field(
        None,
        description="Execution profiles whose physics the runtime probe stepped. When present, a worker qualifies only for these; when absent, for every profile.",
    )
    failures: list[str] | None = Field(
        None, description="Human-readable reasons for a 'fail' status."
    )
    provisional: Boolean | None = Field(
        None,
        description="True when a development-mode probe waived checks a production node must pass (a runtime probe that was not run). A provisional record qualifies only where the platform explicitly allows it (Cyberwave's internal development and test deployments).",
    )
    provisional_reasons: list[str] | None = Field(
        None, description="The checks a provisional record waived."
    )
