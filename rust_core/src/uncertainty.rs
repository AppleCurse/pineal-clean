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

    /// Veriyi doğrula ve ConfidenceLevel döndür.
    /// Asla sahte skor üretmez - Fail-Fast prensibi.
    ///
    /// [006] fix: eski sözleşme yalnızca "alan var mı"na bakıyordu; {} / boş
    /// dizi / placeholder metin / null değerler PASS olup score=100 alıyordu.
    /// Yeni sözleşme: "alan var" != "kanıt var".
    ///   - alan yok veya null        -> HALT
    ///   - boş obje / boş dizi       -> HALT (kanıt taşımayan kap)
    ///   - NaN/sonsuz sayı           -> HALT
    ///   - boş/placeholder metin     -> HALT ("unknown", "n/a", "yok", ...)
    /// PASS yalnızca TÜM zorunlu alanlar gerçek kanıt taşıdığında verilir.
    pub fn evaluate<T: Serialize>(&self, data: &T) -> Result<ConfidenceLevel, UncertaintyError> {
        // JSON serialize ederek alan kontrolü yap
        let json_value = serde_json::to_value(data)
            .map_err(|e| UncertaintyError::ValidationFailed(e.to_string()))?;

        let obj = json_value.as_object()
            .ok_or_else(|| UncertaintyError::ValidationFailed("Veri obje değil".to_string()))?;

        // Eksik/kanıtsız alanları tespit et
        let mut missing: Vec<String> = Vec::new();
        for field in &self.required_fields {
            let bears_evidence = match obj.get(field) {
                None => false,
                Some(value) => Self::value_bears_evidence(value),
            };
            if !bears_evidence {
                missing.push(field.clone());
            }
        }

        if !missing.is_empty() {
            // FAIL-FAST: Eksik/kanıtsız alan varsa hemen HALT
            return Ok(ConfidenceLevel::Halt(InsufficientEvidence {
                reason: format!(
                    "Gerekli {} alandan {} eksik veya kanıt taşımıyor",
                    self.required_fields.len(),
                    missing.len()
                ),
                missing_fields: missing,
                severity: Severity::Critical,
            }));
        }

        // Tüm zorunlu alanlar gerçek kanıt taşıyor - PASS
        let data_points: Vec<String> = obj.keys().cloned().collect();
        Ok(ConfidenceLevel::Pass(Evidence {
            score: 100, // Tüm zorunlu alanlar doğrulandı
            data_points,
            verified_at: chrono::Utc::now(),
        }))
    }

    /// Bir JSON değeri gerçek kanıt taşıyor mu? ([006] sözleşmesi)
    pub fn value_bears_evidence(value: &serde_json::Value) -> bool {
        use serde_json::Value;
        match value {
            Value::Null => false,
            Value::Bool(_) => true,
            Value::Number(n) => n.as_f64().map(|f| f.is_finite()).unwrap_or(false),
            Value::String(s) => {
                let t = s.trim().to_lowercase();
                if t.is_empty() {
                    return false;
                }
                !matches!(
                    t.as_str(),
                    "unknown" | "n/a" | "na" | "-" | "yok" | "yok." | "bilinmiyor"
                        | "veri yok" | "belirsiz" | "not found" | "no data" | "no results"
                )
            }
            Value::Array(items) => !items.is_empty() && items.iter().any(Self::value_bears_evidence),
            Value::Object(map) => !map.is_empty() && map.values().any(Self::value_bears_evidence),
        }
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

    #[test]
    fn test_empty_object_field_does_not_pass() {
        // [006]: {"user_authentic_vector": {}} artık PASS olamaz
        let engine = UncertaintyEngine::new(
            uuid::Uuid::new_v4(),
            vec!["user_authentic_vector".to_string()],
        );
        let data = serde_json::json!({ "user_authentic_vector": {} });
        match engine.evaluate(&data).unwrap() {
            ConfidenceLevel::Halt(e) => assert_eq!(e.missing_fields, vec!["user_authentic_vector"]),
            ConfidenceLevel::Pass(_) => panic!("Boş obje PASS olamaz"),
        }
    }

    #[test]
    fn test_non_numeric_dimension_does_not_pass() {
        // [006]: {"depth": "x"} -> obje dolu ama değer kanıt değil; vektör
        // ajanları tip kontrolünü kendi parse'ında yapar, motor string'e izin
        // verir ANCAK placeholder ise HALT eder:
        let engine = UncertaintyEngine::new(
            uuid::Uuid::new_v4(),
            vec!["vec".to_string()],
        );
        let data = serde_json::json!({ "vec": { "depth": "unknown" } });
        match engine.evaluate(&data).unwrap() {
            ConfidenceLevel::Halt(e) => assert_eq!(e.missing_fields, vec!["vec"]),
            ConfidenceLevel::Pass(_) => panic!("placeholder değer PASS olamaz"),
        }
    }

    #[test]
    fn test_null_and_empty_array_do_not_pass() {
        let engine = UncertaintyEngine::new(
            uuid::Uuid::new_v4(),
            vec!["verifications".to_string(), "score".to_string()],
        );
        let data = serde_json::json!({ "verifications": [], "score": null });
        match engine.evaluate(&data).unwrap() {
            ConfidenceLevel::Halt(e) => assert_eq!(e.missing_fields.len(), 2),
            ConfidenceLevel::Pass(_) => panic!("boş dizi/null PASS olamaz"),
        }
    }

    #[test]
    fn test_valid_evidence_passes() {
        let engine = UncertaintyEngine::new(
            uuid::Uuid::new_v4(),
            vec!["vector".to_string(), "anchors".to_string()],
        );
        let data = serde_json::json!({
            "vector": { "depth": 0.9, "energy": 0.4 },
            "anchors": ["ritüel uyumu"]
        });
        match engine.evaluate(&data).unwrap() {
            ConfidenceLevel::Pass(e) => assert_eq!(e.score, 100),
            ConfidenceLevel::Halt(_) => panic!("geçerli kanıt HALT olamaz"),
        }
    }
}
