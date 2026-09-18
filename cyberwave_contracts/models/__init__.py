"""Pydantic models generated from the contract schemas in ``cyberwave_contracts/schemas``.

Generated, not written -- this file included: run ``make -C cyberwave-contracts
models``. A model here cannot drift from the schema it came from, which is the
whole reason it exists -- the backend's ``test_contract_conformance.py`` measures
the hand-written checks against these and fails on any undeclared disagreement.

Import the model, never re-implement the rule it carries.
"""

from cyberwave_contracts.models.aerial_velocity_command_v1 import (
    AerialVelocityCommandV1,
)
from cyberwave_contracts.models.locomotion_velocity_command_v1 import (
    LocomotionVelocityCommandV1,
)
from cyberwave_contracts.models.policy_artifact_manifest_v1 import (
    ArtifactFile,
    PolicyArtifactManifestV1,
)
from cyberwave_contracts.models.simulation_policy_manifest_v1 import (
    PolicyBinding,
    PolicyBindingPolicyConfig,
    PolicyBindingPolicyConfigNavigationCommandMinimums,
    PolicyBindingPolicyRef,
    SimulationPolicyManifestV1,
)

#: Contract id -> its root model. Keyed so a caller can walk the manifest
#: and find the model for each indexed contract without a second mapping
#: to keep in step with it.
MODELS_BY_CONTRACT_ID = {
    "aerial.velocity_command.v1": AerialVelocityCommandV1,
    "locomotion.velocity_command.v1": LocomotionVelocityCommandV1,
    "policy_artifact_manifest.v1": PolicyArtifactManifestV1,
    "simulation_policy_manifest.v1": SimulationPolicyManifestV1,
}

__all__ = [
    "AerialVelocityCommandV1",
    "ArtifactFile",
    "LocomotionVelocityCommandV1",
    "MODELS_BY_CONTRACT_ID",
    "PolicyArtifactManifestV1",
    "PolicyBinding",
    "PolicyBindingPolicyConfig",
    "PolicyBindingPolicyConfigNavigationCommandMinimums",
    "PolicyBindingPolicyRef",
    "SimulationPolicyManifestV1",
]
