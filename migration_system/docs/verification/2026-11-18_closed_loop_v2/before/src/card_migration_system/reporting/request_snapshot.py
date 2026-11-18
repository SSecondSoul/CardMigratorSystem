"""Freeze the actual disabled/stub policy, never pretend real prompts were run."""
from .identity import digest


DIMENSIONS = {"ssm_extraction": "static", "static_validation": "static", "san_compile": "static",
              "structure_ted": "static", "browser_visual": "browser", "browser_interaction": "browser"}


def build_snapshot(api, *, run_id, task_id, source, request, binding):
    descriptors = {
        "protocol": {"id": "p2b-control-v1", "mode": "development_stub",
                     "profile": request["profile"], "fixture_repair_rounds": request["max_repair_rounds"],
                     "migration_execution_permitted": False},
        "prompt_set": {"mode": "disabled", "templates": [], "real_prompt_execution": False},
        "model_config": {"mode": "development_stub", "provider": None, "external_calls_permitted": False},
        "evaluation_policy": {"id": "p2b-unexecuted-v1", "required_dimensions": list(DIMENSIONS),
                              "quality_evaluators_executed": []},
    }
    contract = api.MigrationRequest(
        run_id=run_id, sample_id=f"task:{task_id}",
        source=api.FileFingerprint(path=source["relative_path"], sha256=source["sha256"]),
        protocol_sha256=digest(descriptors["protocol"]),
        implementation_sha256=binding["implementation_sha256"],
        prompt_set_sha256=digest(descriptors["prompt_set"]),
        evaluation_policy_sha256=digest(descriptors["evaluation_policy"]),
        model_config_sha256=digest(descriptors["model_config"]),
        ssm_schema_version="development_stub_not_extracted",
        # Fixture-loop budget is separate, not a model/rule migration allowance.
        budget=api.Budget(max_model_repair_calls=0, max_rule_steps=0))
    return {"snapshot_version": 1, "hash_format": "canonical_json_utf8_ascii_v1",
            "request": contract.to_dict(), "descriptors": descriptors}


def validate_snapshot(api, *, run_id, task_id, source, request, binding):
    if "contract_snapshot" not in request:
        raise ValueError("report_request_snapshot_missing")
    expected = build_snapshot(api, run_id=run_id, task_id=task_id, source=source, request=request, binding=binding)
    # Python dict equality treats False == 0 and True == 1; the wire contract does not.
    if digest(request["contract_snapshot"]) != digest(expected):
        raise ValueError("report_request_snapshot_mismatch")
    return api.load_contract(request["contract_snapshot"]["request"])
