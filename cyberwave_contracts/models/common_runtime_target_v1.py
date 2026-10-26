# !! GENERATED from common.runtime_target.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean


class CommonRuntimeTargetV1(BaseModel):
    """Cyberwave Controller Runtime Target

    Where and how a controller policy runs for one runtime kind: whether it is enabled, the backend that executes it, and the contracts it reads and writes. Resolved by the backend from a policy's metadata and returned in controller setup views.
    """

    model_config = ConfigDict(extra="allow")

    backend: str = Field(
        ...,
        description="The runtime backend that executes the policy (for example `edge` or a simulation backend name).",
    )
    enabled: Boolean = Field(
        ..., description="False when this runtime kind is switched off for the policy."
    )
    runtime_kind: Literal["physical", "simulation"] = Field(
        ..., description="Whether the policy drives a real robot or a simulated one."
    )
    adapter: str | None = Field(
        None, description="The execution adapter, when the policy needs one."
    )
    input_contract: str | None = Field(
        None, description="The contract id of what the policy consumes."
    )
    metadata: dict[str, Any] | None = Field(
        None, description="Open, adapter-specific data."
    )
    output_contract: str | None = Field(
        None, description="The contract id of what the policy produces."
    )
    safety_level: str | None = Field(
        None, description="The safety classification of the target, when one applies."
    )
    source_type: str | None = Field(
        None,
        description="The source_type the runtime publishes under (see source_type.envelope.v1).",
    )
