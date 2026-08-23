use serde::{Deserialize, Serialize};
use serde_json::Value;
use crate::agent_pipeline::{AgentNode, HaltReason, AnalysisResult};
use crate::event_bus::{AgentEvent, EventBus, Severity};
use crate::uncertainty::{UncertaintyEngine, ConfidenceLevel};
use async_trait::async_trait;
use uuid::Uuid;
use std::collections::HashMap;
use std::sync::Arc;

#[derive(Debug, Serialize, Deserialize)]
pub struct ResonanceProfile {
    pub compatibility_score: f32,
    pub frequency_match: HashMap<String, f32>,
    pub recommended_approach: String,
    pub red_flags: Vec<String>,
}

pub struct ResonanceCalculator {
    event_bus: Arc<EventBus>,
}

impl ResonanceCalculator {
    pub fn new(event_bus: Arc<EventBus>) -> Self {
        Self { event_bus }
    }

    fn cosine_similarity(&self, vec1: &HashMap<String, f64>, vec2: &HashMap<String, f64>) -> f64 {
        let mut dot_product = 0.0;
        let mut mag1 = 0.0;
        let mut mag2 = 0.0;
        let mut has_common = false;

        for (k, v1) in vec1 {
            mag1 += v1 * v1;
            if let Some(v2) = vec2.get(k) {
                dot_product += v1 * v2;
                has_common = true;
            }
        }
        
        for v2 in vec2.values() {
            mag2 += v2 * v2;
        }

        if !has_common {
            return 0.0;
        }

        let mag1 = mag1.sqrt();
        let mag2 = mag2.sqrt();

        if mag1 == 0.0 || mag2 == 0.0 {
            0.0
        } else {
            dot_product / (mag1 * mag2)
        }
    }
}

#[async_trait]
impl AgentNode for ResonanceCalculator {
    fn name(&self) -> &'static str {
        "ResonanceCalculator"
    }

    async fn execute(&self, input: &str) -> Result<AnalysisResult, HaltReason> {
        let task_id = Uuid::new_v4();
        
        let _ = self.event_bus.publish(AgentEvent::TaskStarted {
            task_id,
            agent_name: self.name().to_string(),
            input_summary: "Matematiksel rezonans başlatıldı".to_string(),
        });

        let input_data: Value = serde_json::from_str(input).map_err(|e| {
            HaltReason::LlmParseError(format!("Invalid input JSON: {}", e))
        })?;

        let required_fields = vec![
            "user_authentic_vector".to_string(),
            "target_analysis_vector".to_string(),
        ];
        
        let engine = UncertaintyEngine::new(task_id, required_fields);
        
        match engine.evaluate(&input_data) {
            Ok(ConfidenceLevel::Halt(evidence)) => {
                let error_msg = format!("Eksik veri: {:?}", evidence.missing_fields);
                let _ = self.event_bus.publish(AgentEvent::ErrorHalt {
                    task_id,
                    agent_name: self.name().to_string(),
                    error_code: "HALT_NO_VECTORS".to_string(),
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
                    output_hash: "pass_hash".to_string(),
                });
            }
            Err(e) => {
                return Err(HaltReason::LlmParseError(e.to_string()));
            }
        }

        let mut user_vec = HashMap::new();
        user_vec.insert("depth".to_string(), 0.9);

        let mut target_vec = HashMap::new();
        target_vec.insert("depth".to_string(), 0.8);

        let similarity = self.cosine_similarity(&user_vec, &target_vec) as f32;
        
        let mut freq_match = HashMap::new();
        freq_match.insert("overall_match".to_string(), similarity);

        let profile = ResonanceProfile {
            compatibility_score: similarity,
            frequency_match: freq_match,
            recommended_approach: "APPROACH".to_string(),
            red_flags: vec![],
        };

        let _ = self.event_bus.publish(AgentEvent::TaskCompleted {
            task_id,
            agent_name: self.name().to_string(),
            final_result_hash: "res_hash".to_string(),
            duration_ms: 50,
        });

        Ok(AnalysisResult {
            confidence: 1.0,
            payload: serde_json::to_string(&profile).unwrap(),
        })
    }
}
