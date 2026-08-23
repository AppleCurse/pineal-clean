use pineal_heretic_core::{
    ChiefEngine, AspasiaEngine, EventBus, TaskManager, StealthVault,
};
use pineal_heretic_core::tauri_bridge::{CoreState, setup_telemetry_bridge};
use std::sync::Arc;
use tokio::sync::Mutex;
use std::path::PathBuf;

// ─── FAZ 1-A: Vault Komutlari ─────────────────────────────────────────

#[tauri::command]
async fn create_vault(
    password: String,
    state: tauri::State<'_, CoreState>,
) -> Result<String, String> {
    let vault_dir = std::env::var("PINEAL_VAULT_DIR")
        .unwrap_or_else(|_| {
            let home = std::env::var("USERPROFILE")
                .or_else(|_| std::env::var("HOME"))
                .unwrap_or_else(|_| ".".to_string());
            format!("{}/.pineal_vault", home)
        });
    std::fs::create_dir_all(&vault_dir).ok();
    let vault_path = PathBuf::from(&vault_dir).join("vault.json");

    let vault = StealthVault::new(&vault_path, &password)
        .map_err(|e| format!("Vault olusturulamadi: {}", e))?;

    let mut vault_state = state.vault.lock().await;
    *vault_state = Some(vault);

    Ok("Kasa basariyla olusturuldu. Argon2id + age ile muhUrlendi.".to_string())
}

#[tauri::command]
async fn open_vault(
    password: String,
    state: tauri::State<'_, CoreState>,
) -> Result<String, String> {
    let vault_dir = std::env::var("PINEAL_VAULT_DIR")
        .unwrap_or_else(|_| {
            let home = std::env::var("USERPROFILE")
                .or_else(|_| std::env::var("HOME"))
                .unwrap_or_else(|_| ".".to_string());
            format!("{}/.pineal_vault", home)
        });
    let vault_path = PathBuf::from(&vault_dir).join("vault.json");

    if !vault_path.exists() {
        return Err("Vault dosyasi bulunamadi. Once kasa olusturun.".to_string());
    }

    let vault = StealthVault::load(&vault_path, &password)
        .map_err(|e| format!("Vault acilamadi (yanlis parola?): {}", e))?;

    let mut vault_state = state.vault.lock().await;
    *vault_state = Some(vault);

    Ok("Kasa acildi. Kimlik bilgileri kullanima hazir.".to_string())
}

// ─── FAZ 1-B: Credentials Gercek Yazma ────────────────────────────────

#[tauri::command]
async fn set_vault_credentials(
    key: String,
    value: String,
    state: tauri::State<'_, CoreState>,
) -> Result<String, String> {
    let vault_state = state.vault.lock().await;
    match vault_state.as_ref() {
        Some(vault) => {
            #[derive(serde::Serialize)]
            struct Credential { value: String }
            let cred = Credential { value };
            vault.store(&key, &cred)
                .map_err(|e| format!("Kasaya yazilamadi: {}", e))?;
            Ok(format!("{} basariyla kasaya muhUrlendi.", key))
        }
        None => Err("Kasa acik degil. Once 'Kasa Ac' veya 'Kasa Olustur' butonuna basin.".to_string()),
    }
}

// ─── FAZ 1-C: Aspasia - Kullanici Mesajini Alan Parametre ─────────────

#[tauri::command]
async fn query_aspasia(
    user_message: Option<String>,
    state: tauri::State<'_, CoreState>,
) -> Result<String, String> {
    let mut aspasia = state.aspasia.lock().await;
    let report = aspasia.report_system_overview().await;
    if let Some(msg) = user_message {
        if !msg.is_empty() {
            return Ok(format!("[Mosyo sorusu: {}]\n\n{}", msg, report));
        }
    }
    Ok(report)
}

// ─── FAZ 1-D: Analiz Baslat ───────────────────────────────────────────

#[tauri::command]
async fn start_analysis(
    target_url: String,
    _scraper_type: Option<String>,
    _user_rituals: Option<Vec<String>>,
    _user_playlist: Option<Vec<String>>,
    _user_envies: Option<Vec<String>>,
    state: tauri::State<'_, CoreState>,
) -> Result<String, String> {
    let result = state.task_manager.execute_isolated_task(
        target_url,
        _user_rituals.unwrap_or_default(),
        _user_playlist.unwrap_or_default(),
        _user_envies.unwrap_or_default(),
    ).await;
    result.map_err(|e| format!("Analiz baslatildi: {}", e))
}

// ─── Tauri Uygulama Baslangici ─────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let event_bus = Arc::new(EventBus::new(100));

    // FAZ 1-D: API key'i ENV'den oku, dummy degil
    let api_key = std::env::var("OPENROUTER_API_KEY").unwrap_or_default();

    let chief = ChiefEngine::new(100);
    let aspasia = AspasiaEngine::new(chief, api_key);

    let vault: Option<StealthVault> = None;
    let task_manager = TaskManager::new(event_bus.clone());

    let core_state = CoreState {
        task_manager: Arc::new(task_manager),
        aspasia: Arc::new(Mutex::new(aspasia)),
        vault: Arc::new(Mutex::new(vault)),
        event_bus: event_bus.clone(),
    };

    let telemetry_rx = event_bus.subscribe();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(core_state)
        .invoke_handler(tauri::generate_handler![
            start_analysis,
            query_aspasia,
            create_vault,
            open_vault,
            set_vault_credentials,
        ])
        .setup(move |app| {
            use tauri::Manager;
            let app_handle = app.handle().clone();
            setup_telemetry_bridge(app_handle, telemetry_rx);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}


