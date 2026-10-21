"""Cyberwave payload and configuration contracts.

A contract is a payload shape that more than one component depends on. Each is
defined once as a JSON Schema in :mod:`cyberwave_contracts.schemas`, indexed in
``manifest.yml``, and generated into a pydantic model in
:mod:`cyberwave_contracts.models`.

Validate a payload you received::

    from cyberwave_contracts import MODELS_BY_CONTRACT_ID

    model = MODELS_BY_CONTRACT_ID["locomotion.velocity_command.v1"]
    command = model.model_validate(payload)   # raises if it does not conform

Complete payload contracts name themselves in a required const field, so a
consumer never has to infer which contract it is holding from its shape. Overlay
contracts constrain shared fields on those payloads without adding another wire
identity field. Topic contracts -- the flat twin telemetry topics, whose deployed
publishers predate the rule -- are identified by the MQTT topic their schema names
in ``x-mqtt-topic``.
"""

from cyberwave_contracts.manifest import (
    MANIFEST_PATH,
    MERGE_STRATEGIES,
    SCHEMAS_DIR,
    SECTION_KINDS,
    SECTIONS_DIR,
    SHAPE_OWNERSHIP,
    Contract,
    Mirror,
    load_contracts,
    validate_ownership,
    validate_section,
    split_location,
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
    SourceTypeEnvelopeV1,
)
from cyberwave_contracts.source_type import (
    SOURCE_TYPE_AXES_PATH,
    SOURCE_TYPE_EDGE,
    SOURCE_TYPE_EDGE_FOLLOWER,
    SOURCE_TYPE_EDGE_LEADER,
    SOURCE_TYPE_EDIT,
    SOURCE_TYPE_SIM,
    SOURCE_TYPE_SIM_TELE,
    SOURCE_TYPE_TELE,
    SOURCE_TYPE_VALUES,
    SourceType,
    load_source_type_axes,
    source_types_where,
)

__version__ = "0.1.2"

__all__ = [
    "MANIFEST_PATH",
    "MERGE_STRATEGIES",
    "MODELS_BY_CONTRACT_ID",
    "SCHEMAS_DIR",
    "SECTIONS_DIR",
    "SECTION_KINDS",
    "SOURCE_TYPE_AXES_PATH",
    "SOURCE_TYPE_EDGE",
    "SOURCE_TYPE_EDGE_FOLLOWER",
    "SOURCE_TYPE_EDGE_LEADER",
    "SOURCE_TYPE_EDIT",
    "SOURCE_TYPE_SIM",
    "SOURCE_TYPE_SIM_TELE",
    "SOURCE_TYPE_TELE",
    "SOURCE_TYPE_VALUES",
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
    "SourceType",
    "SourceTypeEnvelopeV1",
    "__version__",
    "load_contracts",
    "load_source_type_axes",
    "source_types_where",
    "split_location",
    "validate_ownership",
    "validate_section",
]
