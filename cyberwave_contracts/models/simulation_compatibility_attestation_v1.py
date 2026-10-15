# !! GENERATED from simulation.compatibility_attestation.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SimulationCompatibilityAttestationV1Evidence(BaseModel):
    """SimulationCompatibilityAttestationV1Evidence"""

    model_config = ConfigDict(extra="allow")

    kind: str = Field(..., description="e.g. replay_trace, diff_report, log, video")
    location: str = Field(
        ...,
        description="Opaque reference (artifact id or bucket-relative path). Never a signed URL.",
    )
    sha256: str | None = Field(None, pattern="^[0-9a-f]{64}$")


class SimulationCompatibilityAttestationV1Key(BaseModel):
    """SimulationCompatibilityAttestationV1Key"""

    model_config = ConfigDict(extra="allow")

    asset_revision: str | None = ...
    asset_uuid: str | None = ...
    backend: Literal["mujoco", "mujoco_warp", "isaac"] = ...
    bundle_digest: str | None = Field(..., pattern="^sha256:[0-9a-f]{64}$")
    config_revision: str | None = ...
    controller_revision: str | None = ...
    environment_revision: str | None = ...
    environment_uuid: str | None = ...
    execution_profile: Literal[
        "isaac-cpu-physics", "isaac-gpu-physics", "isaac-newton-physics", None
    ] = ...
    exporter_version: str | None = ...
    extension_lock_digest: str | None = Field(..., pattern="^sha256:[0-9a-f]{64}$")
    feature_profile_id: str = ...
    image_digest: str | None = Field(..., pattern="^sha256:[0-9a-f]{64}$")
    physics_engine: str | None = Field(
        ...,
        description="Engine the suite ran, e.g. physx or newton; must be the one execution_profile selects. Attestations are per execution profile, so a Newton pass never implies a PhysX pass and vice versa.",
    )
    physics_variant: str | None = ...
    resource_envelope: dict[str, Any] | None = Field(
        ..., description="Machine/GPU/driver class the evidence was produced on."
    )
    runtime_version: str | None = ...
    test_suite_revision: str = ...


class SimulationCompatibilityAttestationV1Tests(BaseModel):
    """SimulationCompatibilityAttestationV1Tests"""

    model_config = ConfigDict(extra="allow")

    status: Literal["passed", "failed", "skipped"] = ...
    test_id: str = ...
    detail: str | None = None
    evidence_ref: str | None = None


class SimulationCompatibilityAttestationV1(BaseModel):
    """Cyberwave Simulation Compatibility Attestation

    Evidence that an asset revision (or assembled environment) passed the compatibility suite for one backend, feature profile and execution profile under exact bundle/exporter/runtime/extension/physics fingerprints. Any change to a key field invalidates it. key_digest is 'sha256:' + hex sha256 of the canonical JSON of key (see cyberwave_contracts.simulation.attestation_key_digest). Evidence locations are opaque references, never signed URLs.
    """

    model_config = ConfigDict(extra="allow")

    attestation_id: str = ...
    contract: Literal["simulation.compatibility_attestation.v1"] = ...
    evidence: list[SimulationCompatibilityAttestationV1Evidence] = ...
    expires_at: str | None = Field(
        ..., description="RFC 3339 UTC timestamp, or null for no time-based expiry."
    )
    issued_at: str = Field(..., description="RFC 3339 UTC timestamp.")
    key: SimulationCompatibilityAttestationV1Key = ...
    key_digest: str = Field(..., pattern="^sha256:[0-9a-f]{64}$")
    reason: str | None = Field(
        ..., description="Why the status is what it is (failure, invalidation trigger)."
    )
    status: Literal["pending", "passed", "failed", "expired", "invalidated"] = ...
    tests: list[SimulationCompatibilityAttestationV1Tests] = ...
    tolerances: dict[str, Any] = Field(
        ...,
        description="Tolerances the tests were evaluated against (same shape as replay trace tolerances).",
    )
    invalidated_at: str | None = None
