"""Inference for the multi-label session failure-cause classifier."""

from __future__ import annotations

import logging
import sqlite3
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.collect_session_dataset import _build_row


logger = logging.getLogger("elou_avt.ml.session_cause")
MODEL_PATH = Path(__file__).resolve().parent / "model_output" / "one_vs_rest_logistic.joblib"

CAUSE_NAMES = {
    "target_1": "Потеря ориентации в установке",
    "target_2": "Долгое время реакции",
    "target_3": "Непонимание физических процессов",
    "target_4": "Незнание алгоритма или регламента",
    "target_5": "Случайная ошибка",
}


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _numeric_equipment_values(snapshot: sqlite3.Row, equipment_id: str) -> list[float]:
    values: list[float] = []
    for column in ("pump_states", "valve_positions"):
        state = _json_object(snapshot[column] if column in snapshot.keys() else None)
        value = state.get(equipment_id)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    states = _json_object(
        snapshot["equipment_states"] if "equipment_states" in snapshot.keys() else None
    )
    state = states.get(equipment_id)
    if isinstance(state, dict):
        for key in ("running", "failed", "position", "value", "pressure",
                    "temperature", "level", "flow"):
            value = state.get(key)
            if isinstance(value, (int, float, bool)):
                values.append(float(value))
    return values


def _model_contract_features(conn: sqlite3.Connection, session: sqlite3.Row) -> dict[str, Any]:
    """Recreate the feature contract used when the saved model was trained."""
    session_id = str(session["id"])
    scenario_id = str(session["scenario_id"])
    actions = conn.execute(
        "SELECT * FROM actions WHERE session_id=? ORDER BY seq", (session_id,)
    ).fetchall()
    expected = conn.execute(
        "SELECT * FROM expected_actions WHERE scenario_id=? ORDER BY deadline_t, id",
        (scenario_id,),
    ).fetchall()
    alarms = conn.execute(
        "SELECT * FROM alarms WHERE session_id=? ORDER BY raised_at", (session_id,)
    ).fetchall()
    errors = conn.execute(
        "SELECT * FROM error_events WHERE session_id=? ORDER BY sim_time", (session_id,)
    ).fetchall()
    snapshots = conn.execute(
        "SELECT * FROM state_snapshots WHERE session_id=? ORDER BY seq", (session_id,)
    ).fetchall()

    sim_start = float(session["sim_start"] or 0.0)
    sim_end = float(session["sim_end"] or sim_start)
    action_times = [float(row["sim_time"]) for row in actions]
    action_pairs = [(row["equipment_id"], row["action_type"]) for row in actions]
    expected_pairs = [(row["equipment_id"], row["action_type"]) for row in expected]
    action_counts = Counter(action_pairs)
    expected_counts = Counter(expected_pairs)
    completed = sum(min(count, action_counts[pair]) for pair, count in expected_counts.items())
    idle = [sim_end - sim_start]
    if action_times:
        idle = [action_times[0] - sim_start]
        idle += [right - left for left, right in zip(action_times, action_times[1:])]
        idle.append(sim_end - action_times[-1])

    relevant_delays: list[float] = []
    expected_set = set(expected_pairs)
    for alarm in alarms:
        raised = float(alarm["raised_at"] or 0.0)
        relevant = next(
            (action for action in actions
             if float(action["sim_time"]) >= raised
             and (action["equipment_id"], action["action_type"]) in expected_set),
            None,
        )
        if relevant is not None:
            relevant_delays.append(float(relevant["sim_time"]) - raised)

    effects: list[float] = []
    for action in actions:
        action_time = float(action["sim_time"])
        equipment_id = str(action["equipment_id"] or "")
        before = [row for row in snapshots if float(row["sim_time"]) <= action_time]
        after = [row for row in snapshots if float(row["sim_time"]) > action_time]
        if not equipment_id or not before or not after:
            continue
        before_values = _numeric_equipment_values(before[-1], equipment_id)
        after_values = _numeric_equipment_values(after[0], equipment_id)
        if before_values and after_values:
            effects.append(mean(after_values) - mean(before_values))

    error_counts = Counter(str(row["rule_error_type"]) for row in errors)
    return {
        "time_to_first_action_s": max(0.0, action_times[0] - sim_start) if action_times else None,
        "action_max_idle_s": max((max(0.0, value) for value in idle), default=0.0),
        "action_correct_ratio": completed / len(actions) if actions else 0.0,
        "action_extra_count": max(0, len(actions) - completed),
        "action_repeated_count": sum(max(0, count - 1) for count in action_counts.values()),
        "expected_completed_count": completed,
        "expected_completion_ratio": completed / len(expected) if expected else 0.0,
        "alarm_active_at_end_count": sum(row["cleared_at"] is None for row in alarms),
        "alarm_mean_relevant_action_delay_s": mean(relevant_delays) if relevant_delays else None,
        "alarm_max_relevant_action_delay_s": max(relevant_delays, default=None),
        "equipment_state_observed_action_ratio": len(effects) / len(actions) if actions else 0.0,
        "equipment_state_changed_action_ratio": (
            sum(abs(value) > 1e-9 for value in effects) / len(effects) if effects else None
        ),
        "error_wrong_parameter_value_count": error_counts["WRONG_PARAMETER_VALUE"],
    }


class SessionCauseClassifier:
    """Loads one model artifact and predicts causes for persisted sessions."""

    def __init__(self, model_path: Path = MODEL_PATH):
        self._model_path = model_path
        self._artifact: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._artifact is None:
            artifact = joblib.load(self._model_path)
            required = {"model", "feature_names", "target_columns"}
            if not required.issubset(artifact):
                raise ValueError("Артефакт ML-модели не содержит обязательные поля")
            self._artifact = artifact
        return self._artifact

    def predict(self, db_path: str | Path, session_id: str) -> dict[str, Any] | None:
        """Build session features and return all causes ordered by probability."""
        if not self._model_path.exists():
            logger.warning("ML model not found: %s", self._model_path)
            return None

        artifact = self._load()
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            session = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None:
                return None
            row = _build_row(conn, dict(session))
            row.update(_model_contract_features(conn, session))

        feature_names = list(artifact["feature_names"])
        missing = [name for name in feature_names if name not in row]
        if missing:
            raise ValueError(f"Не удалось рассчитать признаки модели: {', '.join(missing)}")
        frame = pd.DataFrame([{name: row[name] for name in feature_names}])
        probabilities = self._predict_probabilities(artifact["model"], frame)
        targets = list(artifact["target_columns"])
        raw_thresholds = artifact.get("thresholds", [0.5] * len(targets))
        thresholds = (
            [float(raw_thresholds[target]) for target in targets]
            if isinstance(raw_thresholds, dict)
            else [float(value) for value in raw_thresholds]
        )
        causes = sorted(
            (
                {
                    "label": target,
                    "name": CAUSE_NAMES.get(target, target),
                    "probability": round(float(probability), 6),
                    "selected": bool(probability >= threshold),
                }
                for target, probability, threshold in zip(
                    targets, probabilities, thresholds, strict=True
                )
            ),
            key=lambda item: item["probability"],
            reverse=True,
        )
        return {
            "model_name": self._model_path.name,
            "causes": causes,
            "top_causes": causes[:2],
            "predicted_labels": [item["label"] for item in causes if item["selected"]],
            "features": {name: row[name] for name in feature_names},
        }

    @staticmethod
    def _predict_probabilities(model: Any, frame: pd.DataFrame) -> np.ndarray:
        """Evaluate the saved linear pipeline without depending on sklearn internals.

        This keeps artifacts trained with sklearn 1.6 usable if the application
        environment temporarily has a newer sklearn release installed.
        """
        try:
            return np.asarray(model.predict_proba(frame)[0], dtype=float)
        except AttributeError:
            logger.warning(
                "Sklearn artifact is version-incompatible; using portable linear inference"
            )

        imputer = model.named_steps["imputer"]
        scaler = model.named_steps["scaler"]
        classifier = model.named_steps["classifier"]
        values = frame.to_numpy(dtype=float)
        statistics = np.asarray(imputer.statistics_, dtype=float)
        values = np.where(np.isnan(values), statistics, values)
        scale = np.asarray(scaler.scale_, dtype=float)
        scale = np.where(scale == 0.0, 1.0, scale)
        standardized = (values - np.asarray(scaler.mean_, dtype=float)) / scale
        logits = np.asarray([
            float(standardized[0] @ estimator.coef_[0] + estimator.intercept_[0])
            for estimator in classifier.estimators_
        ])
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -709.0, 709.0)))


session_cause_classifier = SessionCauseClassifier()
