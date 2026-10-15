# !! GENERATED from simulation.feature_profile.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Integer, Number


class SimulationFeatureProfileV1Limits(BaseModel):
    """SimulationFeatureProfileV1Limits

    Declared operating limits. Open for additive limits.
    """

    model_config = ConfigDict(extra="allow")

    max_camera_fps: Number | None = Field(None, ge=0)
    max_camera_height: Integer | None = Field(None, ge=0)
    max_camera_width: Integer | None = Field(None, ge=0)
    max_cameras: Integer | None = Field(None, ge=0)
    max_lidar_rays: Integer | None = Field(None, ge=0)
    max_twins: Integer | None = Field(None, ge=0)
    physics_timestep_s: Number | None = Field(None, gt=0)


class SimulationFeatureProfileV1Media(BaseModel):
    """SimulationFeatureProfileV1Media"""

    model_config = ConfigDict(extra="allow")

    recording: Boolean = Field(
        ..., description="Existing recording selection and run association work."
    )
    webrtc: Boolean = Field(
        ..., description="Frames enter the existing Cyberwave WebRTC/media path."
    )


class SimulationFeatureProfileV1Readiness(BaseModel):
    """SimulationFeatureProfileV1Readiness"""

    model_config = ConfigDict(extra="allow")

    required_first_samples: list[str] = Field(
        ...,
        description="Capabilities (sensor ids, modalities or state streams) whose first valid sample is required before the runtime reports ready.",
    )


class SimulationFeatureProfileV1(BaseModel):
    """Cyberwave Simulation Feature Profile

    The versioned set of control modes, state fields, sensor modalities, media and readiness requirements a simulation runtime must satisfy for a workload. Identified by (profile_id, version); a runtime reports the profile it implements in simulation.runtime_audit.v1.feature_profile_id. Not an options map: every requirement is a named field.
    """

    model_config = ConfigDict(extra="allow")

    backend: Literal["mujoco", "mujoco_warp", "isaac"] = Field(
        ..., description="Canonical simulation backend the profile applies to."
    )
    contract: Literal["simulation.feature_profile.v1"] = ...
    control_modes: list[str] = Field(
        ...,
        description="Mandatory Cyberwave control modes, by existing command name (e.g. joint_position, joint_velocity, gripper, locomotion_velocity, aerial_velocity, gimbal). Each mode must be mapped explicitly per asset; an unmapped mode fails preflight and is never approximated.",
    )
    execution_profile: Literal[
        "isaac-cpu-physics", "isaac-gpu-physics", "isaac-newton-physics", None
    ] = Field(
        ...,
        description="Isaac execution profile, or null for backends without execution profiles.",
    )
    limits: SimulationFeatureProfileV1Limits = Field(
        ..., description="Declared operating limits. Open for additive limits."
    )
    media: SimulationFeatureProfileV1Media = ...
    profile_id: str = Field(
        ...,
        description="Stable identifier of this profile, e.g. 'isaac.core'. Combined with version it names an immutable requirement set.",
    )
    readiness: SimulationFeatureProfileV1Readiness = ...
    sensor_modalities: list[
        Literal[
            "rgb",
            "depth",
            "imu",
            "lidar",
            "range",
            "point_cloud",
            "first_person_camera",
            "sim_viewport",
        ]
    ] = Field(
        ...,
        description="Mandatory sensor modalities; a listed modality the scene does not provide reports missing at readiness. Thermal and audio are not profile modalities: the Isaac runtime renders thermal cameras and routes microphones and speakers for whichever twins declare them, without a profile entry. New modalities are added to this enum additively.",
    )
    state_fields: list[str] = Field(
        ...,
        description="Mandatory state fields by dotted name (e.g. joint.position, joint.velocity, joint.effort, base.pose, base.twist).",
    )
    version: Integer = Field(..., ge=1, description="Monotonic profile version.")
