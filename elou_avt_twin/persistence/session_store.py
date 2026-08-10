"""
session_store.py
================
Persistent SQLite storage for operator training sessions.

The store keeps an immutable event log that doubles as the training corpus
for the AI error-classification service:

    sessions           -> one row per operator run over a scenario
    actions            -> every operator / automatic action (append-only)
    state_snapshots    -> process context before / after an action or step
    alarms             -> alarm lifecycle (raise / ack / clear)
    error_events       -> rule-based detection + AI classification slots
    expected_actions   -> ground truth reference actions of each scenario
    ai_classifications -> audit of every AI call (labelled dataset)

Storage is event-sourced: events are only inserted (never mutated), so a
session can be fully reconstructed and exported for offline AI analysis.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from models.base import Alarm, ErrorEvent, OperatorAction, SimulationState

logger = logging.getLogger("elou_avt.session_store")

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "sessions.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    scenario_id    TEXT NOT NULL,
    operator_id    TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'CREATED',
    sim_start      REAL NOT NULL DEFAULT 0.0,
    sim_end        REAL,
    wall_start     REAL NOT NULL,
    wall_end       REAL,
    scheme_version TEXT,
    performance_score REAL,
    qualification  TEXT,
    ai_verdict     TEXT,
    created_at     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    seq         INTEGER NOT NULL,
    sim_time    REAL NOT NULL,
    wall_time   REAL,
    operator_id TEXT NOT NULL,
    equipment_id TEXT NOT NULL,
    node_type   TEXT,
    action_type TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    source      TEXT NOT NULL DEFAULT 'operator_panel',
    accepted    INTEGER NOT NULL DEFAULT 1,
    reject_reason TEXT,
    UNIQUE (session_id, seq)
);

CREATE TABLE IF NOT EXISTS state_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL REFERENCES sessions(id),
    seq            INTEGER NOT NULL,
    sim_time       REAL NOT NULL,
    wall_time      REAL,
    reason         TEXT NOT NULL DEFAULT 'step',
    action_id      INTEGER REFERENCES actions(id),
    pressure       TEXT,
    temperature    TEXT,
    levels         TEXT,
    flows          TEXT,
    pump_states    TEXT,
    valve_positions TEXT,
    equipment_states TEXT,
    controller_states TEXT,
    active_alarms  TEXT,
    active_failures TEXT,
    UNIQUE (session_id, seq)
);

CREATE TABLE IF NOT EXISTS alarms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    alarm_id    TEXT NOT NULL,
    parameter   TEXT,
    severity    TEXT,
    actual_value REAL,
    threshold   REAL,
    description TEXT,
    raised_at   REAL NOT NULL,
    acked_at    REAL,
    acked_by    TEXT,
    cleared_at  REAL,
    UNIQUE (session_id, alarm_id, raised_at)
);

CREATE TABLE IF NOT EXISTS error_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL REFERENCES sessions(id),
    sim_time            REAL NOT NULL,
    action_id           INTEGER REFERENCES actions(id),
    rule_error_type     TEXT NOT NULL,
    severity            TEXT,
    expected_action     TEXT,
    cause               TEXT,
    consequence         TEXT,
    context_snapshot_id INTEGER REFERENCES state_snapshots(id),
    ai_class            TEXT,
    ai_confidence       REAL,
    ai_reasoning        TEXT,
    ai_status           TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS expected_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id TEXT NOT NULL,
    equipment_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    value       TEXT,
    deadline_t  REAL,
    description TEXT,
    consequence TEXT,
    weight      REAL NOT NULL DEFAULT 1.0,
    UNIQUE (scenario_id, equipment_id, action_type)
);

CREATE TABLE IF NOT EXISTS ai_classifications (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL REFERENCES sessions(id),
    error_event_id   INTEGER REFERENCES error_events(id),
    model            TEXT NOT NULL,
    prompt_version   TEXT,
    input_payload    TEXT NOT NULL,
    predicted_class  TEXT NOT NULL,
    confidence       REAL,
    reasoning        TEXT,
    human_correction TEXT,
    human_corrected  INTEGER NOT NULL DEFAULT 0,
    latency_ms       REAL,
    created_at       REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_actions_session     ON actions (session_id, seq);
CREATE INDEX IF NOT EXISTS idx_snapshots_session   ON state_snapshots (session_id, sim_time);
CREATE INDEX IF NOT EXISTS idx_alarms_session      ON alarms (session_id, raised_at);
CREATE INDEX IF NOT EXISTS idx_errors_session      ON error_events (session_id, sim_time);
CREATE INDEX IF NOT EXISTS idx_errors_pending      ON error_events (ai_status);
CREATE INDEX IF NOT EXISTS idx_expected_scenario   ON expected_actions (scenario_id);
CREATE INDEX IF NOT EXISTS idx_ai_session          ON ai_classifications (session_id);

CREATE TABLE IF NOT EXISTS alarm_setpoints (
    parameter    TEXT PRIMARY KEY,
    low_low      REAL,
    low          REAL,
    high         REAL,
    high_high    REAL,
    unit         TEXT,
    updated_at   REAL NOT NULL
);
"""

_ACTION_TABLES = ("actions", "state_snapshots")


def _json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _unjson(text: Optional[str], default: Any = None) -> Any:
    if text is None:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


_JSON_COLUMNS = {
    "sessions": {"ai_verdict"},
    "actions": {"old_value", "new_value"},
    "state_snapshots": {
        "pressure", "temperature", "levels", "flows", "pump_states",
        "valve_positions", "equipment_states", "controller_states",
        "active_alarms", "active_failures",
    },
    "alarms": set(),
    "error_events": set(),
    "expected_actions": {"value"},
    "ai_classifications": {"input_payload"},
}


def _decode(row: Dict[str, Any], table: str) -> Dict[str, Any]:
    """Deserialize JSON columns of a row back into Python objects."""
    out = dict(row)
    for col in _JSON_COLUMNS[table]:
        out[col] = _unjson(out.get(col))
    return out


class SessionStore:
    """SQLite-backed store for operator training sessions.

    Not thread-bound (a store may be shared across FastAPI worker threads);
    all mutations are serialized with an internal lock. Methods take an
    explicit session_id so a single store can accumulate a training corpus.
    """

    def __init__(self, path: Optional[Union[Path, str]] = None, create_dir: bool = True):
        self._path = Path(path) if path else DEFAULT_DB_PATH
        if create_dir:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA busy_timeout=5000;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        logger.info("SessionStore opened: %s", self._path)

    @classmethod
    def in_memory(cls) -> "SessionStore":
        return cls(path=":memory:")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "SessionStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_seq(self, session_id: str, table: str) -> int:
        row = self._conn.execute(
            f"SELECT COALESCE(MAX(seq), 0) + 1 FROM {table} WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row[0])

    def _touch(self, sql: str, params: tuple) -> None:
        with self._lock, self._conn:
            self._conn.execute(sql, params)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def begin_session(
        self,
        scenario_id: str,
        operator_id: str,
        session_id: Optional[str] = None,
        scheme_version: str = "",
        sim_start: float = 0.0,
        wall_time: Optional[float] = None,
    ) -> str:
        """Create a new session in CREATED state and return its id."""
        sid = session_id or uuid.uuid4().hex
        now = wall_time if wall_time is not None else time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions (id, scenario_id, operator_id, status, "
                "sim_start, wall_start, scheme_version, created_at) "
                "VALUES (?, ?, ?, 'CREATED', ?, ?, ?, ?)",
                (sid, scenario_id, operator_id, sim_start, now, scheme_version, now),
            )
        logger.info("Session started: %s scenario=%s operator=%s", sid, scenario_id, operator_id)
        return sid

    def start_session(self, session_id: str, sim_start: float = 0.0, wall_time: Optional[float] = None) -> None:
        """Move a CREATED session to RUNNING."""
        self._touch(
            "UPDATE sessions SET status='RUNNING', sim_start=?, wall_start=? WHERE id=?",
            (sim_start, wall_time if wall_time is not None else time.time(), session_id),
        )

    def finish_session(
        self,
        session_id: str,
        sim_end: float,
        score: Optional[float] = None,
        qualification: str = "",
        ai_verdict: Optional[Dict[str, Any]] = None,
        wall_time: Optional[float] = None,
    ) -> None:
        """Complete the session with score, grade and optional AI verdict."""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE sessions SET status='COMPLETED', sim_end=?, wall_end=?, "
                "performance_score=?, qualification=?, ai_verdict=? WHERE id=?",
                (
                    sim_end,
                    wall_time if wall_time is not None else time.time(),
                    score,
                    qualification,
                    _json(ai_verdict),
                    session_id,
                ),
            )

    def abort_session(self, session_id: str, reason: str = "", wall_time: Optional[float] = None) -> None:
        self._touch(
            "UPDATE sessions SET status='ABORTED', wall_end=? WHERE id=?",
            (wall_time if wall_time is not None else time.time(), session_id),
        )

    def set_ai_verdict(self, session_id: str, verdict: Dict[str, Any]) -> None:
        self._touch(
            "UPDATE sessions SET ai_verdict=? WHERE id=?",
            (_json(verdict), session_id),
        )

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return _decode(dict(row), "sessions") if row else None

    def list_sessions(self, scenario_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM sessions"
        params: tuple = ()
        if scenario_id:
            sql += " WHERE scenario_id = ?"
            params = (scenario_id,)
        sql += " ORDER BY created_at DESC LIMIT ?"
        rows = self._conn.execute(sql, params + (limit,)).fetchall()
        return [_decode(dict(r), "sessions") for r in rows]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def append_action(
        self,
        session_id: str,
        action: OperatorAction,
        wall_time: Optional[float] = None,
        accepted: bool = True,
        reject_reason: str = "",
        node_type: Optional[str] = None,
    ) -> int:
        """Append one operator action to the session log. Returns row id."""
        with self._lock, self._conn:
            seq = self._next_seq(session_id, "actions")
            cur = self._conn.execute(
                "INSERT INTO actions (session_id, seq, sim_time, wall_time, operator_id, "
                "equipment_id, node_type, action_type, old_value, new_value, source, "
                "accepted, reject_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    seq,
                    action.timestamp,
                    wall_time if wall_time is not None else time.time(),
                    action.operator_id,
                    action.equipment_id,
                    node_type,
                    action.action_type.value if hasattr(action.action_type, "value") else action.action_type,
                    _json(action.old_value),
                    _json(action.new_value),
                    action.source,
                    1 if accepted else 0,
                    reject_reason,
                ),
            )
            row_id = int(cur.lastrowid)
        logger.debug("Action logged: %s on %s", action.action_type, action.equipment_id)
        return row_id

    def get_actions(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM actions WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [_decode(dict(r), "actions") for r in rows]

    # ------------------------------------------------------------------
    # State snapshots
    # ------------------------------------------------------------------

    def append_snapshot(
        self,
        session_id: str,
        state: SimulationState,
        reason: str = "step",
        action_id: Optional[int] = None,
        sim_time: Optional[float] = None,
        wall_time: Optional[float] = None,
    ) -> int:
        """Persist a process context snapshot. Returns row id."""
        t = sim_time if sim_time is not None else state.timestamp
        with self._lock, self._conn:
            seq = self._next_seq(session_id, "state_snapshots")
            cur = self._conn.execute(
                "INSERT INTO state_snapshots (session_id, seq, sim_time, wall_time, reason, "
                "action_id, pressure, temperature, levels, flows, pump_states, valve_positions, "
                "equipment_states, controller_states, active_alarms, active_failures) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    seq,
                    t,
                    wall_time if wall_time is not None else time.time(),
                    reason,
                    action_id,
                    _json(state.pressure),
                    _json(state.temperature),
                    _json(state.level),
                    _json({"feed_flow": state.feed_flow, "product_flow": state.product_flow}),
                    _json(state.pump_states),
                    _json(state.valve_positions),
                    _json(state.equipment_states),
                    _json(state.controllers),
                    _json([a.model_dump() for a in state.alarms]),
                    _json(state.active_failures),
                ),
            )
            row_id = int(cur.lastrowid)
        return row_id

    def get_snapshots(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM state_snapshots WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [_decode(dict(r), "state_snapshots") for r in rows]

    # ------------------------------------------------------------------
    # Alarms
    # ------------------------------------------------------------------

    def append_alarm(self, session_id: str, alarm: Alarm) -> int:
        """Record an alarm raise. Returns row id (or existing id on replay)."""
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT id FROM alarms WHERE session_id=? AND alarm_id=? AND raised_at=?",
                (session_id, alarm.id, alarm.timestamp),
            ).fetchone()
            if existing:
                return int(existing["id"])
            cur = self._conn.execute(
                "INSERT INTO alarms (session_id, alarm_id, parameter, severity, actual_value, "
                "threshold, description, raised_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    alarm.id,
                    alarm.parameter,
                    alarm.severity.value if hasattr(alarm.severity, "value") else alarm.severity,
                    alarm.actual_value,
                    alarm.threshold,
                    alarm.description,
                    alarm.timestamp,
                ),
            )
            return int(cur.lastrowid)

    def update_alarm_event(
        self,
        session_id: str,
        alarm_id: str,
        acked_at: Optional[float] = None,
        acked_by: Optional[str] = None,
        cleared_at: Optional[float] = None,
    ) -> None:
        fields: List[str] = []
        params: List[Any] = []
        if acked_at is not None:
            fields.append("acked_at=?")
            params.append(acked_at)
        if acked_by is not None:
            fields.append("acked_by=?")
            params.append(acked_by)
        if cleared_at is not None:
            fields.append("cleared_at=?")
            params.append(cleared_at)
        if not fields:
            return
        params.extend((session_id, alarm_id))
        self._touch(
            f"UPDATE alarms SET {', '.join(fields)} "
            "WHERE session_id=? AND alarm_id=? AND cleared_at IS NULL",
            tuple(params),
        )

    def get_alarms(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM alarms WHERE session_id = ? ORDER BY raised_at",
            (session_id,),
        ).fetchall()
        return [_decode(dict(r), "alarms") for r in rows]

    # ------------------------------------------------------------------
    # Error events + AI classification
    # ------------------------------------------------------------------

    def append_error(
        self,
        session_id: str,
        error: ErrorEvent,
        action_id: Optional[int] = None,
        context_snapshot_id: Optional[int] = None,
    ) -> int:
        """Record a rule-detected operator error. Returns row id."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO error_events (session_id, sim_time, action_id, rule_error_type, "
                "severity, expected_action, cause, consequence, context_snapshot_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    error.timestamp,
                    action_id,
                    error.error_type,
                    error.severity.value if hasattr(error.severity, "value") else error.severity,
                    error.expected_action,
                    error.cause,
                    error.consequence,
                    context_snapshot_id,
                ),
            )
            return int(cur.lastrowid)

    def get_errors(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM error_events WHERE session_id = ? ORDER BY sim_time",
            (session_id,),
        ).fetchall()
        return [_decode(dict(r), "error_events") for r in rows]

    def link_error_action(self, error_event_id: int, action_id: int) -> None:
        """Link an error event to the operator action that triggered it."""
        self._touch(
            "UPDATE error_events SET action_id=? WHERE id=?",
            (action_id, error_event_id),
        )

    def get_unclassified_errors(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return error events still awaiting AI classification (training queue)."""
        rows = self._conn.execute(
            "SELECT * FROM error_events WHERE ai_status = 'pending' ORDER BY id LIMIT ?",
            (limit,),
        ).fetchall()
        return [_decode(dict(r), "error_events") for r in rows]

    def set_error_classification(
        self,
        error_event_id: int,
        ai_class: str,
        confidence: Optional[float] = None,
        reasoning: str = "",
    ) -> None:
        self._touch(
            "UPDATE error_events SET ai_class=?, ai_confidence=?, ai_reasoning=?, "
            "ai_status='classified' WHERE id=?",
            (ai_class, confidence, reasoning, error_event_id),
        )

    def append_ai_classification(
        self,
        session_id: str,
        predicted_class: str,
        input_payload: Dict[str, Any],
        model: str = "rule_based_v0",
        prompt_version: str = "",
        error_event_id: Optional[int] = None,
        confidence: Optional[float] = None,
        reasoning: str = "",
        latency_ms: Optional[float] = None,
    ) -> int:
        """Audit one AI classification call. This row is the labelled dataset."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO ai_classifications (session_id, error_event_id, model, prompt_version, "
                "input_payload, predicted_class, confidence, reasoning, latency_ms, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    error_event_id,
                    model,
                    prompt_version,
                    _json(input_payload),
                    predicted_class,
                    confidence,
                    reasoning,
                    latency_ms,
                    time.time(),
                ),
            )
            return int(cur.lastrowid)

    def get_classifications(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM ai_classifications WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [_decode(dict(r), "ai_classifications") for r in rows]

    def correct_classification(self, classification_id: int, correction: str) -> None:
        self._touch(
            "UPDATE ai_classifications SET human_correction=?, human_corrected=1 WHERE id=?",
            (correction, classification_id),
        )

    # ------------------------------------------------------------------
    # Expected (reference) actions
    # ------------------------------------------------------------------

    def seed_expected_actions(self, scenario_id: str, reference_actions: List[Dict[str, Any]]) -> int:
        """Insert ground-truth reference actions for a scenario (idempotent)."""
        count = 0
        with self._lock, self._conn:
            for ra in reference_actions:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO expected_actions (scenario_id, equipment_id, action_type, "
                    "value, deadline_t, description, consequence, weight) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        scenario_id,
                        ra.get("equipment", ra.get("equipment_id", "")),
                        ra.get("action", ra.get("action_type", "")),
                        _json(ra.get("value")),
                        ra.get("t", ra.get("deadline_t")),
                        ra.get("description", ""),
                        ra.get("consequence", ""),
                        ra.get("weight", 1.0),
                    ),
                )
                count += cur.rowcount
        return count

    def get_expected_actions(self, scenario_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM expected_actions WHERE scenario_id = ? ORDER BY deadline_t",
            (scenario_id,),
        ).fetchall()
        return [_decode(dict(r), "expected_actions") for r in rows]

    # ------------------------------------------------------------------
    # Alarm setpoints (manual operator overrides, survive restarts)
    # ------------------------------------------------------------------

    def save_alarm_setpoint(
        self,
        parameter: str,
        low_low: Optional[float],
        low: Optional[float],
        high: Optional[float],
        high_high: Optional[float],
        unit: str,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO alarm_setpoints (parameter, low_low, low, high, high_high, unit, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(parameter) DO UPDATE SET "
                "low_low=excluded.low_low, low=excluded.low, high=excluded.high, "
                "high_high=excluded.high_high, unit=excluded.unit, updated_at=excluded.updated_at",
                (parameter, low_low, low, high, high_high, unit, time.time()),
            )

    def clear_alarm_setpoints(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM alarm_setpoints")

    def load_alarm_setpoints(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT parameter, low_low, low, high, high_high, unit FROM alarm_setpoints ORDER BY parameter"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Dump the full session as one JSON-serializable dict (AI dataset row)."""
        session = self.get_session(session_id)
        if session is None:
            return None
        return {
            "session": session,
            "actions": self.get_actions(session_id),
            "snapshots": self.get_snapshots(session_id),
            "alarms": self.get_alarms(session_id),
            "error_events": self.get_errors(session_id),
            "ai_classifications": self.get_classifications(session_id),
        }
