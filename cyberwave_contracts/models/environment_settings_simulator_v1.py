# !! GENERATED from environment.settings.simulator.v1.schema.json -- do not edit.

from __future__ import annotations

from pydantic import RootModel

from cyberwave_contracts.models.common_simulation_engine_v1 import (
    CommonSimulationEngineV1,
)


class EnvironmentSettingsSimulatorV1(RootModel[CommonSimulationEngineV1]):
    """Environment default simulator

    The engine an environment's simulation starts on when a start request names none; unset means mujoco, and a start request's own backend overrides it. Stored as a bare string. Rows written before the contract may hold the alias mjwarp, playground, an empty string or different casing; observe mode reports them.
    """
