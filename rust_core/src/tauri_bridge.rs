use tauri::{AppHandle, Emitter};
use tokio::sync::Mutex;
use std::sync::Arc;
use serde::{Deserialize, Serialize};


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

/// Frekans parametreleri için yapı
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FrequencyParams {
    pub rituals: Vec<String>,
    pub playlist: Vec<String>,
    pub envies: Vec<String>,
}

// 1. Tauri IPC Commands - Genişletilmiş Parametreler

#[allow(unused_variables)]
#[tauri::command]
pub async fn start_analysis(
    target_url: String,
    scraper_type: Option<String>,
    user_rituals: Option<Vec<String>>,
    user_playlist: Option<Vec<String>>,
    user_envies: Option<Vec<String>>,
    state: tauri::State<'_, CoreState>,
) -> Result<String, String> {
    // Varsayılan değerler
    let rituals = user_rituals.unwrap_or_default();
    let playlist = user_playlist.unwrap_or_default();
    let envies = user_envies.unwrap_or_default();

    // Python scraper + PinealExecutor zincirini çalıştır, gerçek veri çek
    let result = state.task_manager.execute_isolated_task(
        target_url,
        rituals,
        playlist,
        envies,
    ).await;
    
    result.map_err(|e| format!("Analiz başlatılamadı: {}", e))
}

#[tauri::command]
pub async fn query_aspasia(state: tauri::State<'_, CoreState>) -> Result<String, String> {
    let aspasia = state.aspasia.lock().await;
    let report = aspasia.report_system_overview().await;
    Ok(report)
}

#[tauri::command]
pub async fn create_vault(password: String, state: tauri::State<'_, CoreState>) -> Result<String, String> {
    let vault_path = std::path::PathBuf::from("/tmp/pineal_vault.json");

    let vault = StealthVault::new(&vault_path, &password)
        .map_err(|e| format!("Vault oluşturulamadı: {}", e))?;

    let mut vault_state = state.vault.lock().await;
    *vault_state = Some(vault);

    Ok("Vault başarıyla oluşturuldu.".to_string())
}

#[tauri::command]
pub async fn open_vault(password: String, state: tauri::State<'_, CoreState>) -> Result<String, String> {
    let vault_path = std::path::PathBuf::from("/tmp/pineal_vault.json");

    if !vault_path.exists() {
        return Err("Vault dosyası bulunamadı. Önce vault oluşturun.".to_string());
    }

    let vault = StealthVault::load(&vault_path, &password)
        .map_err(|e| format!("Vault açılamadı: {}", e))?;

    let mut vault_state = state.vault.lock().await;
    *vault_state = Some(vault);

    Ok("Vault başarıyla açıldı.".to_string())
}

#[tauri::command]
pub async fn set_vault_credentials(key: String, value: String, state: tauri::State<'_, CoreState>) -> Result<String, String> {
    let vault_state = state.vault.lock().await;

    match vault_state.as_ref() {
        Some(vault) => {
            // Veriyi şifreli olarak kasaya koy
            #[derive(Serialize)]
            struct Credential {
                value: String,
            }

            let cred = Credential { value };
            vault.store(&key, &cred)
                .map_err(|e| format!("Kasaya yazılamadı: {}", e))?;

            Ok(format!("{} başarıyla kasaya eklendi.", key))
        }
        None => Err("Vault açık değil. Önce vault oluşturun veya açın.".to_string())
    }
}

#[tauri::command]
pub async fn get_vault_credentials(key: String, state: tauri::State<'_, CoreState>) -> Result<String, String> {
    let vault_state = state.vault.lock().await;

    match vault_state.as_ref() {
        Some(vault) => {
            #[derive(Deserialize)]
            struct Credential {
                value: String,
            }

            let cred: Credential = vault.retrieve(&key)
                .map_err(|e| format!("Kasadan okunamadı: {}", e))?;

            Ok(cred.value)
        }
        None => Err("Vault açık değil. Önce vault oluşturun veya açın.".to_string())
    }
}

/// 2. Canlı Telemetri Köprüsü (EventBus -> Tauri Emit)
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
