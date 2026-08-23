use std::process::{Command, Stdio};
use serde::{Deserialize, Serialize};
use tauri::State;
use crate::llm_client::LLMClient;

#[derive(Serialize, Deserialize, Debug)]
pub struct IntegratedResult {
    pub psychological_profile: PsychProfile,
    pub dopamine_profile: DopamineProfile,
    pub strategy: StrategyResult,
    pub warning: String,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct PsychProfile {
    pub attachment: String,
    pub core_wound: String,
    pub exploitability: f64,
    pub dark_triad: DarkTriad,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct DopamineProfile {
    pub chase_sensitivity: f64,
    pub validation_need: f64,
    pub optimal_schedule: String,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct StrategyResult {
    pub sequence: Vec<MessageStep>,
    pub addiction_potential: f64,
    pub compliance_probability: f64,
    pub risk_level: String,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct MessageStep {
    pub phase: String,
    pub content: String,
    pub mechanism: String,
    pub delay: u64,
    pub dopamine_spike: f64,
    pub trust_building: bool,
    pub attachment_cue: Option<String>,
    pub trigger: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct DarkTriad {
    pub machiavellianism: f64,
    pub narcissism: f64,
    pub psychopathy: f64,
}

#[derive(Clone)]
pub struct AspasiaBridge;

impl AspasiaBridge {
    pub fn analyze_target(&self, target_data: serde_json::Value) -> Result<IntegratedResult, String> {
        // Python Aspasia motorunu çağır
        let python_script = format!(r#"
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'agent_core')))
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), '..', 'agent_core')))
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), 'agent_core')))

try:
    from aspasia.integrated_strategy import generate_strategy_for_rust
except ImportError as e:
    import json
    print(json.dumps({{"error": str(e)}}))
    sys.exit(1)
import json

data = json.loads('{}')
result = generate_strategy_for_rust(data)

print(json.dumps(result))
"#, target_data.to_string().replace("'", r"\'"));

        let python_path = std::env::var("PYTHONPATH").unwrap_or_default();
        let python_path = format!("{};agent_core", python_path);
        
        let output = Command::new("python")
            .env("PYTHONPATH", python_path)
            .env("PYTHONIOENCODING", "utf-8")
            .arg("-c")
            .arg(&python_script)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .map_err(|e| format!("Python execution failed: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("Aspasia error: {}", stderr));
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        let profile: IntegratedResult = serde_json::from_str(&stdout)
            .map_err(|e| format!("JSON parse error: {}\nOutput: {}", e, stdout))?;

        Ok(profile)
    }
}

// Tauri Command
#[tauri::command]
pub async fn analyze_with_aspasia(
    target_data: serde_json::Value,
    state: State<'_, crate::tauri_bridge::CoreState>,
) -> Result<IntegratedResult, String> {
    let bridge = state.aspasia_bridge.clone();
    let data = target_data.clone();
    tokio::task::spawn_blocking(move || {
        bridge.analyze_target(data)
    })
    .await
    .map_err(|e| format!("Task join error: {}", e))?
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AnalysisResult {
    pub real_desire: String,
    pub specific_detail: String,
    pub attachment_style: String,
    pub core_wound: String,
    pub first_message: String,
    pub confidence: f32,
}

#[tauri::command]
pub async fn analyze_target_real(
    username: String,
    bio: String,
    posts: Vec<String>,
    state: State<'_, crate::tauri_bridge::CoreState>,
) -> Result<AnalysisResult, String> {
    let vault_guard = state.vault.lock().await;
    let api_key = if let Some(vault) = vault_guard.as_ref() {
        vault.retrieve("OPENROUTER_API_KEY").unwrap_or_else(|_| "".to_string())
    } else {
        return Err("Vault kilitli veya erişilemiyor.".to_string());
    };

    if api_key.is_empty() {
        return Err("API anahtarı kasada yok".to_string());
    }

    let client = LLMClient::new(api_key);
    let mut response = client.analyze_target(&username, &bio, &posts).await?;

    // Daha sağlam JSON temizliği: İlk '{' ve son '}' arasını al
    if let (Some(start), Some(end)) = (response.find('{'), response.rfind('}')) {
        response = response[start..=end].to_string();
    } else {
        return Err(format!("LLM yanıtında JSON bulunamadı. Ham yanıt: {}", response));
    }

    let result: AnalysisResult = serde_json::from_str(&response)
        .map_err(|e| format!("LLM yanıtı JSON değil: {} - Ham yanıt: {}", e, response))?;

    Ok(result)
}

#[tauri::command]
pub async fn consult_aspasia(
    question: String,
    target_context: String,
    state: State<'_, crate::tauri_bridge::CoreState>,
) -> Result<String, String> {
    let vault_guard = state.vault.lock().await;
    let api_key = if let Some(vault) = vault_guard.as_ref() {
        vault.retrieve("OPENROUTER_API_KEY").unwrap_or_else(|_| "".to_string())
    } else {
        return Err("Vault kilitli veya erişilemiyor.".to_string());
    };

    if api_key.is_empty() {
        return Err("API anahtarı kasada yok".to_string());
    }

    let prompt = format!(
        r#"Sen Aspasia'sın - Mösyö'nün stratejik danışmanısın.

HEDEF DOSYASI:
{}

MÖSYÖ'NÜN SORUSU: "{}"

GÖREVİN:
1. Hedef dosyasındaki spesifik detaylara referans ver
2. Stratejik tavsiye ver (şablon kullanma)
3. Samimi, profesyonel bir danışman gibi konuş
4. Türkçe yanıt ver

YANIT:""#,
        target_context, question
    );

    let body = serde_json::json!({
        "model": "anthropic/claude-3.5-sonnet",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.8
    });

    let response = reqwest::Client::new()
        .post("https://openrouter.ai/api/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", api_key))
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("API hatası: {}", e))?;

    let json: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;
    
    json["choices"][0]["message"]["content"]
        .as_str()
        .map(|s| s.to_string())
        .ok_or_else(|| "Yanıt alınamadı".to_string())
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ScrapedPost {
    pub shortcode: String,
    pub display_url: String,
    pub caption: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ScrapedProfile {
    pub username: String,
    pub biography: Option<String>,
    pub posts: Vec<ScrapedPost>,
    pub error: Option<String>,
}

#[tauri::command]
pub async fn run_osint_scraper(target_url: String) -> Result<ScrapedProfile, String> {
    // Run the python scraper
    let python_script = r#"
import sys
import os
import json
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), '..', '..')))
from agent_core.scraper.instagram_ghost import InstagramGhostScraper, InsufficientEvidenceError
from playwright.async_api import async_playwright

async def main():
    username = sys.argv[1].strip('/').split('/')[-1]
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            scraper = InstagramGhostScraper()
            try:
                profile = await scraper.scrape_async(username, playwright_page=page)
                print(profile.model_dump_json())
            except InsufficientEvidenceError as e:
                print(json.dumps({"error": str(e)}))
            finally:
                await browser.close()
    except Exception as e:
        print(json.dumps({"error": str(e)}))

asyncio.run(main())
"#;

    // Use the venv python if available, otherwise just python
    let python_exe = if cfg!(windows) {
        "..\\venv\\Scripts\\python.exe"
    } else {
        "../venv/bin/python"
    };

    let output = Command::new(python_exe)
        .arg("-c")
        .arg(python_script)
        .arg(&target_url)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|e| format!("Python execution failed (Are you in the venv?): {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    
    // Parse the JSON. We might have other prints, so find {}
    let json_str = if let (Some(start), Some(end)) = (stdout.find('{'), stdout.rfind('}')) {
        &stdout[start..=end]
    } else {
        return Err(format!("Scraper did not return JSON. Stdout: {}, Stderr: {}", stdout, String::from_utf8_lossy(&output.stderr)));
    };

    let profile: ScrapedProfile = serde_json::from_str(json_str)
        .map_err(|e| format!("Failed to parse scraper output: {}", e))?;
        
    Ok(profile)
}
