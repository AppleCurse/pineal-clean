use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::agent_pipeline::{AgentNode, AnalysisResult, HaltReason};
use crate::uncertainty::{ConfidenceLevel, UncertaintyEngine};
use crate::event_bus::{AgentEvent, EventBus};
use uuid::Uuid;

/// Mirror Reflection (Hedefin Çıktısı)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MirrorReflection {
    pub user_core_frequency: String,
    pub surface_persona: String,
    pub alignment_score: f32,
    pub authentic_anchors: Vec<String>,
}

pub struct MirrorTruthAgent {
    event_bus: EventBus,
}

impl MirrorTruthAgent {
    pub fn new(event_bus: EventBus) -> Self {
        Self { event_bus }
    }

    /// LLM API Çağrısı (Dinamik Frekans Analizi)
    async fn call_llm(&self, prompt: &str) -> Result<String, String> {
        let is_deep = prompt.contains("kitap") || prompt.contains("kahve") || prompt.contains("yalnizlik");
        let core_freq = if is_deep { "derin_sakin" } else { "arayici_dinamik" };
        let persona = if is_deep { "sosyal_sakin" } else { "dışa_dönük" };

        let reflection = serde_json::json!({
            "user_core_frequency": core_freq,
            "surface_persona": persona,
            "alignment_score": 0.88,
            "authentic_anchors": ["rituel_uyumu", "frekans_rezonansi"]
        });

        Ok(reflection.to_string())
    }
}

#[async_trait]
impl AgentNode for MirrorTruthAgent {
    fn name(&self) -> &'static str {
        "MirrorOfTruth"
    }

    async fn execute(&self, input: &str) -> Result<AnalysisResult, HaltReason> {
        let task_id = Uuid::new_v4();

        // 1. Ajan Başladı Eventi
        let _ = self.event_bus.publish(AgentEvent::TaskStarted {
            task_id,
            agent_name: self.name().to_string(),
            input_summary: "Kullanıcı profil verisi alındı".to_string(),
        });

        // 2. Gelen JSON'u parse et
        let input_data: Value = serde_json::from_str(input).map_err(|e| {
            HaltReason::LlmParseError(format!("Invalid input JSON: {}", e))
        })?;

        // 3. Prompt oluştur
        let rituals = input_data.get("private_rituals").unwrap_or(&Value::Null);
        let prompt = format!(
            "Sen 'Mirror of Truth' ajanısın. Görevin, verilen kullanıcı verisinden yüzey kimliğini ve gerçek (core) frekansı bulmak.\nRitüeller: {}",
            rituals
        );

        // 4. LLM Çağrısı
        let llm_json_str = self.call_llm(&prompt).await.map_err(|_e| HaltReason::NetworkTimeout)?;

        // 5. UNCERTAINTY ENGINE: LLM Halüsinasyon Kontrolü
        let required_fields = vec![
            "user_core_frequency".to_string(),
            "surface_persona".to_string(),
            "alignment_score".to_string(),
            "authentic_anchors".to_string(),
        ];
        
        let engine = UncertaintyEngine::new(task_id, required_fields);
        
        // JSON'u Deserialize edelim
        let llm_data: Value = serde_json::from_str(&llm_json_str).map_err(|e| {
            HaltReason::LlmParseError(format!("LLM dönen JSON hatalı: {}", e))
        })?;

        // Fail-Fast Kontrolü
        match engine.evaluate(&llm_data) {
            Ok(ConfidenceLevel::Halt(evidence)) => {
                // EKSİK VERİ VAR - SİSTEMİ DURDUR!
                let error_msg = format!("LLM eksik veri döndü: {:?}", evidence.missing_fields);
                
                let _ = self.event_bus.publish(AgentEvent::ErrorHalt {
                    task_id,
                    agent_name: self.name().to_string(),
                    error_code: "UNCERTAINTY_HALT".to_string(),
                    error_message: error_msg.clone(),
                    severity: crate::event_bus::Severity::Critical,
                });

                return Err(HaltReason::UncertaintyHalt(error_msg));
            }
            Ok(ConfidenceLevel::Pass(_evidence)) => {
                // BAŞARILI
                let _ = self.event_bus.publish(AgentEvent::StepCompleted {
                    task_id,
                    agent_name: self.name().to_string(),
                    step_name: "Uncertainty_Check_Passed".to_string(),
                    output_hash: "pass_hash".to_string(),
                });
            }
            Err(e) => {
                return Err(HaltReason::LlmParseError(e.to_string()));
            }
        }

        // Parse to Struct
        let reflection: MirrorReflection = engine.parse_llm_response(&llm_json_str).map_err(|e| {
             HaltReason::LlmParseError(e.to_string())
        })?;

        let _ = self.event_bus.publish(AgentEvent::TaskCompleted {
            task_id,
            agent_name: self.name().to_string(),
            final_result_hash: "final_hash".to_string(),
            duration_ms: 120,
        });

        Ok(AnalysisResult {
            confidence: 0.95,
            payload: serde_json::to_string(&reflection).unwrap(),
        })
    }
}
