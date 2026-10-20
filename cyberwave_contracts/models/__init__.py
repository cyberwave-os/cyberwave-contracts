"""Pydantic models generated from the contract schemas in ``cyberwave_contracts/schemas``.

Generated, not written -- this file included: run ``make -C cyberwave-contracts
models``. A model here cannot drift from the schema it came from, which is the
whole reason it exists -- the backend's ``test_contract_conformance.py`` measures
the hand-written checks against these and fails on any undeclared disagreement.

Import the model, never re-implement the rule it carries.
"""

from cyberwave_contracts.models.aerial_mission_v1 import (
    AerialMissionV1,
    MissionHome,
    MissionItem,
)
from cyberwave_contracts.models.aerial_velocity_command_v1 import (
    AerialVelocityCommandV1,
)
from cyberwave_contracts.models.environment_settings_geo_v1 import (
    EnvironmentSettingsGeoV1,
)
from cyberwave_contracts.models.locomotion_velocity_command_v1 import (
    LocomotionVelocityCommandV1,
)
from cyberwave_contracts.models.policy_artifact_manifest_v1 import (
    ArtifactFile,
    PolicyArtifactManifestV1,
)
from cyberwave_contracts.models.simulation_compatibility_attestation_v1 import (
    SimulationCompatibilityAttestationV1,
    SimulationCompatibilityAttestationV1Evidence,
    SimulationCompatibilityAttestationV1Key,
    SimulationCompatibilityAttestationV1Tests,
)
from cyberwave_contracts.models.simulation_feature_profile_v1 import (
    SimulationFeatureProfileV1,
    SimulationFeatureProfileV1Limits,
    SimulationFeatureProfileV1Media,
    SimulationFeatureProfileV1Readiness,
)
from cyberwave_contracts.models.simulation_hardware_qualification_v1 import (
    SimulationHardwareQualificationV1,
    SimulationHardwareQualificationV1Checks,
)
from cyberwave_contracts.models.simulation_replay_trace_v1 import (
    ReplayTraceCameraFrameRecord,
    ReplayTraceCommandRecord,
    ReplayTraceJointSample,
    ReplayTraceLifecycleRecord,
    ReplayTraceNumericTolerance,
    ReplayTraceReadinessRecord,
    ReplayTraceSensorRecord,
    ReplayTraceStateRecord,
    ReplayTraceStateRecordBase,
    ReplayTraceStateRecordBasePose,
    ReplayTraceStateRecordBasePosePosition,
    ReplayTraceStateRecordBasePoseRotation,
    ReplayTraceStateRecordBaseTwist,
    ReplayTraceStateRecordBaseTwistAngular,
    ReplayTraceStateRecordBaseTwistLinear,
    SimulationReplayTraceV1,
    SimulationReplayTraceV1Physics,
    SimulationReplayTraceV1Run,
    SimulationReplayTraceV1Runtime,
    SimulationReplayTraceV1Timing,
    SimulationReplayTraceV1Tolerances,
)
from cyberwave_contracts.models.simulation_runtime_audit_v1 import (
    RuntimeAuditMismatch,
    SimulationRuntimeAuditV1,
    SimulationRuntimeAuditV1Gpu,
    SimulationRuntimeAuditV1Physics,
)
from cyberwave_contracts.models.simulation_scene_bundle_manifest_v1 import (
    SceneBundleFile,
    SceneBundleFinding,
    SceneBundleSourceAsset,
    SimulationSceneBundleManifestV1,
    SimulationSceneBundleManifestV1Articulations,
    SimulationSceneBundleManifestV1Compatibility,
    SimulationSceneBundleManifestV1Exporter,
    SimulationSceneBundleManifestV1IdentityMap,
    SimulationSceneBundleManifestV1IdentityMapCameras,
    SimulationSceneBundleManifestV1IdentityMapJoints,
    SimulationSceneBundleManifestV1IdentityMapLinks,
    SimulationSceneBundleManifestV1IdentityMapMaterials,
    SimulationSceneBundleManifestV1IdentityMapSensors,
    SimulationSceneBundleManifestV1IdentityMapTwins,
    SimulationSceneBundleManifestV1Physics,
    SimulationSceneBundleManifestV1PhysicsIsaac,
    SimulationSceneBundleManifestV1Provenance,
    SimulationSceneBundleManifestV1ResourceEstimate,
    SimulationSceneBundleManifestV1Runtime,
    SimulationSceneBundleManifestV1Sensors,
    SimulationSceneBundleManifestV1Source,
    SimulationSceneBundleManifestV1Units,
)
from cyberwave_contracts.models.simulation_policy_manifest_v1 import (
    PolicyBinding,
    PolicyBindingPolicyConfig,
    PolicyBindingPolicyConfigNavigationCommandMinimums,
    PolicyBindingPolicyRef,
    SimulationPolicyManifestV1,
)
from cyberwave_contracts.models.source_type_envelope_v1 import (
    SourceTypeEnvelopeV1,
)
from cyberwave_contracts.models.twin_battery_v1 import (
    TwinBatteryV1,
)
from cyberwave_contracts.models.twin_command_response_v1 import (
    TwinCommandResponseV1,
)
from cyberwave_contracts.models.twin_flight_controller_v1 import (
    TwinFlightControllerV1,
    TwinFlightControllerV1Home,
    TwinFlightControllerV1Link,
    TwinFlightControllerV1Mission,
    TwinFlightControllerV1StatusTexts,
)
from cyberwave_contracts.models.twin_flight_state_v1 import (
    TwinFlightStateV1,
)

#: Contract id -> its root model. Keyed so a caller can walk the manifest
#: and find the model for each indexed contract without a second mapping
#: to keep in step with it.
MODELS_BY_CONTRACT_ID = {
    "aerial.mission.v1": AerialMissionV1,
    "aerial.velocity_command.v1": AerialVelocityCommandV1,
    "environment.settings.geo.v1": EnvironmentSettingsGeoV1,
    "locomotion.velocity_command.v1": LocomotionVelocityCommandV1,
    "policy_artifact_manifest.v1": PolicyArtifactManifestV1,
    "simulation.compatibility_attestation.v1": SimulationCompatibilityAttestationV1,
    "simulation.feature_profile.v1": SimulationFeatureProfileV1,
    "simulation.hardware_qualification.v1": SimulationHardwareQualificationV1,
    "simulation.replay_trace.v1": SimulationReplayTraceV1,
    "simulation.runtime_audit.v1": SimulationRuntimeAuditV1,
    "simulation.scene_bundle_manifest.v1": SimulationSceneBundleManifestV1,
    "simulation_policy_manifest.v1": SimulationPolicyManifestV1,
    "source_type.envelope.v1": SourceTypeEnvelopeV1,
    "twin.battery.v1": TwinBatteryV1,
    "twin.command_response.v1": TwinCommandResponseV1,
    "twin.flight_controller.v1": TwinFlightControllerV1,
    "twin.flight_state.v1": TwinFlightStateV1,
}

__all__ = [
    "AerialMissionV1",
    "AerialVelocityCommandV1",
    "ArtifactFile",
    "EnvironmentSettingsGeoV1",
    "LocomotionVelocityCommandV1",
    "MODELS_BY_CONTRACT_ID",
    "MissionHome",
    "MissionItem",
    "PolicyArtifactManifestV1",
    "PolicyBinding",
    "PolicyBindingPolicyConfig",
    "PolicyBindingPolicyConfigNavigationCommandMinimums",
    "PolicyBindingPolicyRef",
    "ReplayTraceCameraFrameRecord",
    "ReplayTraceCommandRecord",
    "ReplayTraceJointSample",
    "ReplayTraceLifecycleRecord",
    "ReplayTraceNumericTolerance",
    "ReplayTraceReadinessRecord",
    "ReplayTraceSensorRecord",
    "ReplayTraceStateRecord",
    "ReplayTraceStateRecordBase",
    "ReplayTraceStateRecordBasePose",
    "ReplayTraceStateRecordBasePosePosition",
    "ReplayTraceStateRecordBasePoseRotation",
    "ReplayTraceStateRecordBaseTwist",
    "ReplayTraceStateRecordBaseTwistAngular",
    "ReplayTraceStateRecordBaseTwistLinear",
    "RuntimeAuditMismatch",
    "SceneBundleFile",
    "SceneBundleFinding",
    "SceneBundleSourceAsset",
    "SimulationCompatibilityAttestationV1",
    "SimulationCompatibilityAttestationV1Evidence",
    "SimulationCompatibilityAttestationV1Key",
    "SimulationCompatibilityAttestationV1Tests",
    "SimulationFeatureProfileV1",
    "SimulationFeatureProfileV1Limits",
    "SimulationFeatureProfileV1Media",
    "SimulationFeatureProfileV1Readiness",
    "SimulationHardwareQualificationV1",
    "SimulationHardwareQualificationV1Checks",
    "SimulationPolicyManifestV1",
    "SimulationReplayTraceV1",
    "SimulationReplayTraceV1Physics",
    "SimulationReplayTraceV1Run",
    "SimulationReplayTraceV1Runtime",
    "SimulationReplayTraceV1Timing",
    "SimulationReplayTraceV1Tolerances",
    "SimulationRuntimeAuditV1",
    "SimulationRuntimeAuditV1Gpu",
    "SimulationRuntimeAuditV1Physics",
    "SimulationSceneBundleManifestV1",
    "SimulationSceneBundleManifestV1Articulations",
    "SimulationSceneBundleManifestV1Compatibility",
    "SimulationSceneBundleManifestV1Exporter",
    "SimulationSceneBundleManifestV1IdentityMap",
    "SimulationSceneBundleManifestV1IdentityMapCameras",
    "SimulationSceneBundleManifestV1IdentityMapJoints",
    "SimulationSceneBundleManifestV1IdentityMapLinks",
    "SimulationSceneBundleManifestV1IdentityMapMaterials",
    "SimulationSceneBundleManifestV1IdentityMapSensors",
    "SimulationSceneBundleManifestV1IdentityMapTwins",
    "SimulationSceneBundleManifestV1Physics",
    "SimulationSceneBundleManifestV1PhysicsIsaac",
    "SimulationSceneBundleManifestV1Provenance",
    "SimulationSceneBundleManifestV1ResourceEstimate",
    "SimulationSceneBundleManifestV1Runtime",
    "SimulationSceneBundleManifestV1Sensors",
    "SimulationSceneBundleManifestV1Source",
    "SimulationSceneBundleManifestV1Units",
    "SourceTypeEnvelopeV1",
    "TwinBatteryV1",
    "TwinCommandResponseV1",
    "TwinFlightControllerV1",
    "TwinFlightControllerV1Home",
    "TwinFlightControllerV1Link",
    "TwinFlightControllerV1Mission",
    "TwinFlightControllerV1StatusTexts",
    "TwinFlightStateV1",
]
