//! [W4.3] Tauri köprüsü — YALNIZCA paylaşılan state + telemetri köprüsü.
//!
//! [009]/[047] fix: Tauri command'larının tek sahibi src-tauri/src/lib.rs'tir.
//! Bu dosyadaki ikiz implementasyonlar (/tmp'li vault yolu, parametresiz
//! query_aspasia, kayıtsız get_vault_credentials) kaldırıldı — çift sahiplik
//! davranış ayrışmasına yol açıyordu (farklı vault dosyaları, farklı imzalar).
//!
//! Kalanlar:
//! - CoreState: motorların Tauri State yönetimi için tek sarıcı
//! - TauriEventPayload + setup_telemetry_bridge: EventBus -> Svelte emit hattı

use serde::Serialize;
use tauri::{AppHandle, Emitter};
use tokio::sync::Mutex;
use std::sync::Arc;

use crate::aspasia::AspasiaEngine;
use crate::event_bus::{EventBus, TelemetryEvent};
use crate::task_isolation::TaskManager;
use crate::vault::StealthVault;

/// State wrapper to hold our core engines for Tauri
pub struct CoreState {
    pub task_manager: Arc<TaskManager>,
    pub aspasia: Arc<Mutex<AspasiaEngine>>,
    pub vault: Arc<Mutex<Option<StealthVault>>>, // Option: başlangıçta boş
    pub event_bus: Arc<EventBus>,
}

#[derive(Serialize, Clone)]
pub struct TauriEventPayload {
    pub event_type: String,
    pub data: String,
}

/// Canlı Telemetri Köprüsü (EventBus -> Tauri Emit)
pub fn setup_telemetry_bridge(app_handle: AppHandle, mut rx: tokio::sync::broadcast::Receiver<TelemetryEvent>) {
    tauri::async_runtime::spawn(async move {
        while let Ok(event) = rx.recv().await {
            // Event'i JSON'a çevir
            if let Ok(json_str) = serde_json::to_string(&event) {
                let payload = TauriEventPayload {
                    event_type: "telemetry_update".to_string(),
                    data: json_str,
                };

                // Tauri arayüzüne (Svelte) gönder
                let _ = app_handle.emit("pineal-telemetry", payload);
            }
        }
    });
}
