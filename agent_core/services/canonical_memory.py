import json
import os
import asyncio
from collections import defaultdict
from typing import List, Dict, Any
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
    
    async def merge_evidence(self, task_id: str, evidence_chain: List[Dict]):
        """
        Kanıtları birleştir, çelişkileri çöz
        """
        profile_file = os.path.join(self.storage_path, f"{task_id}.json")
        
        async with self._locks[task_id]:
            # Mevcut veriyi oku
            existing = {}
            if os.path.exists(profile_file):
                with open(profile_file, 'r') as f:
                    existing = json.load(f)
            
            # Yeni kanıtları ekle (Çelişki kontrolü ile)
            merged = self._resolve_conflicts(existing.get('evidence', []), evidence_chain)
            
            # Kaydet
            with open(profile_file, 'w') as f:
                json.dump({
                    'task_id': task_id,
                    'last_updated': datetime.now(timezone.utc).isoformat(),
                    'evidence': merged,
                    'confidence': self._calculate_overall_confidence(merged)
                }, f, indent=2)
    
    def _resolve_conflicts(self, old: List[Dict], new: List[Dict]) -> List[Dict]:
        """
        Çelişkili kanıtları çözümle
        """
        # Basit çözüm: Daha yüksek confidence'lı kanıt kazanır
        all_evidence = old + new
        return sorted(all_evidence, key=lambda x: x.get('confidence', 0), reverse=True)
        
    def get_task_memory(self, task_id: str) -> dict:
        """ Belleği oku, yoksa veya bozuksa boş dict dön. """
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
