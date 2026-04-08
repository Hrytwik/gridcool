from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.routers.ml import router as ml_router


def test_ml_predict_returns_200_sim_fallback_when_no_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ML_ARTIFACT_DIR", str(tmp_path / "empty_ml"))
    monkeypatch.setenv("ML_DATA_CSV", str(tmp_path / "no_csv.csv"))
    get_settings.cache_clear()

    mini = FastAPI()
    mini.include_router(ml_router)
    with TestClient(mini) as client:
        r = client.get("/ml/predict")

    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "sim_fallback"
    assert body["artifact_status"] in ("missing", "error")
    assert len(body["forecast_load_mw"]) >= 1
