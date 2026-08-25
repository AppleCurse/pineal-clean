import json
import aiofiles
import os
import asyncio
import re
from collections import defaultdict
from typing import List, Dict
from datetime import datetime, timezone
from pydantic import BaseModel

class ProfileMemory(BaseModel):
    profile_id: str
    created_at: datetime
    last_updated: datetime
    evidence_chain: List[Dict]
    resonance_history: List[float]
    successful_approaches: List[str]
    failed_approaches: List[str]

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
        """
        Çelişkili kanıtları çözümle
        """
        # Basit çözüm: Daha yüksek confidence'lı kanıt kazanır
        all_evidence = old + new
        return sorted(all_evidence, key=lambda x: x.get('confidence', 0), reverse=True)
        
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
        if not evidence:
            return 0.0
        confidences = [e.get('result', {}).get('confidence', 0) for e in evidence]
        return sum(confidences) / len(confidences)
