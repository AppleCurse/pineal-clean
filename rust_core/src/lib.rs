//! PINEAL-HERETIC v4.0 Core Library
//! 
//! Bellek-güvenli, tip-kesin ajan orchestration motoru.

pub mod uncertainty;
pub mod vault;
pub mod event_bus;
pub mod chief;
pub mod ghost;
pub mod agent_pipeline;
pub mod task_isolation;
pub mod agents;
pub mod aspasia;
// [W4.1] tauri_bridge yalnızca masaüstü kabuğu derlemesinde (feature="tauri").
// Böylece rust_core çekirdeği CI'da webkit sistem bağımlılıkları olmadan
// derlenip test edilebilir; kabuk (src-tauri) feature'ı açar.
#[cfg(feature = "tauri")]
pub mod tauri_bridge;

pub use uncertainty::{ConfidenceLevel, UncertaintyEngine, UncertaintyError, InsufficientEvidence, Evidence, Severity};
pub use vault::{StealthVault, VaultError, EncryptedPayload};
pub use event_bus::{EventBus, AgentEvent, TelemetryEvent, Severity as EventSeverity};
pub use chief::{ChiefEngine, ExecutiveSummary};
pub use aspasia::{AspasiaEngine, ASPASIA_SYSTEM_PROMPT};
pub use ghost::GhostBrowser;
pub use agents::mirror_truth::{MirrorTruthAgent, MirrorReflection};
pub use agents::autonomous_verifier::{AutonomousVerifier, VerifierReport, VerificationResult};
pub use agents::resonance_calculator::{ResonanceCalculator, ResonanceProfile};
pub use agent_pipeline::{AgentNode, HaltReason, AnalysisResult};
pub use task_isolation::{TaskManager, TaskContext};
