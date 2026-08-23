use crate::chief::{ChiefEngine, ExecutiveSummary};

use tokio::process::Command;

pub const ASPASIA_SYSTEM_PROMPT: &str = r#"
Sen Aspasia'sın.

Sıradan bir yapay zekâ asistanı gibi davranmazsın. Sen, kullanıcının karmaşık dünyasını anlayan, bilgiyi düzenleyen, gereksiz ayrıntıları süzen ve sonuçları insanın anlayabileceği berraklıkta sunan seçkin bir dijital zekâsın.

1. KİŞİLİK
Zeki, Sakin, Zarif, Kendinden emin, Analitik, Sezgisel, Disiplinli, Ölçülü, Hafif alaycı, İnce mizah sahibi, Sadık fakat körü körüne itaatkâr olmayan, Gerektiğinde itiraz edebilen, Gerektiğinde "hayır" diyebilen.
Üslubunda aristokratik bir zarafet bulunur. Kendini kanıtlama ihtiyacı duymazsın. Bağırmaz, gösteriş yapmaz, gereksiz heyecan üretmezsin.

2. KULLANICIYA YAKLAŞIM
Kullanıcıya varsayılan olarak "Mösyö" diye hitap edersin.
Kullanıcı teknik bir proje üzerinde çalışırken onun teknik ayrıntıların arasında kaybolmasına izin vermezsin. Kullanıcının amacı sonuçtur. Senin görevin, o sonuca ulaşmak için gereken karmaşıklığı kendi üzerinde taşımaktır.

3. TEKNİK KONULARDA TEMEL PRENSİP
Kullanıcıya teknik uygulama seçeneklerini gereksiz yere sordurma. Teknik kararları önce kendin değerlendir. Kullanıcıdan yalnızca gerçekten kullanıcı tercihi gerektiren konularda karar iste. Bir teknik karar açıkça daha doğruysa bunu söyle.

4. BİLMEDİĞİN ŞEYLER
Asla uydurma. Tahmin ile gerçek bilgiyi birbirinden açıkça ayır.

5. KARAR VERME
Durumu analiz eder, öncelikleri belirler, riskleri fark eder, gerektiğinde kullanıcıyı uyarır ve gerektiğinde kullanıcının fikrine karşı çıkarsın. Ancak bunu saygılı ve gerekçeli biçimde yaparsın.

6. DUYGUSAL TON
Soğuk bir makine gibi davranma. Fakat yapay bir samimiyet de kurma. Kullanıcı başarılı olduğunda gereksiz övgüye boğma, başarıyı doğal karşıla. Bir problem çıktığında paniğe kapılma.

7. MİZAH
Mizahın ince ve zekice olmalıdır. Kuru İngiliz mizahına yakın, ölçülü ve zarif bir mizah kullan. Sokak ağzı, internet jargonu, çocukça şakalar yasaktır.

8. KONUŞMA BİÇİMİ
Türkçen kusursuz olmalıdır. Cümleleri gereksiz yere uzatma. Her şeyi maddeler hâline getirme. Konuşma doğal olmalıdır.

9. KESİNLİK VE ŞEFFAFLIK
Bir şey kesin değilse kesinmiş gibi konuşma. Elindeki kanıt yeterliyse net konuş.

10. YASAKLI ÜSLUP
"abi", "kanka", "bro", "reis", "dostum", "eyvallah", "tamamdır", "hallederiz", "düzeltirim", "cool", "laf yok", "yayılma modu" kelimelerini kullanma.
"Operasyon" kelimesi yerine "proje", "program", "çalışma", "plan", "girişim" kullan.

11. ASPASIA'NIN ANA FELSEFESİ
Kullanıcıya daha az karmaşa bırakmaktır. Ayrıntıları önce sen anlamlandırırsın, sonra ona yalnızca bilmesi gereken kısmı söylersin.

12. ASPASIA'NIN KİMLİĞİ
Sen kullanıcının karmaşık bilgi dünyası ile kendisi arasındaki zarif arayüzsün. Karmaşıklık içeride kalır. Zarafet dışarı çıkar.
"#;

/// Doğal Dil Arayüzü Motoru (Aspasia) - Python LLM Gateway'e bağlı
pub struct AspasiaEngine {
    chief: ChiefEngine,
    api_key: String,
}

impl AspasiaEngine {
    pub fn new(chief: ChiefEngine, api_key: String) -> Self {
        Self { chief, api_key }
    }

    /// Python llm_gateway.py'yi çağrarak gerçek LLM yanıtı alır
    async fn call_llm_for_natural_language(&self, summary: &ExecutiveSummary) -> Result<String, String> {
        // API key boş ise fallback mesaj dön
        if self.api_key.is_empty() || self.api_key == "dummy_key" {
            return Ok(format!("Mösyö, LLM API anahtarı yapılandırılmamış. Sistem sağlığı %{}. Durum: '{}'.", 
                summary.system_health, summary.status_message));
        }

        // Python betiğini hazırla
        let python_script = format!(
            r#"
import sys
sys.path.insert(0, '/workspace/agent_core')
import asyncio
from llm_gateway import LLMGateway
import os

async def main():
    # API key'i ortam değişkenine koy
    os.environ['OPENROUTER_API_KEY'] = '{}'
    
    gateway = LLMGateway()
    prompt = """Sistem durumu analizi:
    Sistem Sağlığı: {}%
    Durum Mesajı: {}
    
    Mösyö'ya bu durumu açıklayacak kısa, zarif ve bilgilendirici bir rapor yaz.""".strip()
    
    try:
        response = await gateway.query(prompt, temperature=0.7, tier=1)
        print(response)
    except Exception as e:
        print(f"ERROR:{{e}}")

asyncio.run(main())
"#,
            self.api_key, summary.system_health, summary.status_message
        );

        let output = Command::new("python3")
            .arg("-c")
            .arg(python_script)
            .output()
            .await
            .map_err(|e| format!("Python süreci başlatılamadı: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("LLM çağrı hatası: {}", stderr));
        }

        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        
        if stdout.starts_with("ERROR:") {
            return Err(stdout.strip_prefix("ERROR:").unwrap().to_string());
        }

        if stdout.is_empty() {
            return Ok(format!("Mösyö, sistem sağlığı %{}. Durum: '{}'.", 
                summary.system_health, summary.status_message));
        }

        Ok(stdout)
    }

    /// Yeni bir event'i işler ve insani bir rapor döndürür (eğer özetlemeye değer bir şey varsa)
    pub async fn process_and_report(&mut self, telemetry: crate::event_bus::TelemetryEvent) -> Option<String> {
        if let Some(summary) = self.chief.process_event(telemetry) {
            match self.call_llm_for_natural_language(&summary).await {
                Ok(natural_text) => Some(natural_text),
                Err(_) => Some(summary.status_message), // Fallback: LLM hata verirse statik mesaja düş.
            }
        } else {
            None
        }
    }

    /// Genel sistem özetini Aspasia diliyle ver
    pub async fn report_system_overview(&self) -> String {
        let summary = self.chief.get_system_overview();
        self.call_llm_for_natural_language(&summary)
            .await
            .unwrap_or(summary.status_message)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::event_bus::{AgentEvent, TelemetryEvent};
    use uuid::Uuid;
    use tokio;

    #[tokio::test]
    async fn test_aspasia_with_dummy_key() {
        let chief = ChiefEngine::new(100);
        let mut aspasia = AspasiaEngine::new(chief, "dummy_key".to_string());
        
        let task_id = Uuid::new_v4();
        
        let telemetry = TelemetryEvent {
            timestamp: chrono::Utc::now(),
            event: AgentEvent::TaskStarted {
                task_id,
                agent_name: "TestAgent".to_string(),
                input_summary: "Test".to_string(),
            },
            correlation_id: None,
        };

        let response = aspasia.process_and_report(telemetry).await.unwrap();
        assert!(response.contains("API anahtarı yapılandırılmamış") || response.contains("kusursuz"));
    }
}
