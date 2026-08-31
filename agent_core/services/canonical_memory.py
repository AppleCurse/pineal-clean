import asyncio
import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


class MemoryState(str, Enum):
    """Machine-readable state of one task's canonical memory."""

    EMPTY = "EMPTY"
    READY = "READY"
    CORRUPTED = "CORRUPTED"


class MemoryCorruptedError(RuntimeError):
    """Raised when canonical memory exists but cannot be trusted."""

    error_code = "MEMORY_CORRUPTED"

    def __init__(self, task_id: str, reason: str, path: str):
        self.task_id = task_id
        self.reason = reason
        self.path = path
        super().__init__(f"{self.error_code}: task {task_id} canonical memory is corrupt ({reason})")


class CanonicalMemory:
    """Canonical evidence store with fail-closed corruption semantics.

    A missing task file is empty memory. An existing malformed task file is
    corrupted memory and is never interpreted as empty or overwritten by a
    normal merge. Recovery is an explicit, auditable operation.
    """

    def __init__(self, storage_path: str = "./memory/"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        self._locks = defaultdict(asyncio.Lock)

    @staticmethod
    def _validate_task_id(task_id: str):
        if not re.match(r"^[a-zA-Z0-9_-]+$", task_id):
            raise ValueError(f"Geçersiz task_id formatı: {task_id}")

    def _profile_file(self, task_id: str) -> str:
        self._validate_task_id(task_id)
        return os.path.join(self.storage_path, f"{task_id}.json")

    @staticmethod
    def _inspection(
        task_id: str,
        state: MemoryState,
        *,
        data: Optional[dict] = None,
        reason: Optional[str] = None,
    ) -> dict:
        return {
            "task_id": task_id,
            "state": state.value,
            "data": data,
            "error_code": MemoryCorruptedError.error_code if state is MemoryState.CORRUPTED else None,
            "reason": reason,
        }

    def inspect_task_memory(self, task_id: str) -> dict:
        """Return EMPTY, READY, or CORRUPTED without hiding malformed data."""
        profile_file = self._profile_file(task_id)
        if not os.path.exists(profile_file):
            return self._inspection(task_id, MemoryState.EMPTY)

        try:
            with open(profile_file, "r", encoding="utf-8") as handle:
                content = handle.read()
        except UnicodeDecodeError:
            return self._inspection(task_id, MemoryState.CORRUPTED, reason="INVALID_UTF8")

        if not content.strip():
            return self._inspection(task_id, MemoryState.CORRUPTED, reason="EMPTY_FILE")

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return self._inspection(task_id, MemoryState.CORRUPTED, reason="INVALID_JSON")

        if not isinstance(data, dict):
            return self._inspection(task_id, MemoryState.CORRUPTED, reason="INVALID_ROOT_TYPE")
        if "evidence" in data and not isinstance(data["evidence"], list):
            return self._inspection(task_id, MemoryState.CORRUPTED, reason="INVALID_EVIDENCE_TYPE")
        stored_task_id = data.get("task_id")
        if stored_task_id is not None and stored_task_id != task_id:
            return self._inspection(task_id, MemoryState.CORRUPTED, reason="TASK_ID_MISMATCH")
        return self._inspection(task_id, MemoryState.READY, data=data)

    @staticmethod
    def _atomic_write(profile_file: str, payload: str) -> None:
        temp_file = f"{profile_file}.tmp"
        with open(temp_file, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_file, profile_file)

    def _serialize(self, task_id: str, evidence: List[Dict], **metadata) -> str:
        document = {
            "task_id": task_id,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "evidence": evidence,
            "confidence": self._calculate_overall_confidence(evidence),
        }
        document.update(metadata)
        return json.dumps(document, indent=2, ensure_ascii=False, default=str)

    @staticmethod
    def _raise_if_corrupted(task_id: str, profile_file: str, inspection: dict) -> None:
        if inspection["state"] == MemoryState.CORRUPTED.value:
            raise MemoryCorruptedError(task_id, inspection["reason"] or "UNKNOWN", profile_file)

    async def merge_evidence(self, task_id: str, evidence_chain: List[Dict]):
        """Merge evidence atomically, refusing to overwrite corrupted memory."""
        profile_file = self._profile_file(task_id)

        async with self._locks[task_id]:
            inspection = await asyncio.to_thread(self.inspect_task_memory, task_id)
            self._raise_if_corrupted(task_id, profile_file, inspection)
            existing = inspection["data"] or {}
            merged = self._resolve_conflicts(existing.get("evidence", []), evidence_chain)
            payload = self._serialize(task_id, merged)
            await asyncio.to_thread(self._atomic_write, profile_file, payload)

    async def quarantine_and_reset(self, task_id: str) -> dict:
        """Explicitly archive corrupt bytes and install a valid empty document.

        This operation is intentionally separate from reads and normal writes.
        It refuses to run unless the current canonical file is corrupt.
        """
        profile_file = self._profile_file(task_id)
        async with self._locks[task_id]:
            inspection = await asyncio.to_thread(self.inspect_task_memory, task_id)
            if inspection["state"] != MemoryState.CORRUPTED.value:
                raise ValueError(f"Task {task_id} memory is not corrupted")

            recovered_at = datetime.now(timezone.utc)
            corrupt_path = (
                f"{profile_file}.corrupt."
                f"{recovered_at.strftime('%Y%m%dT%H%M%S%fZ')}"
            )
            payload = self._serialize(
                task_id,
                [],
                recovery={
                    "action": "QUARANTINE_AND_RESET",
                    "reason": inspection["reason"],
                    "recovered_at": recovered_at.isoformat(),
                    "quarantine_file": os.path.basename(corrupt_path),
                },
            )

            def activate_recovery() -> None:
                temp_file = f"{profile_file}.recovery.tmp"
                with open(temp_file, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(profile_file, corrupt_path)
                try:
                    os.replace(temp_file, profile_file)
                except BaseException:
                    # Best-effort rollback keeps the original canonical bytes at
                    # their original path if recovery activation fails.
                    os.replace(corrupt_path, profile_file)
                    raise

            await asyncio.to_thread(activate_recovery)
            logger.warning(
                "Canonical memory quarantined and reset for task %s: %s",
                task_id,
                inspection["reason"],
            )
            return {
                "task_id": task_id,
                "state": MemoryState.READY.value,
                "action": "QUARANTINE_AND_RESET",
                "previous_state": MemoryState.CORRUPTED.value,
                "reason": inspection["reason"],
                "quarantine_path": corrupt_path,
            }

    def _resolve_conflicts(self, old: List[Dict], new: List[Dict]) -> List[Dict]:
        """Preserve provenance and mark conflicting claim evidence explicitly.

        Evidence must never be silently reordered or discarded merely because a
        confidence field exists at a different nesting level. Exact duplicates
        are coalesced; conflicting claim verdicts remain visible to reviewers.
        """
        merged = []
        seen = set()
        for item in old + new:
            fingerprint = json.dumps(item, sort_keys=True, default=str)
            if fingerprint not in seen:
                seen.add(fingerprint)
                merged.append(item)

        claims = {}
        for index, item in enumerate(merged):
            result = item.get("result", {}) if isinstance(item, dict) else {}
            if not isinstance(result, dict):
                continue
            claim = result.get("claim_text")
            verdict = result.get("truth_status")
            if claim and verdict:
                claims.setdefault(claim.strip().casefold(), []).append((index, verdict))

        for entries in claims.values():
            verdicts = {verdict for _, verdict in entries}
            if len(verdicts) > 1:
                conflicting_indexes = [index for index, _ in entries]
                for index, _ in entries:
                    merged[index]["conflict_status"] = "CONTRADICTED"
                    merged[index]["conflicts_with"] = [i for i in conflicting_indexes if i != index]
        return merged

    def get_task_memory(self, task_id: str) -> dict:
        """Read trusted memory; return {} only when no canonical file exists."""
        profile_file = self._profile_file(task_id)
        inspection = self.inspect_task_memory(task_id)
        self._raise_if_corrupted(task_id, profile_file, inspection)
        return inspection["data"] or {}

    def _calculate_overall_confidence(self, evidence: List[Dict]) -> float:
        """Calculate confidence only from actual agent outputs."""
        values: List[float] = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            if item.get("evidence_type") not in (None, "agent_output"):
                continue
            result = item.get("result")
            if not isinstance(result, dict):
                continue
            confidence = result.get("confidence")
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
                values.append(float(confidence))
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)
