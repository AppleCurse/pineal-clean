use serde::{Deserialize, Serialize};
use serde_json::Value;
use crate::agent_pipeline::{AgentNode, HaltReason, AnalysisResult};
use crate::event_bus::{AgentEvent, EventBus, Severity};
use crate::uncertainty::{UncertaintyEngine, ConfidenceLevel};
use async_trait::async_trait;
use uuid::Uuid;
use std::sync::Arc;

#[derive(Debug, Serialize, Deserialize)]
pub struct Claim {
    pub claim_text: String,
    pub category: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct VerificationResult {
    pub claim_text: String,
    pub truth_status: String,
    pub evidence_url: String,
    pub contradiction_detail: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct VerifierReport {
    pub verifications: Vec<VerificationResult>,
    pub overall_authenticity_score: f32,
}

pub struct AutonomousVerifier {
    event_bus: Arc<EventBus>,
    tavily_key: Option<String>,
}

/// [048] fix: adli telemetri hash'i SHA-256 (MD5 değil).
fn sha256_hex(text: &str) -> String {
    use sha2::Digest;
    let mut hasher = sha2::Sha256::new();
    hasher.update(text.as_bytes());
    format!("{:x}", hasher.finalize())
}

impl AutonomousVerifier {
    pub fn new(event_bus: Arc<EventBus>, tavily_key: Option<String>) -> Self {
        Self { event_bus, tavily_key }
    }
}

#[async_trait]
impl AgentNode for AutonomousVerifier {
    fn name(&self) -> &'static str {
        "AutonomousVerifier"
    }

    async fn execute(&self, input: &str) -> Result<AnalysisResult, HaltReason> {
        let task_id = Uuid::new_v4();
        let started = std::time::Instant::now();

        let _ = self.event_bus.publish(AgentEvent::TaskStarted {
            task_id,
            agent_name: self.name().to_string(),
            input_summary: "Web teyidi başlatıldı".to_string(),
        });

        if self.tavily_key.is_none() {
            let error_msg = "Eksik arama motoru anahtarı (Tavily)".to_string();
            let _ = self.event_bus.publish(AgentEvent::ErrorHalt {
                task_id,
                agent_name: self.name().to_string(),
                error_code: "HALT_NO_TAVILY".to_string(),
                error_message: error_msg.clone(),
                severity: Severity::Critical,
            });
            return Err(HaltReason::InsufficientEvidence(error_msg));
        }

        let input_data: Value = serde_json::from_str(input).map_err(|e| {
            HaltReason::LlmParseError(format!("Invalid input JSON: {}", e))
        })?;

        let tavily_api_key = self.tavily_key.as_ref().unwrap();
        let target_bio = input_data.get("target_profile")
            .and_then(|p| p.get("bio"))
            .and_then(|b| b.as_str())
            .unwrap_or("");

        // [043] fix: eski davranış fail-open'di — HTTP tamamen başarısız olsa
        // bile overall_score=1.0 kalıyordu (SIFIR kanıtla %100 otantiklik) ve
        // her arama sonucu koşulsuz "DOĞRULANDI" etiketi alıyordu (claim
        // eşleşmesi yok). Yeni sözleşme:
        //   - arama sonuçları yalnızca KAYNAK olarak kaydedilir (UNVERIFIED);
        //     gerçek claim eşleşmesi implemente edilmeden DOĞRULANDI DENMEZ
        //   - sağlayıcı/HTTP/parse hatası sessizce yutulmaz, kayda geçer
        //   - skor TEMİNAT ölçüsüdür (3 sonuç hedefine ulaşma oranı)
        let mut verifications = Vec::new();
        let mut failure_reason: Option<String> = None;

        if target_bio.is_empty() {
            failure_reason = Some("Hedef bio kanıtı yok; teyit edilecek iddia bulunamadı".to_string());
        } else {
            let client = reqwest::Client::new();
            let search_body = serde_json::json!({
                "api_key": tavily_api_key,
                "query": target_bio,
                "max_results": 3
            });

            match client.post("https://api.tavily.com/search").json(&search_body).send().await {
                Ok(res) => match res.json::<Value>().await {
                    Ok(search_json) => {
                        if let Some(results) = search_json.get("results").and_then(|r| r.as_array()) {
                            for item in results {
                                let title = item.get("title").and_then(|t| t.as_str()).unwrap_or("Bilinmeyen").to_string();
                                let url = item.get("url").and_then(|u| u.as_str()).unwrap_or("").to_string();
                                let snippet = item.get("content").and_then(|s| s.as_str()).unwrap_or("").to_string();
                                verifications.push(VerificationResult {
                                    claim_text: title,
                                    truth_status: "UNVERIFIED".to_string(),
                                    evidence_url: url,
                                    contradiction_detail: snippet,
                                });
                            }
                            if verifications.is_empty() {
                                failure_reason = Some("Arama sonuç döndürmedi".to_string());
                            }
                        } else {
                            failure_reason = Some("Arama yanıtı 'results' alanı içermiyor".to_string());
                        }
                    }
                    Err(e) => failure_reason = Some(format!("Arama yanıtı parse edilemedi: {}", e)),
                },
                Err(e) => failure_reason = Some(format!("Arama sağlayıcısına ulaşılamadı: {}", e)),
            }
        }

        if let Some(reason) = &failure_reason {
            tracing::warn!("[AutonomousVerifier] {}", reason);
        }

        // Skor: teminat kapsamı (0 sonuç -> 0.0). Kanıt yoksa uncertainty
        // motoru ([006]) boş listeyi HALT eder — sıfır kanıtla %100 imkânsız.
        let overall_score = (verifications.len() as f32 / 3.0).min(1.0);

        let report = VerifierReport {
            verifications,
            overall_authenticity_score: overall_score,
        };

        let llm_json_str = serde_json::to_string(&report).unwrap();

        let required_fields = vec![
            "verifications".to_string(),
            "overall_authenticity_score".to_string(),
        ];
        
        let engine = UncertaintyEngine::new(task_id, required_fields);
        
        let llm_data: Value = serde_json::from_str(&llm_json_str).map_err(|e| {
            HaltReason::LlmParseError(format!("LLM dönen JSON hatalı: {}", e))
        })?;

        match engine.evaluate(&llm_data) {
            Ok(ConfidenceLevel::Halt(evidence)) => {
                let error_msg = format!("LLM eksik veri döndü: {:?}", evidence.missing_fields);
                let _ = self.event_bus.publish(AgentEvent::ErrorHalt {
                    task_id,
                    agent_name: self.name().to_string(),
                    error_code: "UNCERTAINTY_HALT".to_string(),
                    error_message: error_msg.clone(),
                    severity: Severity::Critical,
                });
                return Err(HaltReason::UncertaintyHalt(error_msg));
            }
            Ok(ConfidenceLevel::Pass(_)) => {
                let _ = self.event_bus.publish(AgentEvent::StepCompleted {
                    task_id,
                    agent_name: self.name().to_string(),
                    step_name: "Uncertainty_Check_Passed".to_string(),
                    output_hash: sha256_hex(&llm_json_str),
                });
            }
            Err(e) => {
                return Err(HaltReason::LlmParseError(e.to_string()));
            }
        }

        let _ = self.event_bus.publish(AgentEvent::TaskCompleted {
            task_id,
            agent_name: self.name().to_string(),
            final_result_hash: sha256_hex(&llm_json_str),
            duration_ms: started.elapsed().as_millis() as u64,
        });

        Ok(AnalysisResult {
            confidence: overall_score,
            payload: llm_json_str,
        })
    }
}
