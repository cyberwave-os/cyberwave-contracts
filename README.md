# cyberwave-contracts

Payload and configuration contracts shared by the Cyberwave backend, SDK, edge
components and simulator.

A **contract** is a payload shape that more than one component depends on. Each is
defined once as a JSON Schema, and a pydantic model is generated from it — so the
code that validates a payload cannot drift from the schema that documents it.

```bash
pip install cyberwave-contracts   # coming with the first public release
```

Until then the package is consumed from the monorepo: the backend builds it from
its build context, and the schemas are served at `GET /api/v1/contracts`.

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

## What ships

| | |
| --- | --- |
| `cyberwave_contracts.schemas` | the JSON Schemas, usable from any language |
| `cyberwave_contracts.models` | generated pydantic models, one per schema |
| `cyberwave_contracts.manifest` | the index: every contract, its owner, and where it is mirrored |
| `cyberwave_contracts.source_type` | the authoritative decomposition of legacy `source_type` provenance |

The schemas are installed with the package, so validation works offline and
against a pinned version rather than whatever a server happened to return.

They are also served unauthenticated at `GET /api/v1/contracts` for non-Python
consumers.

## Contracts

| id | what it carries |
| --- | --- |
| `locomotion.velocity_command.v1` | body-frame velocity command for ground robots |
| `aerial.velocity_command.v1` | the same for free-body / aerial platforms |
| `policy_artifact_manifest.v1` | the files making up a policy artifact |
| `simulation_policy_manifest.v1` | policy bindings exported for a simulator |
| `source_type.envelope.v1` | flat transport overlay requiring `source_type` |

`GET /api/v1/contracts` lists what a given deployment serves.

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

## Development

```bash
make models     # regenerate the pydantic models from the schemas
```

Generated output is committed, so consumers need no build step. CI fails if a
schema changes without the models being regenerated.

Runtime dependencies are deliberately limited to `pydantic` and `pyyaml`: this
package is imported by every Cyberwave component, so anything added here is added
to all of them.

## License

Apache-2.0
