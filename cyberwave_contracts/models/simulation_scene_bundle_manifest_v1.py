# !! GENERATED from simulation.scene_bundle_manifest.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Integer, Number


class SimulationSceneBundleManifestV1Articulations(BaseModel):
    """SimulationSceneBundleManifestV1Articulations"""

    model_config = ConfigDict(extra="allow")

    base: Literal["fixed", "floating"] = ...
    root_usd_path: str = Field(..., pattern="^(/[A-Za-z_][A-Za-z0-9_]*)+$")
    twin_uuid: str = ...
    drives: list[dict[str, Any]] | None = None
    reset: dict[str, Any] | None = Field(
        None,
        description="Initial/reset state declaration (joint positions, base pose).",
    )


class SceneBundleFinding(BaseModel):
    """SceneBundleFinding"""

    model_config = ConfigDict(extra="allow")

    code: str = Field(..., description="Stable machine-readable code.")
    message: str = Field(..., description="Human-readable detail.")
    asset_uuid: str | None = None
    subject: str | None = Field(
        None, description="Link, joint, sensor or file the finding is about."
    )
    twin_uuid: str | None = None


class SimulationSceneBundleManifestV1Compatibility(BaseModel):
    """SimulationSceneBundleManifestV1Compatibility"""

    model_config = ConfigDict(extra="allow")

    errors: list[SceneBundleFinding] = ...
    rejected_features: list[SceneBundleFinding] = ...
    warnings: list[SceneBundleFinding] = ...


class SimulationSceneBundleManifestV1Exporter(BaseModel):
    """SimulationSceneBundleManifestV1Exporter"""

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="e.g. cyberwave-robot-format")
    usd_schema_version: str = Field(
        ..., description="Version of the Cyberwave USD schema authored."
    )
    version: str = ...


class SceneBundleFile(BaseModel):
    """SceneBundleFile"""

    model_config = ConfigDict(extra="allow")

    path: str = Field(
        ...,
        pattern="^\\.?[A-Za-z0-9_+@=-][A-Za-z0-9_.+@=-]*(/\\.?[A-Za-z0-9_+@=-][A-Za-z0-9_.+@=-]*)*$",
        description="Confined relative POSIX path.",
    )
    sha256: str = Field(
        ...,
        pattern="^[0-9a-f]{64}$",
        description="Lowercase hex sha256 of the file bytes.",
    )
    size: Integer = Field(..., ge=0, description="Size in bytes.")


class SimulationSceneBundleManifestV1IdentityMapCameras(BaseModel):
    """SimulationSceneBundleManifestV1IdentityMapCameras"""

    model_config = ConfigDict(extra="allow")

    camera_id: str = ...
    role: Literal["sensor", "first_person", "sim_viewport"] = ...
    twin_uuid: str | None = Field(
        ..., description="Null for environment cameras such as sim_viewport."
    )
    usd_path: str = Field(..., pattern="^(/[A-Za-z_][A-Za-z0-9_]*)+$")
    sensor_id: str | None = None


class SimulationSceneBundleManifestV1IdentityMapJoints(BaseModel):
    """SimulationSceneBundleManifestV1IdentityMapJoints"""

    model_config = ConfigDict(extra="allow")

    dof_index: Integer = Field(..., ge=0)
    joint: str = Field(
        ..., description="Cyberwave joint name as used in commands and state."
    )
    twin_uuid: str = ...
    usd_path: str = Field(..., pattern="^(/[A-Za-z_][A-Za-z0-9_]*)+$")


class SimulationSceneBundleManifestV1IdentityMapLinks(BaseModel):
    """SimulationSceneBundleManifestV1IdentityMapLinks"""

    model_config = ConfigDict(extra="allow")

    link: str = ...
    twin_uuid: str = ...
    usd_path: str = Field(..., pattern="^(/[A-Za-z_][A-Za-z0-9_]*)+$")


class SimulationSceneBundleManifestV1IdentityMapSensors(BaseModel):
    """SimulationSceneBundleManifestV1IdentityMapSensors"""

    model_config = ConfigDict(extra="allow")

    kind: Literal[
        "rgb",
        "depth",
        "imu",
        "lidar",
        "range",
        "point_cloud",
        "first_person_camera",
        "sim_viewport",
    ] = ...
    sensor_id: str = ...
    twin_uuid: str | None = ...
    usd_path: str = Field(..., pattern="^(/[A-Za-z_][A-Za-z0-9_]*)+$")


class SimulationSceneBundleManifestV1IdentityMapTwins(BaseModel):
    """SimulationSceneBundleManifestV1IdentityMapTwins"""

    model_config = ConfigDict(extra="allow")

    twin_uuid: str = ...
    usd_path: str = Field(..., pattern="^(/[A-Za-z_][A-Za-z0-9_]*)+$")


class SimulationSceneBundleManifestV1IdentityMapMaterials(BaseModel):
    """SimulationSceneBundleManifestV1IdentityMapMaterials"""

    model_config = ConfigDict(extra="allow")

    material_id: str = ...
    usd_path: str = Field(..., pattern="^(/[A-Za-z_][A-Za-z0-9_]*)+$")


class SimulationSceneBundleManifestV1IdentityMap(BaseModel):
    """SimulationSceneBundleManifestV1IdentityMap

    Stable Cyberwave-identity to USD prim path maps. USD paths are prim paths inside the stage, not filesystem paths.
    """

    model_config = ConfigDict(extra="allow")

    cameras: list[SimulationSceneBundleManifestV1IdentityMapCameras] = ...
    joints: list[SimulationSceneBundleManifestV1IdentityMapJoints] = ...
    links: list[SimulationSceneBundleManifestV1IdentityMapLinks] = ...
    sensors: list[SimulationSceneBundleManifestV1IdentityMapSensors] = ...
    twins: list[SimulationSceneBundleManifestV1IdentityMapTwins] = ...
    materials: list[SimulationSceneBundleManifestV1IdentityMapMaterials] | None = None


class SimulationSceneBundleManifestV1PhysicsIsaac(BaseModel):
    """SimulationSceneBundleManifestV1PhysicsIsaac

    Isaac solver settings from the environment's Physics.extensions['isaac_physics'] (validated by cyberwave_contracts.simulation.normalize_isaac_physics). Omitted when the environment sets none; the plant then keeps the engine defaults.
    """

    model_config = ConfigDict(extra="forbid")

    solver_position_iterations: Integer | None = Field(
        None,
        ge=1,
        le=255,
        description="PhysX scene min and max position iteration count.",
    )
    solver_velocity_iterations: Integer | None = Field(
        None,
        ge=0,
        le=255,
        description="PhysX scene min and max velocity iteration count.",
    )
    substeps: Integer | None = Field(
        None, ge=1, le=64, description="Physics sub-steps per plant step."
    )


class SimulationSceneBundleManifestV1Physics(BaseModel):
    """SimulationSceneBundleManifestV1Physics"""

    model_config = ConfigDict(extra="allow")

    engine: Literal["physx", "newton"] = Field(
        ...,
        description="Physics engine the scene was authored and validated for. Isaac Sim's Newton engine reads the same UsdPhysics scene, so a 'physx' bundle may also list isaac-newton-physics in supported_execution_profiles; the execution profile, not this field, selects the engine at run time (see cyberwave_contracts.simulation.physics_for_execution_profile).",
    )
    supported_execution_profiles: list[
        Literal["isaac-cpu-physics", "isaac-gpu-physics", "isaac-newton-physics"]
    ] = ...
    variant: str = Field(
        ..., description="Explicit engine/USD variant the scene was authored for."
    )
    isaac: SimulationSceneBundleManifestV1PhysicsIsaac | None = Field(
        None,
        description="Isaac solver settings from the environment's Physics.extensions['isaac_physics'] (validated by cyberwave_contracts.simulation.normalize_isaac_physics). Omitted when the environment sets none; the plant then keeps the engine defaults.",
    )


class SimulationSceneBundleManifestV1Provenance(BaseModel):
    """SimulationSceneBundleManifestV1Provenance"""

    model_config = ConfigDict(extra="allow")

    attestation_ref: str | None = Field(
        ...,
        description="Opaque reference to a signature/attestation record; never a URL.",
    )
    toolchain: dict[str, str] = Field(
        ..., description="Tool name -> version used to author the bundle."
    )


class SimulationSceneBundleManifestV1ResourceEstimate(BaseModel):
    """SimulationSceneBundleManifestV1ResourceEstimate

    Aggregate estimate used by scheduling preflight.
    """

    model_config = ConfigDict(extra="allow")

    cpu_cores: Number | None = Field(None, ge=0)
    disk_mb: Number | None = Field(None, ge=0)
    gpu_required: Boolean | None = Field(
        None, description="True when rendering/cameras require an RTX GPU."
    )
    ram_mb: Number | None = Field(None, ge=0)
    vram_mb: Number | None = Field(None, ge=0)


class SimulationSceneBundleManifestV1Runtime(BaseModel):
    """SimulationSceneBundleManifestV1Runtime"""

    model_config = ConfigDict(extra="allow")

    extension_lock_digest: str | None = Field(
        ...,
        pattern="^sha256:[0-9a-f]{64}$",
        description="Digest of the Kit extension lock, or null when unpinned.",
    )
    isaac_version: str = Field(
        ..., description="Isaac Sim version the bundle was validated for."
    )


class SimulationSceneBundleManifestV1Sensors(BaseModel):
    """SimulationSceneBundleManifestV1Sensors"""

    model_config = ConfigDict(extra="allow")

    fidelity: str = Field(
        ...,
        description="Fidelity label, e.g. 'geometric_ray', 'rendered', 'heuristic'. Never implies more physical fidelity than implemented.",
    )
    kind: Literal[
        "rgb",
        "depth",
        "imu",
        "lidar",
        "range",
        "point_cloud",
        "first_person_camera",
        "sim_viewport",
    ] = ...
    params: dict[str, Any] = Field(
        ...,
        description="Kind-specific descriptor (rate, resolution, range, intrinsics, noise).",
    )
    sensor_id: str = ...
    twin_uuid: str | None = ...


class SceneBundleSourceAsset(BaseModel):
    """SceneBundleSourceAsset"""

    model_config = ConfigDict(extra="allow")

    asset_uuid: str = ...
    content_hash: str | None = ...
    registry_id: str | None = ...
    revision: str = ...


class SimulationSceneBundleManifestV1Source(BaseModel):
    """SimulationSceneBundleManifestV1Source"""

    model_config = ConfigDict(extra="allow")

    assets: list[SceneBundleSourceAsset] = ...
    environment_revision: str = Field(
        ...,
        description="Revision/version token of the environment the bundle was built from.",
    )
    environment_uuid: str = ...


class SimulationSceneBundleManifestV1Units(BaseModel):
    """SimulationSceneBundleManifestV1Units"""

    model_config = ConfigDict(extra="allow")

    kilograms_per_unit: Number = Field(
        ..., ge=1.0, le=1.0, description="Always 1.0 (kilograms)."
    )
    meters_per_unit: Number = Field(
        ..., ge=1.0, le=1.0, description="Always 1.0 (meters)."
    )
    up_axis: Literal["Z"] = ...


class SimulationSceneBundleManifestV1(BaseModel):
    """Cyberwave Simulation Scene Bundle Manifest

    Manifest of an immutable, self-contained OpenUSD scene bundle exported from Cyberwave Format. Every path is relative to the bundle root and confined to it (no leading '/', no '..' segment, no scheme). bundle_digest is 'sha256:' + hex sha256 over the canonical file list (see cyberwave_contracts.simulation.compute_bundle_digest); the manifest file itself is not listed in files. A referenced dependency missing from files is fatal. The manifest never carries URLs, signed URLs, credentials or authorization claims.
    """

    model_config = ConfigDict(extra="allow")

    articulations: list[SimulationSceneBundleManifestV1Articulations] = ...
    bundle_digest: str = Field(
        ...,
        pattern="^sha256:[0-9a-f]{64}$",
        description="'sha256:' + lowercase hex sha256 over the canonical file list.",
    )
    compatibility: SimulationSceneBundleManifestV1Compatibility = ...
    contract: Literal["simulation.scene_bundle_manifest.v1"] = ...
    created_at: str = Field(..., description="RFC 3339 UTC timestamp of the export.")
    exporter: SimulationSceneBundleManifestV1Exporter = ...
    files: list[SceneBundleFile] = Field(
        ..., description="Every file in the bundle except the manifest."
    )
    identity_map: SimulationSceneBundleManifestV1IdentityMap = Field(
        ...,
        description="Stable Cyberwave-identity to USD prim path maps. USD paths are prim paths inside the stage, not filesystem paths.",
    )
    physics: SimulationSceneBundleManifestV1Physics = ...
    provenance: SimulationSceneBundleManifestV1Provenance = ...
    resource_estimate: SimulationSceneBundleManifestV1ResourceEstimate = Field(
        ..., description="Aggregate estimate used by scheduling preflight."
    )
    root_layer: str = Field(
        ...,
        pattern="^\\.?[A-Za-z0-9_+@=-][A-Za-z0-9_.+@=-]*(/\\.?[A-Za-z0-9_+@=-][A-Za-z0-9_.+@=-]*)*$",
        description="Root USD layer, a confined relative path that is also listed in files.",
    )
    runtime: SimulationSceneBundleManifestV1Runtime = ...
    schema_version: Integer = Field(
        ..., ge=1, le=1, description="Always 1 for this contract version."
    )
    sensors: list[SimulationSceneBundleManifestV1Sensors] = ...
    source: SimulationSceneBundleManifestV1Source = ...
    units: SimulationSceneBundleManifestV1Units = ...
