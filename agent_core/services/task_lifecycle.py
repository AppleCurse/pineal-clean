"""Deterministic task event sequencing and terminal-state protection."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from agent_core.schemas.telemetry import AgentEvent, AgentEventType, TelemetryEvent


class LifecycleState(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    HALTED = "HALTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = frozenset({
    LifecycleState.COMPLETED,
    LifecycleState.HALTED,
    LifecycleState.FAILED,
    LifecycleState.CANCELLED,
})


@dataclass
class LifecycleRun:
    task_id: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: LifecycleState = LifecycleState.ACTIVE
    sequence: int = 0
    fingerprints: set[str] = field(default_factory=set)
    terminal_snapshot_fingerprint: Optional[str] = None
    terminal_event_recorded: bool = False


@dataclass(frozen=True)
class LifecycleDecision:
    accepted: bool
    outcome: str
    envelope: Optional[TelemetryEvent] = None
    state: LifecycleState = LifecycleState.ACTIVE


class TaskLifecycleRegistry:
    """Room-scoped lifecycle authority.

    Sequence assignment, duplicate checks, and terminal transitions happen
    under one lock. A terminal run can never become active again.
    """

    def __init__(self):
        self._runs: Dict[str, LifecycleRun] = {}
        self._lock = threading.Lock()
        self.duplicate_events = 0
        self.rejected_terminal_events = 0
        self.rejected_terminal_mutations = 0
        self.idempotent_terminal_requests = 0

    def _run(self, task_id: str) -> LifecycleRun:
        run = self._runs.get(task_id)
        if run is None:
            run = LifecycleRun(task_id=task_id)
            self._runs[task_id] = run
        return run

    @staticmethod
    def _fingerprint(payload: object) -> str:
        if hasattr(payload, "model_dump"):
            value = payload.model_dump(mode="json", warnings=False)
        else:
            value = payload
        encoded = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _event_terminal_state(event_type: AgentEventType) -> Optional[LifecycleState]:
        if event_type == AgentEventType.TaskCompleted:
            return LifecycleState.COMPLETED
        if event_type == AgentEventType.ErrorHalt:
            return LifecycleState.HALTED
        if event_type == AgentEventType.TaskCancelled:
            return LifecycleState.CANCELLED
        return None

    @staticmethod
    def normalize_state(status: object) -> LifecycleState:
        value = getattr(status, "value", status)
        normalized = str(value or "").strip().lower()
        if normalized.startswith("halted"):
            return LifecycleState.HALTED
        if normalized in {"completed", "partially_completed"}:
            return LifecycleState.COMPLETED
        if normalized in {"failed", "error"}:
            return LifecycleState.FAILED
        if normalized in {"cancelled", "canceled"}:
            return LifecycleState.CANCELLED
        return LifecycleState.ACTIVE

    def record_event(self, event: AgentEvent) -> LifecycleDecision:
        task_id = getattr(event, "task_id", "")
        if not task_id:
            raise ValueError("Telemetry events require task_id")
        event_type = event.event_type
        fingerprint = self._fingerprint(event)

        with self._lock:
            run = self._run(task_id)
            if fingerprint in run.fingerprints:
                self.duplicate_events += 1
                return LifecycleDecision(False, "DUPLICATE", state=run.state)
            terminal_state = self._event_terminal_state(event_type)
            if run.state in TERMINAL_STATES:
                # The final snapshot can precede its terminal event in the
                # executor. Permit that one matching terminal confirmation.
                if terminal_state != run.state or run.terminal_event_recorded:
                    self.rejected_terminal_events += 1
                    return LifecycleDecision(False, "TERMINAL_STATE", state=run.state)

            run.sequence += 1
            run.fingerprints.add(fingerprint)
            if terminal_state is not None:
                run.state = terminal_state
                run.terminal_event_recorded = True
            envelope = TelemetryEvent(
                task_id=task_id,
                run_id=run.run_id,
                sequence=run.sequence,
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                event=event,
            )
            return LifecycleDecision(True, "ACCEPTED", envelope=envelope, state=run.state)

    def transition(self, task_id: str, requested: object) -> LifecycleDecision:
        requested_state = self.normalize_state(requested)
        with self._lock:
            run = self._run(task_id)
            if run.state in TERMINAL_STATES:
                if requested_state == run.state:
                    self.idempotent_terminal_requests += 1
                    return LifecycleDecision(True, "IDEMPOTENT", state=run.state)
                self.rejected_terminal_mutations += 1
                return LifecycleDecision(False, "TERMINAL_STATE", state=run.state)
            run.state = requested_state
            return LifecycleDecision(True, "TRANSITIONED", state=run.state)

    def accept_snapshot(self, snapshot: object) -> LifecycleDecision:
        task_id = getattr(snapshot, "task_id", "")
        if not task_id:
            raise ValueError("Task snapshots require task_id")
        requested_state = self.normalize_state(getattr(snapshot, "status", None))
        fingerprint = self._fingerprint(snapshot)

        with self._lock:
            run = self._run(task_id)
            if run.state in TERMINAL_STATES:
                if requested_state != run.state:
                    self.rejected_terminal_mutations += 1
                    return LifecycleDecision(False, "TERMINAL_STATE", state=run.state)
                if run.terminal_snapshot_fingerprint is None:
                    # A terminal event may reach the bus just before its final
                    # snapshot. Exactly one matching terminal snapshot is valid.
                    run.terminal_snapshot_fingerprint = fingerprint
                    return LifecycleDecision(True, "TERMINAL_SNAPSHOT", state=run.state)
                if fingerprint == run.terminal_snapshot_fingerprint:
                    return LifecycleDecision(True, "IDEMPOTENT", state=run.state)
                self.rejected_terminal_mutations += 1
                return LifecycleDecision(False, "TERMINAL_STATE", state=run.state)

            run.state = requested_state
            if requested_state in TERMINAL_STATES:
                run.terminal_snapshot_fingerprint = fingerprint
            return LifecycleDecision(True, "SNAPSHOT", state=run.state)

    def terminate(self, task_id: str, action: str) -> LifecycleDecision:
        normalized = action.strip().lower()
        if normalized == "halt":
            requested = LifecycleState.HALTED
        elif normalized in {"cancel", "cancelled", "canceled"}:
            requested = LifecycleState.CANCELLED
        else:
            raise ValueError(f"Unsupported terminal action: {action}")
        return self.transition(task_id, requested)

    def get_run(self, task_id: str) -> Optional[dict]:
        with self._lock:
            run = self._runs.get(task_id)
            if run is None:
                return None
            return {
                "task_id": run.task_id,
                "run_id": run.run_id,
                "state": run.state.value,
                "last_sequence": run.sequence,
            }

    def metrics(self) -> dict:
        with self._lock:
            return {
                "runs": len(self._runs),
                "duplicate_events": self.duplicate_events,
                "rejected_terminal_events": self.rejected_terminal_events,
                "rejected_terminal_mutations": self.rejected_terminal_mutations,
                "idempotent_terminal_requests": self.idempotent_terminal_requests,
            }
