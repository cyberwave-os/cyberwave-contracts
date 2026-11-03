# !! GENERATED from common.simulation_backend.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import RootModel


class CommonSimulationBackendV1(
    RootModel[Literal["playground", "mujoco", "mjwarp", "isaac"]]
):
    """Cyberwave Simulation Backend Flag

    A capability flag an asset or twin carries in `supported_simulation_backends`, and the one a policy names in `preferred_simulation_backend`: which simulators the robot is known to work in. A different vocabulary from common.simulation_engine.v1 on purpose: `playground` is a flag with no engine, and the engine `mujoco_warp` is the flag `mjwarp`. `isaac` is set by the asset author like `mujoco`; a compatibility attestation is optional evidence. ENGINE_TO_CAPABILITY_FLAG in the backend maps engines to flags.
    """
