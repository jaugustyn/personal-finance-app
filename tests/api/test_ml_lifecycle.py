"""API contract tests for durable classifier lifecycle resources."""
from __future__ import annotations

from apps.api.routers import ml as ml_router
from finance.domain.models import MlTrainingJob


def test_lifecycle_resources_have_explicit_empty_states(client) -> None:
    versions = client.get("/ml/model-versions")
    evaluation = client.get("/ml/evaluation-sets/current")

    assert versions.status_code == 200
    assert versions.json() == []
    assert evaluation.status_code == 200
    assert evaluation.json()["active"] is False
    assert evaluation.json()["data_readiness"]["ready"] is False
    assert evaluation.json()["data_readiness"]["total"] == 0


def test_retrain_creates_durable_job_without_automatic_activation(
    client,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(ml_router, "_retrain_job", lambda _job_id: None)
    monkeypatch.setattr(
        ml_router,
        "readiness_summary",
        lambda _session: {"training_ready": True},
    )

    response = client.post("/ml/retrain?estimator=logreg&feature_set=baseline")

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"]
    job = db_session.get(MlTrainingJob, body["job_id"])
    assert job is not None
    assert job.status == "queued"
    assert job.execution_slot == 1
    assert job.result == {}


def test_default_retrain_queues_exactly_two_baseline_candidates(
    client,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(ml_router, "_retrain_job", lambda _job_id: None)
    monkeypatch.setattr(
        ml_router,
        "readiness_summary",
        lambda _session: {"training_ready": True},
    )

    response = client.post("/ml/retrain")

    assert response.status_code == 202
    job = db_session.get(MlTrainingJob, response.json()["job_id"])
    assert job is not None
    assert job.requested_variants == [
        {"estimator": "logreg", "feature_set": "baseline", "promotable": True},
        {
            "estimator": "linear_svc_calibrated",
            "feature_set": "baseline",
            "promotable": True,
        },
    ]


def test_retrain_rejects_feature_v2_as_runtime_candidate(
    client,
    db_session,
) -> None:
    response = client.post("/ml/retrain?feature_set=feature_v2")

    assert response.status_code == 400
    assert "benchmark-only" in response.json()["detail"]
    assert db_session.query(MlTrainingJob).count() == 0


def test_retrain_rejects_request_before_creating_job_without_gold_labels(
    client,
    db_session,
) -> None:
    response = client.post("/ml/retrain")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "training_data_not_ready"
    assert detail["readiness"]["total_labelled"] == 0
    assert db_session.query(MlTrainingJob).count() == 0


def test_transaction_type_cold_start_does_not_require_a_model(client) -> None:
    reclassify = client.post("/ml/transaction-types/reclassify")

    assert reclassify.status_code == 200
    assert reclassify.json() == {"updated": 0}
