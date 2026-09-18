"""Cyberwave payload and configuration contracts.

A contract is a payload shape that more than one component depends on. Each is
defined once as a JSON Schema in :mod:`cyberwave_contracts.schemas`, indexed in
``manifest.yml``, and generated into a pydantic model in
:mod:`cyberwave_contracts.models`.

Validate a payload you received::

    from cyberwave_contracts import MODELS_BY_CONTRACT_ID

    model = MODELS_BY_CONTRACT_ID["locomotion.velocity_command.v1"]
    command = model.model_validate(payload)   # raises if it does not conform

Every contract payload names itself in a required const field, so a consumer
never has to infer which contract it is holding from the shape of the fields.
"""

from cyberwave_contracts.manifest import (
    MANIFEST_PATH,
    SCHEMAS_DIR,
    SHAPE_OWNERSHIP,
    Contract,
    Mirror,
    load_contracts,
    validate_ownership,
)
from cyberwave_contracts.models import (
    MODELS_BY_CONTRACT_ID,
    AerialVelocityCommandV1,
    ArtifactFile,
    LocomotionVelocityCommandV1,
    PolicyArtifactManifestV1,
    PolicyBinding,
    PolicyBindingPolicyConfig,
    PolicyBindingPolicyConfigNavigationCommandMinimums,
    PolicyBindingPolicyRef,
    SimulationPolicyManifestV1,
)

__version__ = "0.1.0"

__all__ = [
    "MANIFEST_PATH",
    "MODELS_BY_CONTRACT_ID",
    "SCHEMAS_DIR",
    "SHAPE_OWNERSHIP",
    "AerialVelocityCommandV1",
    "ArtifactFile",
    "Contract",
    "LocomotionVelocityCommandV1",
    "Mirror",
    "PolicyArtifactManifestV1",
    "PolicyBinding",
    "PolicyBindingPolicyConfig",
    "PolicyBindingPolicyConfigNavigationCommandMinimums",
    "PolicyBindingPolicyRef",
    "SimulationPolicyManifestV1",
    "__version__",
    "load_contracts",
    "validate_ownership",
]
