import json
import os
from typing import List, Dict

class MemoryInjector:
    """
    Kullanıcı tarafından girilen kuralları (dealbreakers) okuyup 
    ajanların sistem prompt'una KUTSAL KURALLAR olarak enjekte eder.
    """
    
    def __init__(self, memory_path: str = "./memory/learnings.json"):
        self.memory_path = memory_path

    def fetch_active_rules(self) -> str:
        """
        Geçerli kuralları okur ve prompt bloğu olarak döndürür.
        """
        if not os.path.exists(self.memory_path):
            return ""
            
        try:
            with open(self.memory_path, 'r', encoding='utf-8') as f:
                learnings = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return ""

        if not learnings:
            return ""

        # Dedub by hash just in case
        unique_rules = {}
        for rule in learnings:
            if "hash" in rule and rule["hash"] not in unique_rules:
                unique_rules[rule["hash"]] = rule
            elif "hash" not in rule:
                # Fallback if hash missing
                unique_rules[rule.get("fact")] = rule
                
        if not unique_rules:
            return ""

        rules_text = "\n".join([f"- [{r.get('tag', 'KURAL')}] {r.get('fact', '')}" for r in unique_rules.values()])
        
        injection = (
            "\n\n"
            "=========================================\n"
            "=== KUTSAL KURALLAR (OVERRIDE) ===\n"
            "Aşağıdaki kurallar mutlak gerçektir ve her türlü stratejinin/algoritmanın üstündedir.\n"
            "Bu kuralları ÇİĞNEYEMEZSİN:\n"
            f"{rules_text}\n"
            "=========================================\n"
        )
        return injection
