import json
import aiofiles
import os
import asyncio
import re
from collections import defaultdict
from typing import List, Dict
from datetime import datetime, timezone

class CanonicalMemory:
    """
    Öğrenen, unutmayan, birleştiren bellek.
    Sahte başarı kaydetmez, sadece gerçek kanıtları tutar.
    """
    
    def __init__(self, storage_path: str = "./memory/"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        self._locks = defaultdict(asyncio.Lock)
    
    @staticmethod
    def _validate_task_id(task_id: str):
        if not re.match(r"^[a-zA-Z0-9_-]+$", task_id):
            raise ValueError(f"Geçersiz task_id formatı: {task_id}")

    
    async def merge_evidence(self, task_id: str, evidence_chain: List[Dict]):
        """
        Kanıtları birleştir, çelişkileri çöz
        """
        self._validate_task_id(task_id)
        profile_file = os.path.join(self.storage_path, f"{task_id}.json")
        
        async with self._locks[task_id]:
            existing = {}
            if os.path.exists(profile_file):
                async with aiofiles.open(profile_file, 'r') as f:
                    content = await f.read()
                try:
                    existing = json.loads(content) if content.strip() else {}
                except json.JSONDecodeError:
                    # Preserve forensic material rather than silently overwriting it.
                    corrupt_path = f"{profile_file}.corrupt.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
                    await asyncio.to_thread(os.replace, profile_file, corrupt_path)
                    existing = {}

            # Yeni kanıtları ekle (Çelişki kontrolü ile)
            merged = self._resolve_conflicts(existing.get('evidence', []), evidence_chain)
            payload = json.dumps({
                'task_id': task_id,
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'evidence': merged,
                'confidence': self._calculate_overall_confidence(merged)
            }, indent=2)

            # Write then atomically replace so interrupted writes do not leave an
            # empty canonical memory file.
            temp_file = f"{profile_file}.tmp"
            async with aiofiles.open(temp_file, 'w') as f:
                await f.write(payload)
            await asyncio.to_thread(os.replace, temp_file, profile_file)
    
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
        """ Belleği oku, yoksa veya bozuksa boş dict dön. """
        self._validate_task_id(task_id)
        profile_file = os.path.join(self.storage_path, f"{task_id}.json")
        if not os.path.exists(profile_file):
            return {}
        try:
            with open(profile_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            import logging
            logging.error(f"Memory corrupted for task {task_id}")
            return {}
    
    def _calculate_overall_confidence(self, evidence: List[Dict]) -> float:
        """[036] fix: toplam güven yalnızca GERÇEK ajan çıktılarından hesaplanır.

        Doğrulama notları (deep_research), pillar özetleri ve execution_failure
        kayıtları confidence taşımaz; eski davranış bunları 0 sayıp ortalamayı
        seyreltiyordu (iyi bir şey olan doğrulama notu güveni DÜŞÜRÜYORDU).
        evidence_type'sız (eski format) kayıtlar geriye uyumluluk için dahil
        edilir; result dict değilse güvenli atlanır.
        """
        values: List[float] = []
        for e in evidence:
            if not isinstance(e, dict):
                continue
            if e.get("evidence_type") not in (None, "agent_output"):
                continue
            result = e.get("result")
            if not isinstance(result, dict):
                continue
            confidence = result.get("confidence")
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
                values.append(float(confidence))
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)
