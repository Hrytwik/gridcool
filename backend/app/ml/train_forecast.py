from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from app.core.config import get_settings
from app.ml.model_io import resolve_backend_root, save_artifacts

SEASONS = ["summer", "monsoon", "winter", "shoulder"]


def _prepare_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    d = df.sort_values("timestamp").reset_index(drop=True)
    d["load_mw"] = pd.to_numeric(d["load_mw"], errors="coerce")
    for c in ("temp_c", "feels_like_c", "humidity", "wind_speed", "cloud_cover"):
        d[c] = pd.to_numeric(d[c], errors="coerce")

    d["lag_1h"] = d["load_mw"].shift(1)
    d["roll_mean_3h"] = d["load_mw"].shift(1).rolling(window=3, min_periods=1).mean()
    d["roll_mean_24h"] = d["load_mw"].shift(1).rolling(window=24, min_periods=1).mean()

    for s in SEASONS:
        d[f"season_{s}"] = (d["season"].astype(str) == s).astype(int)

    d["y_next"] = d["load_mw"].shift(-1)

    feature_cols = [
        "hour_of_day",
        "day_of_week",
        "month",
        "is_weekend",
        "is_holiday",
        "season_summer",
        "season_monsoon",
        "season_winter",
        "season_shoulder",
        "temp_c",
        "feels_like_c",
        "humidity",
        "wind_speed",
        "cloud_cover",
        "heatwave_flag",
        "event_flag",
        "load_mw_lag_24h",
        "lag_1h",
        "roll_mean_3h",
        "roll_mean_24h",
    ]

    d2 = d.dropna(subset=feature_cols + ["y_next"]).reset_index(drop=True)
    return d2, feature_cols


def _time_split(df: pd.DataFrame, val_hours: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(df) <= val_hours + 48:
        split = int(len(df) * 0.85)
        return df.iloc[:split], df.iloc[split:]
    return df.iloc[:-val_hours], df.iloc[-val_hours:]


def train_pipeline(*, csv_path: Path, ml_artifact_dir: str, val_hours: int = 1440) -> dict[str, object]:
    raw = pd.read_csv(csv_path)
    df, feature_cols = _prepare_frame(raw)
    train_df, val_df = _time_split(df, val_hours=val_hours)

    X_tr = train_df[feature_cols]
    y_tr = train_df["y_next"]
    X_va = val_df[feature_cols]
    y_va = val_df["y_next"]

    model = XGBRegressor(
        n_estimators=400,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)

    pred_va = model.predict(X_va)
    mae = float(mean_absolute_error(y_va, pred_va))
    rmse = float(mean_squared_error(y_va, pred_va) ** 0.5)

    cap = float(np.percentile(train_df["load_mw"].to_numpy(), 99.0) * 1.02)
    cap = max(cap, 1.0)

    metadata: dict[str, object] = {
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "val_mae_mw": mae,
        "val_rmse_mw": rmse,
        "calibration": {
            "capacity_mw": cap,
            "default_capacity_mw": cap,
        },
        "data_path": str(csv_path.resolve()),
    }

    mpath, jpath = save_artifacts(
        model=model,
        feature_names=feature_cols,
        metadata=metadata,
        ml_artifact_dir=ml_artifact_dir,
    )
    return {
        "model_path": str(mpath),
        "meta_path": str(jpath),
        "mae": mae,
        "rmse": rmse,
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "capacity_mw": cap,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Train XGBoost hourly load forecaster")
    p.add_argument("--data", type=str, default="data/chennai_hourly_load.csv")
    p.add_argument("--val-hours", type=int, default=1440)
    args = p.parse_args()

    settings = get_settings()
    backend = resolve_backend_root()
    csv_path = Path(args.data)
    if not csv_path.is_absolute():
        parts = csv_path.parts
        if len(parts) >= 2 and parts[0] == "backend":
            csv_path = (backend / Path(*parts[1:])).resolve()
        else:
            csv_path = (backend / csv_path).resolve()
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    summary = train_pipeline(
        csv_path=csv_path,
        ml_artifact_dir=settings.ML_ARTIFACT_DIR,
        val_hours=int(args.val_hours),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
