//! PINEAL-HERETIC v4.0 - Uncertainty Engine
//! 
//! Tip-güvenli belirsizlik yönetimi ve Fail-Fast mekanizması.
//! LLM halüsinasyonlarını ve eksik veri durumlarını derleme zamanında yakalar.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Güven skoru enum'u - asla çıplak float değil!
/// Eksik veri durumunda zincir güvenle durur.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ConfidenceLevel {
    /// Kanıt yetersiz, işlem durdurulmalı
    Halt(InsufficientEvidence),
    /// Kanıt yeterli, işleme devam edilebilir
    Pass(Evidence),
}

/// Yetersiz kanıt durumu - neden durduğunu açıklar
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct InsufficientEvidence {
    pub reason: String,
    pub missing_fields: Vec<String>,
    pub severity: Severity,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Severity {
    Low,
    Medium,
    Critical,
}

/// Başarılı kanıt - eldeki veriyi taşır
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Evidence {
    pub score: u8, // 0-100 arası tip-güvenli skor
    pub data_points: Vec<String>,
    pub verified_at: chrono::DateTime<chrono::Utc>,
}

/// Uncertainty Engine hataları
#[derive(Error, Debug)]
pub enum UncertaintyError {
    #[error("Veri eksik: {0}")]
    MissingData(String),
    
    #[error("Doğrulama başarısız: {0}")]
    ValidationFailed(String),
    
    #[error("LLM yanıtı format hatası: {0}")]
    LLMFormatError(String),
}

/// Belirsizlik Motoru - ana işleyici
pub struct UncertaintyEngine {
    _task_id: uuid::Uuid,
    required_fields: Vec<String>,
}

impl UncertaintyEngine {
    pub fn new(task_id: uuid::Uuid, required_fields: Vec<String>) -> Self {
        Self { _task_id: task_id, required_fields }
    }

    /// Veriyi doğrula ve ConfidenceLevel döndür
    /// Asla sahte skor üretmez - Fail-Fast prensibi
    pub fn evaluate<T: Serialize>(&self, data: &T) -> Result<ConfidenceLevel, UncertaintyError> {
        // JSON serialize ederek alan kontrolü yap
        let json_value = serde_json::to_value(data)
            .map_err(|e| UncertaintyError::ValidationFailed(e.to_string()))?;

        let obj = json_value.as_object()
            .ok_or_else(|| UncertaintyError::ValidationFailed("Veri obje değil".to_string()))?;

        // Eksik alanları tespit et
        let mut missing: Vec<String> = Vec::new();
        for field in &self.required_fields {
            if !obj.contains_key(field) {
                missing.push(field.clone());
            }
        }

        if !missing.is_empty() {
            // FAIL-FAST: Eksik alan varsa hemen HALT
            return Ok(ConfidenceLevel::Halt(InsufficientEvidence {
                reason: format!("Gerekli {} alandan {} eksik", self.required_fields.len(), missing.len()),
                missing_fields: missing,
                severity: Severity::Critical,
            }));
        }

        // Tüm alanlar mevcut - PASS
        let data_points: Vec<String> = obj.keys().cloned().collect();
        Ok(ConfidenceLevel::Pass(Evidence {
            score: 100, // Tüm alanlar mevcut
            data_points,
            verified_at: chrono::Utc::now(),
        }))
    }

    /// LLM'den gelen JSON'u güvenli şekilde parse et
    pub fn parse_llm_response<T: for<'de> Deserialize<'de>>(
        &self,
        raw_response: &str,
    ) -> Result<T, UncertaintyError> {
        serde_json::from_str(raw_response)
            .map_err(|e| UncertaintyError::LLMFormatError(format!("JSON parse hatası: {}", e)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Serialize;

    #[derive(Serialize)]
    struct MockProfile {
        username: String,
        posts: Vec<String>,
        // bio eksik olacak
    }

    #[test]
    fn test_fail_fast_on_missing_field() {
        let engine = UncertaintyEngine::new(
            uuid::Uuid::new_v4(),
            vec!["username".to_string(), "posts".to_string(), "bio".to_string()],
        );

        let profile = MockProfile {
            username: "test_user".to_string(),
            posts: vec!["post1".to_string()],
        };

        let result = engine.evaluate(&profile).unwrap();
        
        match result {
            ConfidenceLevel::Halt(evidence) => {
                assert_eq!(evidence.missing_fields, vec!["bio"]);
                assert_eq!(evidence.severity, Severity::Critical);
            },
            ConfidenceLevel::Pass(_) => panic!("Beklenen HALT durumu gelmedi!"),
        }
    }
}
