# !! GENERATED from simulation_policy_manifest.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cyberwave_contracts.models._scalars import Boolean, Number


class PolicyBindingPolicyConfigNavigationCommandMinimums(BaseModel):
    """PolicyBindingPolicyConfigNavigationCommandMinimums

    Measured nonzero command floors for waypoint tracking only. Requested planar speed, yaw limits and the trained command envelope still win. Does not alter manual input, stop or expiry. Absent means unchanged legacy tracking.
    """

    model_config = ConfigDict(extra="forbid")

    ang_vel_z: Number | None = Field(None, ge=0)
    lin_vel_x: Number | None = Field(None, ge=0)
    lin_vel_y: Number | None = Field(None, ge=0)


class PolicyBindingPolicyConfig(BaseModel):
    """PolicyBindingPolicyConfig"""

    model_config = ConfigDict(extra="allow")

    actuator_model: str = Field(
        "pd",
        description="Trained actuator dynamics. The onnx_joint_policy runner supports pd and actuator_net_lstm. The latter requires a validated control.actuator_lstm.v1 actuator_network artifact, trained timestep and effort model. Missing or incompatible dynamics must not silently fall back to PD.",
    )
    navigation_command_minimums: (
        PolicyBindingPolicyConfigNavigationCommandMinimums | None
    ) = Field(
        None,
        description="Measured nonzero command floors for waypoint tracking only. Requested planar speed, yaw limits and the trained command envelope still win. Does not alter manual input, stop or expiry. Absent means unchanged legacy tracking.",
    )
    navigation_minimum_activation: Number | None = Field(
        None,
        gt=0,
        description="Only apply a calibrated floor when the absolute waypoint command exceeds this threshold. Smaller commands retain their original value; this is not a manual-input dead zone.",
    )

    @model_validator(mode="after")
    def _check_dependent_required(self) -> PolicyBindingPolicyConfig:
        """Schema `dependentRequired`: one key present requires another.

        Presence, not truthiness -- `model_fields_set` is the set of
        keys the payload carried, so an explicit null still counts.
        """
        for trigger, dependents in (
            ("navigation_command_minimums", ("navigation_minimum_activation",)),
        ):
            if trigger not in self.model_fields_set:
                continue
            missing = [d for d in dependents if d not in self.model_fields_set]
            if missing:
                raise ValueError(f"{trigger} requires {', '.join(missing)}")
        return self


class PolicyBindingPolicyRef(BaseModel):
    """PolicyBindingPolicyRef"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["uuid", "catalog_seed_id", "slug"] = ...
    value: str = ...


class PolicyBinding(BaseModel):
    """PolicyBinding"""

    model_config = ConfigDict(extra="allow")

    runtime_kind: Literal["simulation"] = ...
    simulation_backend: str = ...
    twin_uuid: str = ...
    adapter: str | None = None
    artifact_manifest: dict[str, Any] | None = None
    asset_registry_id: str | None = None
    asset_uuid: str | None = None
    controller_policy_catalog_key: str | None = None
    controller_policy_uuid: str | None = None
    enabled: Boolean | None = None
    execution_contract: str | None = None
    mlmodel_uuid: str | None = None
    output_contract: str | None = None
    policy_config: PolicyBindingPolicyConfig | None = None
    policy_ref: PolicyBindingPolicyRef | None = None
    reason: str | None = Field(
        None,
        description="Why the configured runtime cannot execute this policy, when known.",
    )
    twin_name: str | None = None


class SimulationPolicyManifestV1(BaseModel):
    """Cyberwave Simulation Policy Manifest

    Backend-exported simulation policy bindings for MuJoCo and future simulation runtimes.
    """

    model_config = ConfigDict(extra="allow")

    environment_uuid: str = ...
    generated_at: str = ...
    policies: list[PolicyBinding] = ...
    runtime_kind: Literal["simulation"] = ...
    sha256: str = ...
    simulation_backend: str = ...
    version: Literal["simulation_policy_manifest.v1"] = ...
