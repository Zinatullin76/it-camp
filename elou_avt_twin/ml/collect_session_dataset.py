"""Collect every session from sessions.db into a pandas DataFrame.

Run without arguments: ``python ml/collect_session_dataset.py``.
The script only reads SQLite and writes ``ml/session_dataset.csv``.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

import pandas as pd


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "sessions.db"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "session_dataset.csv"

ERROR_TYPES = (
    "WRONG_SEQUENCE",
    "DELAYED_ACTION",
    "WRONG_EQUIPMENT",
    "WRONG_ACTION_TYPE",
    "WRONG_PARAMETER_VALUE",
    "MISSED_ACTION",
)


def _json_load(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _rows(conn: sqlite3.Connection, table: str, session_id: str, order: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, table) or "session_id" not in _columns(conn, table):
        return []
    query = f'SELECT * FROM "{table}" WHERE session_id = ? ORDER BY {order}'
    return [dict(row) for row in conn.execute(query, (session_id,)).fetchall()]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _interval_features(prefix: str, times: Sequence[float]) -> dict[str, float]:
    gaps = [right - left for left, right in zip(times, times[1:]) if right >= left]
    return {
        f"{prefix}_mean_interval_s": mean(gaps) if gaps else 0.0,
        f"{prefix}_max_interval_s": max(gaps, default=0.0),
    }


def _equipment_values(snapshot: Mapping[str, Any], equipment_id: str) -> list[float]:
    """Extract numeric dynamic state only for the requested equipment."""
    values: list[float] = []
    for column in ("pump_states", "valve_positions"):
        state = _json_load(snapshot.get(column), {})
        if isinstance(state, Mapping):
            value = _number(state.get(equipment_id))
            if value is not None:
                values.append(value)

    equipment_states = _json_load(snapshot.get("equipment_states"), {})
    state = equipment_states.get(equipment_id) if isinstance(equipment_states, Mapping) else None
    if isinstance(state, Mapping):
        for key in ("running", "failed", "position", "value", "pressure", "temperature", "level", "flow"):
            value = _number(state.get(key))
            if value is not None:
                values.append(value)
    return values


def _action_effect_features(
    actions: Sequence[Mapping[str, Any]], snapshots: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    effects: list[float] = []
    for action in actions:
        action_time = _number(action.get("sim_time"))
        equipment_id = action.get("equipment_id")
        if action_time is None or not equipment_id:
            continue
        before = [s for s in snapshots if (_number(s.get("sim_time")) or 0.0) <= action_time]
        after = [s for s in snapshots if (_number(s.get("sim_time")) or 0.0) > action_time]
        if not before or not after:
            continue
        before_values = _equipment_values(before[-1], str(equipment_id))
        after_values = _equipment_values(after[0], str(equipment_id))
        if before_values and after_values:
            effects.append(mean(after_values) - mean(before_values))
    return {
        "equipment_state_observed_action_ratio": len(effects) / len(actions) if actions else 0.0,
        "equipment_state_changed_action_ratio": (
            sum(abs(effect) > 1e-9 for effect in effects) / len(effects) if effects else None
        ),
    }


def _mean_or_none(values: Sequence[float]) -> float | None:
    return mean(values) if values else None


def _build_row(
    conn: sqlite3.Connection,
    session: Mapping[str, Any],
) -> dict[str, Any]:
    session_id = str(session["id"])
    scenario_id = str(session["scenario_id"])
    actions = _rows(conn, "actions", session_id, "seq")
    snapshots = _rows(conn, "state_snapshots", session_id, "seq")
    alarms = _rows(conn, "alarms", session_id, "raised_at")
    errors = _rows(conn, "error_events", session_id, "sim_time")
    expected = []
    if _table_exists(conn, "expected_actions"):
        expected = [
            dict(row) for row in conn.execute(
                "SELECT * FROM expected_actions WHERE scenario_id=? ORDER BY deadline_t, id",
                (scenario_id,),
            ).fetchall()
        ]

    sim_start = _number(session.get("sim_start")) or 0.0
    sim_end = _number(session.get("sim_end"))
    wall_start = _number(session.get("wall_start"))
    wall_end = _number(session.get("wall_end"))
    action_times = [float(a["sim_time"]) for a in actions if _number(a.get("sim_time")) is not None]
    error_times = [float(e["sim_time"]) for e in errors if _number(e.get("sim_time")) is not None]
    error_counts = Counter(str(e.get("rule_error_type", "UNKNOWN")) for e in errors)
    alarm_severity = Counter(str(a.get("severity", "UNKNOWN")) for a in alarms)
    equipment = {str(a.get("equipment_id")) for a in actions if a.get("equipment_id")}
    action_pair_list = [(a.get("equipment_id"), a.get("action_type")) for a in actions]
    expected_pair_list = [(a.get("equipment_id"), a.get("action_type")) for a in expected]
    action_pair_counts = Counter(action_pair_list)
    expected_pair_counts = Counter(expected_pair_list)
    matched_expected_count = sum(
        min(count, action_pair_counts[pair]) for pair, count in expected_pair_counts.items()
    )
    correct_action_count = matched_expected_count
    extra_action_count = len(actions) - matched_expected_count
    repeated_action_count = sum(max(0, count - 1) for count in action_pair_counts.values())

    alarm_reaction_delays: list[float] = []
    for alarm in alarms:
        raised_at = _number(alarm.get("raised_at"))
        if raised_at is None:
            continue
        reaction = next(
            (
                action for action in actions
                if (_number(action.get("sim_time")) or -math.inf) >= raised_at
                and (action.get("equipment_id"), action.get("action_type")) in expected_pair_counts
            ),
            None,
        )
        if reaction is not None:
            alarm_reaction_delays.append(float(reaction["sim_time"]) - raised_at)

    expected_coverage = matched_expected_count / len(expected_pair_list) if expected_pair_list else 0.0
    idle_gaps = []
    if sim_end is not None:
        if action_times:
            idle_gaps = [max(0.0, action_times[0] - sim_start)]
            idle_gaps.extend(
                max(0.0, right - left) for left, right in zip(action_times, action_times[1:])
            )
            idle_gaps.append(max(0.0, sim_end - action_times[-1]))
        else:
            idle_gaps = [max(0.0, sim_end - sim_start)]
    row: dict[str, Any] = {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "session_duration_sim_s": max(0.0, sim_end - sim_start) if sim_end is not None else 0.0,
        "session_duration_wall_s": (
            max(0.0, wall_end - wall_start)
            if wall_start is not None and wall_end is not None else None
        ),
        "time_to_first_action_s": max(0.0, action_times[0] - sim_start) if action_times else None,
        "action_max_idle_s": max(idle_gaps, default=0.0),
        "action_count": len(actions),
        "action_unique_equipment_count": len(equipment),
        "action_correct_ratio": correct_action_count / len(actions) if actions else 0.0,
        "action_extra_count": extra_action_count,
        "action_repeated_count": repeated_action_count,
        "expected_action_count": len(expected),
        "expected_completed_count": matched_expected_count,
        "expected_completion_ratio": expected_coverage,
        "error_count": len(errors),
        "error_unique_type_count": len(error_counts),
        "error_first_at_s": max(0.0, error_times[0] - sim_start) if error_times else None,
        "error_last_at_s": max(0.0, error_times[-1] - sim_start) if error_times else None,
        "alarm_count": len(alarms),
        "alarm_active_at_end_count": sum(a.get("cleared_at") is None for a in alarms),
        "alarm_mean_relevant_action_delay_s": _mean_or_none(alarm_reaction_delays),
        "alarm_max_relevant_action_delay_s": max(alarm_reaction_delays, default=None),
    }
    row.update(_interval_features("action", action_times))
    row.update(_interval_features("error", error_times))
    row.update(_action_effect_features(actions, snapshots))
    for error_type in ERROR_TYPES:
        row[f"error_{error_type.lower()}_count"] = error_counts[error_type]
    for severity in ("HIGH", "CRITICAL"):
        row[f"alarm_severity_{severity.lower()}_count"] = alarm_severity[severity]
    return row


def build_session_dataframe(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """Return a DataFrame with one row for every session in the database."""
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if not _table_exists(conn, "sessions"):
            raise ValueError("В базе данных отсутствует таблица sessions")
        sessions = conn.execute(
            "SELECT * FROM sessions "
            "WHERE sim_end IS NOT NULL AND sim_end - sim_start >= 3.0 "
            "ORDER BY created_at"
        ).fetchall()
        return pd.DataFrame(
            [_build_row(conn, dict(session)) for session in sessions]
        ).convert_dtypes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    frame = build_session_dataframe(args.db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix.lower() == ".parquet":
        frame.to_parquet(args.output, index=False)
    else:
        frame.to_csv(args.output, index=False)
    print(f"Сохранено сессий: {len(frame)}; столбцов: {len(frame.columns)}; файл: {args.output}")


if __name__ == "__main__":
    main()
