# cyberwave-contracts

Payload and configuration contracts shared by the Cyberwave backend, SDK, edge
components and simulator.

A **contract** is a payload shape that more than one component depends on. Each is
defined once as a JSON Schema, and a pydantic model is generated from it — so the
code that validates a payload cannot drift from the schema that documents it.

```bash
pip install cyberwave-contracts
```

This repository is a read-only mirror of the `cyberwave-contracts/` directory of
the Cyberwave monorepo, published on every production release; issues are
welcome, but changes land upstream. Inside the monorepo the backend, the edge
images and the simulator install the package from the checkout rather than from
PyPI, and the schemas are also served at `GET /api/v1/contracts`.

## Validating a payload

```python
from cyberwave_contracts import MODELS_BY_CONTRACT_ID

model = MODELS_BY_CONTRACT_ID["locomotion.velocity_command.v1"]
command = model.model_validate(payload)      # raises ValidationError if malformed

command.linear_x     # typed float, autocompletes
command.gait         # Literal["walk", "trot", "stand"]
```

Every contract payload names itself in a required field, so you never have to
infer which contract you are holding from the shape of the fields:

```python
model = MODELS_BY_CONTRACT_ID[payload["contract"]]
```

The one exception is the flat twin telemetry topics (`twin.flight_state.v1` and
the others under [Twin telemetry topics](#twin-telemetry-topics)): their
publishers predate the rule and send no contract id, so the topic identifies the
contract. Each of those schemas names its topic in an `x-mqtt-topic` annotation.

## What ships

| | |
| --- | --- |
| `cyberwave_contracts.schemas` | the JSON Schemas, usable from any language |
| `cyberwave_contracts.sections` | section contracts: one part of a stored JSON field (see below) |
| `cyberwave_contracts.models` | generated pydantic models, one per schema |
| `cyberwave_contracts.manifest` | the index: every contract, its owner, and where it is mirrored |
| `cyberwave_contracts.source_type` | the authoritative decomposition of legacy `source_type` provenance |
| `cyberwave_contracts.locomotion` | the locomotion and aerial velocity commands: normalising, clamping, building and stopping them (standard library only) |
| `cyberwave_contracts.simulation` | simulation backend identity (`mujoco`, `mujoco_warp`, `isaac`), Isaac execution profiles and the physics engine/device each selects (`isaac-cpu-physics`, `isaac-gpu-physics`, experimental `isaac-newton-physics`), scene-bundle digests and path confinement, runtime-audit readiness checks, the hardware-qualification check (a VRAM floor, no GPU-model list, no driver pin), and run fencing (standard library only) |
| `cyberwave_contracts.trace` | write, read, validate and diff `simulation.replay_trace.v1` traces; `python -m cyberwave_contracts.trace diff a.jsonl b.jsonl` reports the first divergence (standard library only) |

The schemas are installed with the package, so validation works offline and
against a pinned version rather than whatever a server happened to return.

They are also served unauthenticated at `GET /api/v1/contracts` for non-Python
consumers.

## Contracts

| id | what it carries |
| --- | --- |
| `locomotion.velocity_command.v1` | body-frame velocity command for ground robots |
| `aerial.velocity_command.v1` | the same for free-body / aerial platforms |
| `aerial.mission.v1` | a flight plan: planned home, altitude reference and waypoint / loiter / RTL / land-start items |
| `policy_artifact_manifest.v1` | the files making up a policy artifact |
| `simulation_policy_manifest.v1` | policy bindings exported for a simulator |
| `source_type.envelope.v1` | flat transport overlay requiring `source_type` |
| `twin.command_response.v1` | the reply to a twin command sent over MQTT v5 request/response |
| `twin.flight_controller.v1` | an aircraft's autopilot state: armed, mode, failsafe, link, mission progress, home |
| `twin.flight_state.v1` | whether an aircraft is airborne, as the aircraft reports it |
| `twin.battery.v1` | a robot's own battery reading |
| `simulation.feature_profile.v1` | what a simulation backend/execution profile supports: control modes, state fields, sensors, media, limits, readiness |
| `simulation.scene_bundle_manifest.v1` | an immutable, content-addressed simulation scene bundle: files, digest, identity map, physics, units, provenance |
| `simulation.runtime_audit.v1` | what a running simulation runtime reports about itself, and whether it matches what was requested |
| `simulation.compatibility_attestation.v1` | evidence that an asset/environment passed a backend's conformance suite under an exact runtime key |
| `simulation.replay_trace.v1` | a JSON Lines replay trace: a header, then command, state, lifecycle, readiness, sensor and camera-frame records |
| `simulation.hardware_qualification.v1` | the hardware fingerprint an Isaac worker's qualification probe records (RT-core GPU, VRAM, driver, image digest, probe version, time); stored in the node's metadata under `hardware_qualification` |

`GET /api/v1/contracts` lists what a given deployment serves.

## Sections

A section contract describes one part of a JSON field stored on a Cyberwave
object -- for example `Environment.settings.geo` -- rather than a message on the
wire. Its manifest entry has `kind: section` and, instead of an identity field:

- `location`: where the section is stored, as `Entity.field[.path]`;
- `section_kind`: `configuration`, `catalog`, `reported`, `derived` or
  `bookkeeping`, which says who may write it;
- `merge` (asset sections only): how a twin inherits it -- `instance_only` (the
  default), `replace`, `narrow_only`, `seed_once` or `precedence_chain`.

A section's own object is closed, so a misspelt key is an error. Section schemas
ship in `sections/` with generated models, and are not listed by
`GET /api/v1/contracts`.

| id | location |
| --- | --- |
| `environment.settings.geo.v1` | `Environment.settings.geo` |

## Transport envelope

MQTT payloads keep their existing flat JSON shape. The v1 transport envelope
requires only `source_type` and preserves every domain field beside it:

```python
from cyberwave_contracts import SourceTypeEnvelopeV1

envelope = SourceTypeEnvelopeV1.model_validate(
    {"source_type": "tele", "command": "move_forward", "data": {}}
)
```

Domain payload models inherit this generated model, so one `payload_schema`
validation checks both the routing discriminator and topic-specific fields. This
keeps routing metadata owned by the transport layer without nesting or duplicating
it in every domain contract. The semantic decomposition remains in
`source_type_axes.yml` and is checked against the schema vocabulary.

## Versioning

A contract id ends in its version (`…v1`). Within a version, changes are
**additive only** — a payload valid against `v1` stays valid. A field that becomes
required, an enum value that is removed, or a type that narrows is a new version.

Contract roots accept unknown properties, so a newer publisher can add fields your
version has not heard of, and your model keeps them rather than dropping them on a
round-trip.

CI enforces this: `python -m cyberwave_contracts._compat --base <revision>`
compares every schema with its previous version. Payloads must stay compatible in
both directions, because producers and consumers upgrade at different times;
sections must stay readable by the new version, because stored rows outlive the
code that wrote them.

## Development

```bash
make models               # regenerate the pydantic models from the schemas
make compat BASE=<git-rev>   # check schema changes are compatible with BASE
```

Generated output is committed, so consumers need no build step. CI fails if a
schema changes without the models being regenerated.

Runtime dependencies are deliberately limited to `pydantic` and `pyyaml`: this
package is imported by every Cyberwave component, so anything added here is added
to all of them.

## License

Apache-2.0

## Command request/response over MQTT v5

A twin command (`{prefix}cyberwave/twin/{twin_uuid}/command`) is fire-and-forget
over MQTT 3.1.1. Over MQTT v5 a caller can ask for the outcome instead of
guessing it:

1. **Requester** connects with MQTT v5 and subscribes, for each twin it will
   command, to its own reply inbox under that twin:
   `{prefix}cyberwave/twin/{twin_uuid}/command/{client_id}/response`. The broker
   lets only the client with that client id read it, so other readers of the
   twin (including `twin/{twin_uuid}/#` subscribers) never see the reply.
2. It publishes the command with two v5 properties:
   - **Response Topic** `{prefix}cyberwave/twin/{twin_uuid}/command/{client_id}/response`
   - **Correlation Data**: opaque bytes, unique per request (e.g. a UUID).
3. **Handler** (the twin's driver) publishes exactly one
   `twin.command_response.v1` payload to that Response Topic, QoS 1, echoing the
   Correlation Data. Publishing there is an ordinary write to the twin, so one
   twin's driver cannot answer for another; the handler also ignores a Response
   Topic that is not this twin's reply inbox.
4. The requester matches the reply by Correlation Data. `status` tells it what
   happened: `accepted`, `rejected` (refused before reaching the device),
   `denied` (the device refused, with `reason` and the device's `messages`) or
   `timeout`.

A request without a Response Topic is handled exactly as before and gets no
reply, so MQTT 3.1.1 publishers are unaffected. Requesters should still bound
their wait: a handler that predates this contract never replies.

## Twin telemetry topics

Three contracts describe telemetry a driver publishes on a flat twin topic, all
relative to the environment prefix:

| topic | contract | required |
| --- | --- | --- |
| `cyberwave/twin/{twin_uuid}/flight_controller` | `twin.flight_controller.v1` | `type`, `source_type`, `timestamp`, `armed`, `mode`, `failsafe` |
| `cyberwave/twin/{twin_uuid}/flight_state` | `twin.flight_state.v1` | `source_type`, `timestamp`, `is_flying` |
| `cyberwave/twin/{twin_uuid}/battery/status` | `twin.battery.v1` | `source_type`, `timestamp`, `percentage` |

```python
from cyberwave_contracts import MODELS_BY_CONTRACT_ID

state = MODELS_BY_CONTRACT_ID["twin.flight_state.v1"].model_validate(payload)
```

`source_type` says where the reading came from: `edge` for a real vehicle, `sim`
for a simulated one (for example an autopilot running in SITL). Publish `sim`
from a simulator rather than `edge`; consumers keep the two apart.

`twin.flight_controller.v1` covers what every autopilot driver reports. A
driver may add fields of its own beside them; the root stays open, and those
fields are not part of the contract. `mode` is the firmware's own mode name, for
display: compare `custom_mode` together with `autopilot` when you need the raw
value.

A `battery/status` `percentage` is 0-100, never a 0-1 fraction. A publisher that
cannot measure a percentage, or a voltage, omits the field rather than sending 0.

## Aerial missions

`aerial.mission.v1` is a flight plan as an operator states it: a planned home
(latitude, longitude, ground altitude AMSL), what item altitudes are measured
from (`home`, `amsl` or `terrain`) and the items in flight order:

| `type` | MAVLink command | fields |
| --- | --- | --- |
| `waypoint` | `MAV_CMD_NAV_WAYPOINT` | position, `altitude_m`, `acceptance_radius_m` |
| `loiter_time` | `MAV_CMD_NAV_LOITER_TIME` | position, `altitude_m`, `seconds`, `direction` |
| `loiter_turns` | `MAV_CMD_NAV_LOITER_TURNS` | position, `altitude_m`, `turns` (1-255), `radius_m`, `direction` |
| `loiter_unlimited` | `MAV_CMD_NAV_LOITER_UNLIM` | position, `altitude_m`, `radius_m`, `direction` |
| `return_to_launch` | `MAV_CMD_NAV_RETURN_TO_LAUNCH` | none |
| `land_start` | `MAV_CMD_DO_LAND_START` | optional position |

```python
from cyberwave_contracts import MODELS_BY_CONTRACT_ID

mission = MODELS_BY_CONTRACT_ID["aerial.mission.v1"].model_validate(
    {
        "contract": "aerial.mission.v1",
        "name": "north field",
        "home": {"latitude": 45.56, "longitude": 12.24, "altitude_amsl_m": 10.0},
        "default_altitude_m": 100,
        "items": [
            {"type": "waypoint", "latitude": 45.565, "longitude": 12.245},
            {"type": "loiter_turns", "latitude": 45.565, "longitude": 12.235,
             "turns": 2, "radius_m": 70, "direction": "ccw"},
            {"type": "return_to_launch"},
        ],
    }
)
```

The plan carries intent, not the vehicle: bank limit, airspeeds, endurance,
default loiter radius and RTL altitude come from the twin's capabilities. The
schema fixes the shape; whether a plan is flyable (altitude band, turn
geometry, operating areas, terrain clearance, endurance including the way home)
is decided by the platform's plan validation. Loiter rules follow what ArduPilot
flies: `loiter_time` always uses the vehicle's default loiter radius, so it takes
no `radius_m`; `loiter_turns` counts whole turns. Nothing may follow
`return_to_launch` or `loiter_unlimited`.
