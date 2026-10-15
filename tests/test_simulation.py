"""Simulation backend identity, scene-bundle digests and confinement, runtime
readiness and run fencing (``cyberwave_contracts.simulation``)."""

from __future__ import annotations

import ast
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cyberwave_contracts import simulation as sim

FIXTURES = Path(__file__).parent / "fixtures" / "simulation"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_module_is_stdlib_only_and_imports_no_simulator() -> None:
    tree = ast.parse(Path(sim.__file__).read_text(encoding="utf-8"))
    imported = {
        (node.module or "").split(".")[0]
        if isinstance(node, ast.ImportFrom)
        else alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported <= {
        "__future__",
        "hashlib",
        "json",
        "os",
        "re",
        "collections",
        "dataclasses",
        "datetime",
        "pathlib",
        "typing",
    }


# -- backend identity ------------------------------------------------------------


def test_frozen_identifiers() -> None:
    assert sim.CANONICAL_BACKENDS == ("mujoco", "mujoco_warp", "isaac")
    assert sim.EXECUTION_PROFILES == (
        "isaac-cpu-physics",
        "isaac-gpu-physics",
        "isaac-newton-physics",
    )
    assert sim.DEFAULT_ISAAC_EXECUTION_PROFILE == "isaac-cpu-physics"
    assert sim.EXPERIMENTAL_EXECUTION_PROFILES == {"isaac-newton-physics"}
    assert sim.PHYSICS_ENGINES == ("physx", "newton")
    assert sim.CLOUD_NODE_PROFILE_MUJOCO == "mujoco-sim"
    assert sim.CLOUD_NODE_PROFILE_ISAAC == "isaac-sim"
    assert sim.ERROR_CODES == (
        "simulation_backend_unsupported",
        "simulation_backend_not_enabled",
        "simulation_backend_incompatible",
        "simulation_backend_runtime_mismatch",
        "simulation_backend_capacity_unavailable",
        "simulation_parameter_unsupported",
        "simulation_parameter_invalid",
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "mujoco"),
        ("mujoco", "mujoco"),
        ("mujoco_warp", "mujoco_warp"),
        ("mjwarp", "mujoco_warp"),
        (" Isaac ", "isaac"),
    ],
)
def test_normalize_backend(value: str | None, expected: str) -> None:
    assert sim.normalize_backend(value) == expected


@pytest.mark.parametrize(
    "value", ["", "  ", "isaacsim", "mujoco-warp", "physx", "MuJoCo2", 1, True]
)
def test_normalize_backend_fails_closed(value: object) -> None:
    with pytest.raises(ValueError) as caught:
        sim.normalize_backend(value)  # type: ignore[arg-type]
    assert isinstance(caught.value, sim.UnsupportedSimulationBackendError)
    assert caught.value.code == "simulation_backend_unsupported"


def test_execution_profile_rules() -> None:
    assert sim.normalize_execution_profile("isaac", None) == "isaac-cpu-physics"
    assert (
        sim.normalize_execution_profile("isaac", "isaac-gpu-physics")
        == "isaac-gpu-physics"
    )
    assert (
        sim.normalize_execution_profile("isaac", " Isaac-Newton-Physics ")
        == "isaac-newton-physics"
    )
    assert sim.normalize_execution_profile("mujoco", None) is None
    for backend, profile in (
        ("mujoco", "isaac-cpu-physics"),
        ("mujoco_warp", "isaac-newton-physics"),
        ("isaac", "gpu"),
        ("isaac", "newton"),
        ("isaac", "isaac-newton-cpu-physics"),
        ("isaac", ""),
    ):
        with pytest.raises(sim.SimulationContractError) as caught:
            sim.normalize_execution_profile(backend, profile)
        assert caught.value.code == "simulation_backend_unsupported"


@pytest.mark.parametrize(
    ("profile", "engine", "device"),
    [
        ("isaac-cpu-physics", "physx", "cpu"),
        ("isaac-gpu-physics", "physx", "gpu"),
        ("isaac-newton-physics", "newton", "gpu"),
    ],
)
def test_execution_profile_physics_round_trips(
    profile: str, engine: str, device: str
) -> None:
    assert sim.physics_for_execution_profile(profile) == sim.PhysicsSelection(
        engine, device
    )
    assert sim.execution_profile_for_physics(engine, device) == profile


def test_every_execution_profile_maps_to_physics() -> None:
    assert set(sim.EXECUTION_PROFILE_PHYSICS) == set(sim.EXECUTION_PROFILES)
    for selection in sim.EXECUTION_PROFILE_PHYSICS.values():
        assert selection.engine in sim.PHYSICS_ENGINES
        assert selection.device in sim.PHYSICS_DEVICES


def test_physics_mapping_fails_closed() -> None:
    # Newton runs on the GPU only: no profile is Newton-on-CPU.
    assert sim.execution_profile_for_physics("newton", "cpu") is None
    assert sim.execution_profile_for_physics("mujoco", "cpu") is None
    assert sim.execution_profile_for_physics(None, None) is None
    with pytest.raises(sim.SimulationContractError) as caught:
        sim.physics_for_execution_profile("isaac-warp-physics")
    assert caught.value.code == "simulation_backend_unsupported"


# -- confinement and digests -----------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "scene.usda",
        "assets/robot/meshes/base_link.usdc",
        "a/.keep",
        "textures/wood+oak@2x.png",
        "a..b/c",
    ],
)
def test_confined_paths(path: str) -> None:
    assert sim.is_confined_relative_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/etc/passwd",
        "../secret",
        "a/../../b",
        "a/./b",
        "a//b",
        "a/",
        "C:/x.usda",
        "C:\\x.usda",
        "https://example.com/x.usda",
        "a b.usda",
        "scene.usda\n",
        "~/x",
        None,
    ],
)
def test_unconfined_paths(path: object) -> None:
    assert not sim.is_confined_relative_path(path)
    with pytest.raises(ValueError):
        sim.validate_bundle_path(path)


def test_bundle_digest_is_order_independent_and_content_sensitive() -> None:
    files = _load("scene_bundle_manifest.valid.json")["files"]
    digest = sim.compute_bundle_digest(files)
    assert digest.startswith("sha256:") and len(digest) == 71
    assert sim.compute_bundle_digest(list(reversed(files))) == digest
    changed = [dict(files[0], size=files[0]["size"] + 1), *files[1:]]
    assert sim.compute_bundle_digest(changed) != digest
    renamed = [dict(files[0], path="scene2.usda"), *files[1:]]
    assert sim.compute_bundle_digest(renamed) != digest


def test_bundle_digest_known_value() -> None:
    # Pins the canonical form: "<sha256> <size> <path>\n" sorted by UTF-8 path.
    files = [
        {"path": "b.usda", "sha256": "1" * 64, "size": 2},
        {"path": "a.usda", "sha256": "0" * 64, "size": 1},
    ]
    import hashlib

    canonical = f"{'0' * 64} 1 a.usda\n{'1' * 64} 2 b.usda\n".encode()
    assert (
        sim.compute_bundle_digest(files)
        == "sha256:" + hashlib.sha256(canonical).hexdigest()
    )


@pytest.mark.parametrize(
    "files",
    [
        [
            {"path": "a", "sha256": "0" * 64, "size": 1},
            {"path": "a", "sha256": "1" * 64, "size": 1},
        ],
        [{"path": "a", "sha256": "A" * 64, "size": 1}],
        [{"path": "a", "sha256": "0" * 64, "size": -1}],
        [{"path": "a", "sha256": "0" * 64, "size": True}],
        [{"path": "../a", "sha256": "0" * 64, "size": 1}],
    ],
)
def test_bundle_digest_refuses_ambiguous_input(files: list[dict]) -> None:
    with pytest.raises(ValueError):
        sim.compute_bundle_digest(files)


def test_hash_bundle_files_matches_digest_and_refuses_symlinks(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "scene.usda").write_text("#usda 1.0\n")
    (tmp_path / "assets" / "robot.usda").write_text("#usda 1.0\n")
    (tmp_path / "manifest.json").write_text("{}")
    files = sim.hash_bundle_files(tmp_path)
    assert [f["path"] for f in files] == ["assets/robot.usda", "scene.usda"]
    assert sim.compute_bundle_digest(files).startswith("sha256:")

    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("secret")
    try:
        os.symlink(outside, tmp_path / "assets" / "escape.usda")
        with pytest.raises(ValueError, match="not a regular file"):
            sim.hash_bundle_files(tmp_path)
    finally:
        outside.unlink()


def test_valid_manifest_has_no_problems() -> None:
    assert sim.validate_bundle_manifest(_load("scene_bundle_manifest.valid.json")) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda m: m["files"].__setitem__(0, dict(m["files"][0], path="/abs.usda")),
            "not a confined relative path",
        ),
        (lambda m: m.__setitem__("root_layer", "missing.usda"), "not listed in files"),
        (
            lambda m: m["files"].append(dict(m["files"][0], path="Scene.usda")),
            "case-insensitively",
        ),
        (
            lambda m: m.__setitem__("bundle_digest", "sha256:" + "0" * 64),
            "does not match",
        ),
        (
            lambda m: m["sensors"][0]["params"].__setitem__(
                "uri", "https://bucket/x?X-Goog-Signature=abc"
            ),
            "credential-like",
        ),
        (
            lambda m: m["provenance"].__setitem__(
                "attestation_ref", "https://cyberwave.com/a/1"
            ),
            "URL not allowed",
        ),
        (lambda m: m["provenance"].__setitem__("api_key", "x"), "credential-like key"),
        (
            lambda m: m["identity_map"]["twins"].append(
                dict(m["identity_map"]["twins"][0])
            ),
            "duplicate identity",
        ),
        (
            lambda m: m["identity_map"]["joints"][0].__setitem__("usd_path", "World/x"),
            "invalid prim path",
        ),
    ],
)
def test_manifest_problems(mutate, expected: str) -> None:
    manifest = _load("scene_bundle_manifest.valid.json")
    mutate(manifest)
    problems = sim.validate_bundle_manifest(manifest)
    assert any(expected in p for p in problems), problems


# -- runtime readiness -----------------------------------------------------------


def test_runtime_audit_ready() -> None:
    audit = _load("runtime_audit.valid.json")
    check = sim.check_runtime_audit(
        audit,
        expected_bundle_digest=audit["bundle_digest"],
        expected_image_digest=audit["image_digest"],
        expected_feature_profile_id="isaac-cpu-physics.v1",
        required_capabilities=["state", "camera:rgb"],
    )
    assert check and check.ready and check.mismatches == () and check.error_code is None


@pytest.mark.parametrize(
    ("change", "kwargs", "field", "code"),
    [
        (
            {"reported_backend": "mujoco"},
            {},
            "reported_backend",
            "simulation_backend_runtime_mismatch",
        ),
        (
            {"execution_profile": "isaac-gpu-physics"},
            {},
            "execution_profile",
            "simulation_backend_runtime_mismatch",
        ),
        (
            {},
            {"expected_bundle_digest": "sha256:" + "0" * 64},
            "bundle_digest",
            "simulation_backend_runtime_mismatch",
        ),
        (
            {"bundle_digest": None},
            {},
            "bundle_digest",
            "simulation_backend_runtime_mismatch",
        ),
        (
            {"capabilities": {"state": "pending", "joint_command": "ok"}},
            {},
            "capabilities.state",
            None,
        ),
        ({}, {"required_capabilities": ["lidar"]}, "capabilities.lidar", None),
        ({"capabilities": {}}, {}, "capabilities", None),
        (
            {"requested_backend": "isaacsim"},
            {},
            "requested_backend",
            "simulation_backend_unsupported",
        ),
    ],
)
def test_runtime_audit_mismatches(
    change: dict, kwargs: dict, field: str, code: str | None
) -> None:
    audit = {**_load("runtime_audit.valid.json"), **change}
    check = sim.check_runtime_audit(audit, **kwargs)
    assert not check
    assert any(m["field"] == field and m["code"] == code for m in check.mismatches), (
        check.mismatches
    )


def test_newton_runtime_audit_ready_with_physics_verified() -> None:
    audit = _load("runtime_audit.valid.newton.json")
    check = sim.check_runtime_audit(
        audit,
        requested_execution_profile="isaac-newton-physics",
        verify_physics=True,
    )
    assert check.ready, check.mismatches


@pytest.mark.parametrize(
    ("fixture", "physics", "field"),
    [
        # Claims the Newton profile while stepping PhysX.
        ("runtime_audit.valid.newton.json", {"engine": "physx"}, "physics.engine"),
        # Claims GPU PhysX while stepping on the CPU.
        ("runtime_audit.valid.json", {"device": "cpu"}, "physics.device"),
    ],
)
def test_runtime_audit_physics_must_match_the_profile(
    fixture: str, physics: dict, field: str
) -> None:
    audit = _load(fixture)
    if fixture == "runtime_audit.valid.json":
        audit["requested_execution_profile"] = "isaac-gpu-physics"
        audit["execution_profile"] = "isaac-gpu-physics"
        audit["physics"] = {**audit["physics"], "device": "gpu"}
    audit["physics"] = {**audit["physics"], **physics}
    # The physics check is the default; only a test
    # runtime reporting a stand-in engine opts out.
    assert sim.check_runtime_audit(audit, verify_physics=False).ready
    check = sim.check_runtime_audit(audit)
    assert not check.ready
    assert [m["field"] for m in check.mismatches] == [field]
    assert check.error_code == "simulation_backend_runtime_mismatch"


def test_newton_audit_for_a_physx_request_is_a_mismatch() -> None:
    audit = _load("runtime_audit.valid.newton.json")
    check = sim.check_runtime_audit(
        audit, requested_execution_profile="isaac-gpu-physics"
    )
    assert check.error_code == "simulation_backend_runtime_mismatch"
    assert any(m["field"] == "execution_profile" for m in check.mismatches)


def test_runtime_audit_never_trusts_the_ready_flag() -> None:
    audit = {
        **_load("runtime_audit.valid.json"),
        "reported_backend": "mujoco",
        "ready": True,
    }
    assert not sim.check_runtime_audit(audit).ready


def test_runtime_audit_requested_backend_argument_wins() -> None:
    audit = _load("runtime_audit.valid.json")
    check = sim.check_runtime_audit(audit, requested_backend="mujoco")
    assert check.error_code == "simulation_backend_runtime_mismatch"


def test_runtime_audit_error_code_comes_from_the_mismatch() -> None:
    # Only the audit's own requested_backend disagrees: its mismatch carries
    # the runtime-mismatch code, and the verdict must report it.
    check = sim.check_runtime_audit(
        {
            "requested_backend": "isaac",
            "reported_backend": "mujoco",
            "capabilities": {"stream": "ok"},
        },
        requested_backend="mujoco",
    )
    assert [m["field"] for m in check.mismatches] == ["requested_backend"]
    assert check.error_code == "simulation_backend_runtime_mismatch"
    # A capability failure carries no code, so neither does the verdict.
    audit = {**_load("runtime_audit.valid.json"), "capabilities": {"state": "error"}}
    assert sim.check_runtime_audit(audit).error_code is None


# -- hardware qualification ---------------------------------------------------------

_PROBED_AT = datetime(2026, 10, 3, 8, 0, tzinfo=timezone.utc)
_IMAGE = "sha256:6105d6cc76af400325e94d588ce511be5bfdbb73b437dc51eca43917d7a43e3d"


def test_hardware_qualification_passes() -> None:
    record = _load("hardware_qualification.valid.json")
    assert (
        sim.check_hardware_qualification(
            record,
            now=_PROBED_AT + timedelta(hours=1),
            expected_image_digest=_IMAGE,
            execution_profile="isaac-newton-physics",
        )
        == []
    )


@pytest.mark.parametrize(
    ("change", "kwargs", "reason"),
    [
        ({"status": "fail"}, {}, "status"),
        ({"rt_cores": False}, {}, "RT cores"),
        ({"gpu_model": "NVIDIA A100-SXM4-80GB", "rt_cores": False}, {}, "RT cores"),
        ({"vram_mib": 12282}, {}, "VRAM"),
        ({"vram_mib": True}, {}, "VRAM"),
        ({"driver": ""}, {}, "driver missing"),
        ({"probe_version": None}, {}, "probe_version missing"),
        ({"image_digest": None}, {}, "image_digest"),
        ({"contract": "simulation.runtime_audit.v1"}, {}, "contract"),
        ({"checked_at": "2026-10-03T08:00:00"}, {}, "checked_at"),
        ({"checked_at": "yesterday"}, {}, "checked_at"),
        ({"checked_at": "2026-10-01T08:00:00Z"}, {}, "stale"),
        ({"checked_at": "2026-10-04T08:00:00Z"}, {}, "future"),
        ({}, {"expected_image_digest": "sha256:" + "0" * 64}, "pinned"),
        (
            {"execution_profiles": ["isaac-cpu-physics", "isaac-gpu-physics"]},
            {"execution_profile": "isaac-newton-physics"},
            "not probed",
        ),
    ],
)
def test_hardware_qualification_fails_closed(
    change: dict, kwargs: dict, reason: str
) -> None:
    record = {**_load("hardware_qualification.valid.json"), **change}
    reasons = sim.check_hardware_qualification(
        record, now=_PROBED_AT + timedelta(hours=1), **kwargs
    )
    assert any(reason in r for r in reasons), reasons


def test_provisional_hardware_qualification_needs_explicit_allowance() -> None:
    record = {
        **_load("hardware_qualification.valid.json"),
        "provisional": True,
        "provisional_reasons": ["runtime probe not run (set ISAAC_RUNTIME_PROBE=1)"],
    }
    now = _PROBED_AT + timedelta(hours=1)
    reasons = sim.check_hardware_qualification(record, now=now)
    assert any("provisional" in r for r in reasons), reasons
    assert (
        sim.check_hardware_qualification(record, now=now, allow_provisional=True) == []
    )


@pytest.mark.parametrize(
    "marker", [{"fake_runtime": True}, {"mode": sim.FAKE_RUNTIME_MODE}]
)
def test_fake_runtime_hardware_qualification_is_its_own_allowance(marker) -> None:
    """Admitting a waived real probe never also admits a GPU-less test record."""
    record = {
        **_load("hardware_qualification.valid.json"),
        "provisional": True,
        **marker,
    }
    now = _PROBED_AT + timedelta(hours=1)
    reasons = sim.check_hardware_qualification(record, now=now, allow_provisional=True)
    assert any("GPU-less" in r for r in reasons), reasons
    assert (
        sim.check_hardware_qualification(
            record, now=now, allow_provisional=True, allow_fake_runtime=True
        )
        == []
    )


@pytest.mark.parametrize("record", [None, {}, "pass", []])
def test_missing_hardware_qualification_never_qualifies(record: object) -> None:
    assert sim.check_hardware_qualification(record, now=_PROBED_AT)


def test_hardware_qualification_max_age_is_configurable() -> None:
    record = _load("hardware_qualification.valid.json")
    later = _PROBED_AT + timedelta(minutes=30)
    assert sim.check_hardware_qualification(record, now=later, max_age_s=3600) == []
    assert sim.check_hardware_qualification(record, now=later, max_age_s=600)


@pytest.mark.parametrize(
    ("gpu_model", "driver"),
    [
        ("NVIDIA L4", "550.54.15"),
        ("NVIDIA GeForce RTX 4080 SUPER", "570.86.10"),
        ("NVIDIA L40S", "580.95.05"),
        ("NVIDIA RTX PRO 6000 Blackwell Server Edition", "595.58.03"),
    ],
)
def test_any_rt_gpu_on_the_vram_floor_qualifies_on_any_driver(
    gpu_model: str, driver: str
) -> None:
    record = {
        **_load("hardware_qualification.valid.json"),
        "gpu_model": gpu_model,
        "driver": driver,
    }
    now = _PROBED_AT + timedelta(hours=1)
    assert sim.check_hardware_qualification(record, now=now) == []


def test_vram_floor_admits_16gb_cards_and_rejects_12gb() -> None:
    record = _load("hardware_qualification.valid.json")
    now = _PROBED_AT + timedelta(hours=1)
    for reported_total in (16303, 16376, 24564, 49140):
        assert (
            sim.check_hardware_qualification(
                {**record, "vram_mib": reported_total}, now=now
            )
            == []
        )
    assert sim.check_hardware_qualification({**record, "vram_mib": 12282}, now=now)


# -- attestation key ---------------------------------------------------------------


def test_attestation_key_digest_matches_fixture_and_detects_changes() -> None:
    attestation = _load("compatibility_attestation.valid.json")
    assert sim.attestation_key_digest(attestation["key"]) == attestation["key_digest"]
    reordered = dict(reversed(list(attestation["key"].items())))
    assert sim.attestation_key_digest(reordered) == attestation["key_digest"]
    changed = {**attestation["key"], "extension_lock_digest": "sha256:" + "1" * 64}
    assert sim.attestation_key_digest(changed) != attestation["key_digest"]


# -- run fencing -------------------------------------------------------------------

_FENCING = _load("run_fencing.v1.json")["cases"]


@pytest.mark.parametrize("case", _FENCING, ids=[c["name"] for c in _FENCING])
def test_run_fencing_fixture(case: dict) -> None:
    decision = sim.accept(case["item"], case["current_run"])
    assert (decision.accepted, decision.reason) == (
        case["expected"]["accepted"],
        case["expected"]["reason"],
    )
    assert bool(decision) is case["expected"]["accepted"]
    assert decision.reason in sim.FENCE_REASONS


def test_fencing_covers_the_required_scenarios() -> None:
    names = " ".join(c["name"] for c in _FENCING)
    for scenario in (
        "delayed command",
        "stale publisher",
        "reconnect",
        "reset with queued output",
        "old media",
    ):
        assert scenario in names


def test_fencing_accepts_run_identity_instance() -> None:
    run = sim.RunIdentity(run_id="r", stream_instance_id="s", reset_epoch=2)
    assert sim.accept({"run_id": "r", "stream_instance_id": "s", "reset_epoch": 2}, run)
    assert sim.accept({"run_id": "r"}, run).reason == "ok"
    assert (
        sim.accept({"run_id": "r", "reset_epoch": True}, run).reason
        == "missing_run_identity"
    )


# -- secret scanning ---------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        {"token": "x"},
        {"Authorization": "x"},
        {"nested": {"mqtt_password": "x"}},
        {
            "url": "https://storage.googleapis.com/b/o?X-Goog-Algorithm=a&X-Goog-Signature=abc"
        },
        {"url": "https://bucket.s3.amazonaws.com/o?X-Amz-Signature=abc"},
        {"url": "https://x.blob.core.windows.net/c/b?sv=1&sig=abc"},
        {"url": "https://api/x?token=abc"},
        {"header": "Bearer abc.def"},
        {"jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig"},
        {"url": "mqtt://user:pass@broker:1883"},
        ["ok", {"client_secret": "x"}],
    ],
)
def test_find_secret_like(value: object) -> None:
    assert sim.find_secret_like(value)


def test_find_secret_like_ignores_benign_values() -> None:
    value = {
        "sensor_id": "token_ring_camera",
        "path": "assets/sig.usda",
        "note": "signature verified",
    }
    assert sim.find_secret_like(value) == []
    assert sim.find_secret_like({"ref": "https://cyberwave.com"}, forbid_urls=True)


# -- simulation parameters -------------------------------------------------------


def test_timing_normalises_and_drops_unset_fields() -> None:
    timing = sim.normalize_timing(
        "isaac",
        {
            "dt": 0.002,
            "realtime": True,
            "simulation_speed": 2,
            "stream_frequency_hz": 50,
            "range_stream_frequency_hz": 0,
            "range_self_hit_fallback": None,
        },
    )
    assert timing == {
        "dt": 0.002,
        "realtime": True,
        "simulation_speed": 2.0,
        "stream_frequency_hz": 50.0,
        "range_stream_frequency_hz": 0.0,
    }
    assert sim.normalize_timing("mujoco", None) == {}


def test_timing_bounds_match_the_backend_schema() -> None:
    assert sim.TIMING_DT_RANGE == (1e-6, 0.1)
    assert sim.TIMING_STREAM_FREQUENCY_RANGE == (0.1, 1000.0)
    assert sim.TIMING_RANGE_STREAM_FREQUENCY_RANGE == (0.0, 1000.0)


@pytest.mark.parametrize(
    "timing",
    [
        {"dt": 5.0},
        {"dt": 0.0},
        {"dt": True},
        {"dt": "0.01"},
        {"dt": float("nan")},
        {"simulation_speed": 0},
        {"simulation_speed": -1},
        {"stream_frequency_hz": 5000},
        {"range_stream_frequency_hz": -1},
        {"realtime": 1},
    ],
)
def test_timing_rejects_invalid_values(timing: dict) -> None:
    with pytest.raises(sim.SimulationContractError) as exc:
        sim.normalize_timing("isaac", timing)
    assert exc.value.code == sim.ERROR_PARAMETER_INVALID


def test_timing_rejects_unknown_and_backend_unsupported_keys() -> None:
    with pytest.raises(sim.SimulationContractError) as exc:
        sim.normalize_timing("mujoco", {"integrator": "RK4"})
    assert exc.value.code == sim.ERROR_PARAMETER_UNSUPPORTED
    assert "integrator" in exc.value.detail
    with pytest.raises(sim.SimulationContractError) as exc:
        sim.normalize_timing("isaac", {"range_self_hit_fallback": False})
    assert exc.value.code == sim.ERROR_PARAMETER_UNSUPPORTED
    # MuJoCo honours it, including the meaningful False.
    assert sim.normalize_timing("mujoco", {"range_self_hit_fallback": False}) == {
        "range_self_hit_fallback": False
    }


def test_isaac_timing_carries_solver_and_render_settings() -> None:
    timing = sim.normalize_timing(
        "isaac",
        {
            "substeps": 4,
            "solver_position_iterations": 32,
            "solver_velocity_iterations": 0,
            "rendering_dt": 1 / 30,
            "realtime": False,
        },
    )
    assert timing == {
        "substeps": 4,
        "solver_position_iterations": 32,
        "solver_velocity_iterations": 0,
        "rendering_dt": pytest.approx(1 / 30),
        "realtime": False,
    }
    assert isinstance(timing["substeps"], int)


@pytest.mark.parametrize(
    "timing",
    [
        {"substeps": 0},
        {"substeps": 2.0},
        {"solver_position_iterations": 0},
        {"solver_velocity_iterations": 256},
        {"rendering_dt": 0.0},
        {"rendering_dt": 2.0},
    ],
)
def test_isaac_timing_rejects_invalid_solver_and_render_values(timing: dict) -> None:
    with pytest.raises(sim.SimulationContractError) as exc:
        sim.normalize_timing("isaac", timing)
    assert exc.value.code == sim.ERROR_PARAMETER_INVALID


@pytest.mark.parametrize("key", sorted(sim.ISAAC_ONLY_TIMING_FIELDS))
def test_mujoco_refuses_isaac_only_timing(key: str) -> None:
    value = 0.01 if key == "rendering_dt" else 2
    with pytest.raises(sim.SimulationContractError) as exc:
        sim.normalize_timing("mujoco", {key: value})
    assert exc.value.code == sim.ERROR_PARAMETER_UNSUPPORTED


def test_newton_refuses_per_run_solver_iterations() -> None:
    newton = sim.EXECUTION_PROFILE_ISAAC_NEWTON
    assert sim.normalize_timing("isaac", {"substeps": 2}, execution_profile=newton) == {
        "substeps": 2
    }
    with pytest.raises(sim.SimulationContractError) as exc:
        sim.normalize_timing(
            "isaac", {"solver_position_iterations": 8}, execution_profile=newton
        )
    assert exc.value.code == sim.ERROR_PARAMETER_UNSUPPORTED


def test_isaac_physics_extension() -> None:
    assert sim.normalize_isaac_physics(None) == {}
    assert sim.normalize_isaac_physics(
        {
            "solver_position_iterations": 32,
            "solver_velocity_iterations": 0,
            "substeps": 4,
        },
        execution_profile="isaac-gpu-physics",
    ) == {
        "solver_position_iterations": 32,
        "solver_velocity_iterations": 0,
        "substeps": 4,
    }
    # Newton steps substeps but has no PhysX iteration counts.
    assert sim.normalize_isaac_physics(
        {"substeps": 2}, execution_profile="isaac-newton-physics"
    ) == {"substeps": 2}
    with pytest.raises(sim.SimulationContractError) as exc:
        sim.normalize_isaac_physics(
            {"solver_position_iterations": 8}, execution_profile="isaac-newton-physics"
        )
    assert exc.value.code == sim.ERROR_PARAMETER_UNSUPPORTED


@pytest.mark.parametrize(
    "profile", ["ISAAC-NEWTON-PHYSICS", " isaac-newton-physics", "bogus-profile"]
)
def test_isaac_physics_extension_refuses_an_unknown_profile(profile: str) -> None:
    # An unrecognised profile must not disable the Newton solver guard.
    with pytest.raises(sim.SimulationContractError) as exc:
        sim.normalize_isaac_physics(
            {"solver_position_iterations": 8}, execution_profile=profile
        )
    assert exc.value.code == sim.ERROR_BACKEND_UNSUPPORTED
    with pytest.raises(sim.SimulationContractError):
        sim.normalize_timing(
            "isaac", {"solver_position_iterations": 8}, execution_profile=profile
        )


@pytest.mark.parametrize(
    ("options", "code"),
    [
        ({"solver_type": "TGS"}, "simulation_parameter_unsupported"),
        ({"solver_position_iterations": 0}, "simulation_parameter_invalid"),
        ({"solver_position_iterations": 256}, "simulation_parameter_invalid"),
        ({"solver_velocity_iterations": -1}, "simulation_parameter_invalid"),
        ({"substeps": 65}, "simulation_parameter_invalid"),
        ({"substeps": 2.0}, "simulation_parameter_invalid"),
        ({"substeps": True}, "simulation_parameter_invalid"),
        ([1, 2], "simulation_parameter_invalid"),
    ],
)
def test_isaac_physics_extension_fails_closed(options: object, code: str) -> None:
    with pytest.raises(sim.SimulationContractError) as exc:
        sim.normalize_isaac_physics(options)  # type: ignore[arg-type]
    assert exc.value.code == code


def test_gravity() -> None:
    assert sim.normalize_gravity([0, 0, -9.81]) == (0.0, 0.0, -9.81)
    for bad in ([0, -9.81], "0 0 -9.81", [0, 0, None], [0, 0, float("inf")]):
        with pytest.raises(sim.SimulationContractError) as exc:
            sim.normalize_gravity(bad)
        assert exc.value.code == sim.ERROR_PARAMETER_INVALID
