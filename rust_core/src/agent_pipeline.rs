use async_trait::async_trait;

#[derive(Debug, Clone)]
pub enum HaltReason {
    InsufficientEvidence(String),
    LlmParseError(String),
    UncertaintyHalt(String),
    NetworkTimeout,
}

impl std::fmt::Display for HaltReason {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InsufficientEvidence(msg) => write!(f, "Insufficient Evidence: {}", msg),
            Self::LlmParseError(msg) => write!(f, "LLM Parse Error: {}", msg),
            Self::UncertaintyHalt(msg) => write!(f, "Uncertainty Halt: {}", msg),
            Self::NetworkTimeout => write!(f, "Network Timeout"),
        }
    }
}

#[derive(Debug, Clone)]
pub struct AnalysisResult {
    pub confidence: f32,
    pub payload: String,
}

#[async_trait]
pub trait AgentNode {
    fn name(&self) -> &'static str;
    async fn execute(&self, input: &str) -> Result<AnalysisResult, HaltReason>;
}
