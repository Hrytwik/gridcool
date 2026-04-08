from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

MODEL_FILENAME = "load_forecast_xgb.joblib"
METADATA_FILENAME = "load_forecast_meta.json"


def load_to_stress_score(load_mw: float, context: dict[str, Any] | None = None) -> float:
    """
    Monotonic map from predicted load (MW) to stress score [0, 100].
    `context` may contain `capacity_mw` override; otherwise uses calibration default.
    """

    cap = None
    if context and "capacity_mw" in context:
        try:
            cap = float(context["capacity_mw"])
        except (TypeError, ValueError):
            cap = None
    if cap is None or cap <= 0:
        cap = float((context or {}).get("_default_capacity_mw") or 6600.0)
    return float(min(100.0, max(0.0, 100.0 * float(load_mw) / cap)))


def resolve_backend_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def resolve_ml_dir(ml_artifact_dir: str) -> Path:
    p = Path(ml_artifact_dir)
    if not p.is_absolute():
        p = resolve_backend_root() / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_artifacts(
    *,
    model: object,
    feature_names: list[str],
    metadata: dict[str, Any],
    ml_artifact_dir: str,
) -> tuple[Path, Path]:
    root = resolve_ml_dir(ml_artifact_dir)
    mpath = root / MODEL_FILENAME
    jpath = root / METADATA_FILENAME
    joblib.dump(model, mpath)
    payload = {
        **metadata,
        "feature_names": feature_names,
        "saved_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    jpath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return mpath, jpath


def load_artifacts(ml_artifact_dir: str) -> tuple[object | None, dict[str, Any] | None, str]:
    """
    Returns (model, metadata, status) where status is 'loaded' | 'missing' | 'error'.
    """

    root = Path(ml_artifact_dir)
    if not root.is_absolute():
        root = resolve_backend_root() / root
    mpath = root / MODEL_FILENAME
    jpath = root / METADATA_FILENAME
    if not mpath.is_file() or not jpath.is_file():
        return None, None, "missing"
    try:
        model = joblib.load(mpath)
        meta = json.loads(jpath.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            return None, None, "error"
        if model is None or not hasattr(model, "predict"):
            return None, None, "error"
        return model, meta, "loaded"
    except Exception:
        return None, None, "error"


def stress_context_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cal = metadata.get("calibration") or {}
    cap = cal.get("capacity_mw")
    ctx: dict[str, Any] = {}
    if cap is not None:
        try:
            ctx["capacity_mw"] = float(cap)
        except (TypeError, ValueError):
            pass
    if "capacity_mw" not in ctx:
        ctx["_default_capacity_mw"] = float(cal.get("default_capacity_mw") or 6600.0)
    return ctx
