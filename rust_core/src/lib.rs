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
