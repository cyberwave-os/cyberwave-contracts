# !! GENERATED from common.simulation_engine.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import RootModel


class CommonSimulationEngineV1(RootModel[Literal["mujoco", "mujoco_warp", "isaac"]]):
    """Cyberwave Simulation Engine

    The engine a simulation run starts on: the `backend` of a start request. Defined in code by cyberwave_contracts.simulation.CANONICAL_BACKENDS, which a test keeps equal to this list. `mjwarp` is accepted on input as an alias of `mujoco_warp` and is never a stored value. Not the capability flag assets and twins carry in `supported_simulation_backends`; see common.simulation_backend.v1 and ENGINE_TO_CAPABILITY_FLAG for the mapping between the two.
    """
