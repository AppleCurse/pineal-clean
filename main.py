import asyncio
from agent_core.task_executor import PinealExecutor
# Register pattern_interrupt dynamically
from agent_core.agents.pattern_interrupt import PatternInterrupt

async def main():
    executor = PinealExecutor()
    executor.agents['pattern_interrupt'] = PatternInterrupt()
    
    # Görev: Hedef profili analiz et ve mesaj üret
    task_input = {
        'user_profile': {
            'private_rituals': ['çay', 'kitap', 'neset_ertas'],
            'late_night_playlist': ['neşet ertaş - gönül dağı'],
            'secret_envies': ['derin bağlantılar', 'anlaşılmak'],
            'authenticity_score': 0.85
        },
        'target_profile': {
            'images': ['./target_photo_1.jpg', './target_photo_2.jpg'],
            'bio': "Hayatımı yaşıyorum 💫 Sadece pozitif enerji ✨",
            'posts': [
                "Cuma akşamı evdeyim yorgunum 😴",
                "Pazartesi motivasyonu! 💪",
                "Kimse anlamıyor beni..."
            ],
            'post_times': ['23:30', '08:00', '02:15']
        }
    }
    
    try:
        result = await executor.execute_task(task_input, task_id="op_001")
        print(f"Görev durumu: {result.status}")
        print(f"Kanıt zinciri: {len(result.evidence_chain)} adım")
        
        # Son adım: Mesaj
        if result.evidence_chain:
            final_message = result.evidence_chain[-1]['result'].get('message', '')
            if final_message:
                print(f"\nÜretilen mesaj:\n{final_message}")
            
    except Exception as e:
        print(f"Sistem hatası: {e}")
        # Hata gizlenmez, loglanır, yukarı iletilir

if __name__ == "__main__":
    asyncio.run(main())
