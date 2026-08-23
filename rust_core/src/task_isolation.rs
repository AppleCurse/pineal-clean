use uuid::Uuid;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Instant;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;
use serde_json::{json, Value};
use crate::event_bus::{EventBus, AgentEvent, Severity};

#[derive(Debug, Clone)]
pub struct TaskContext {
    pub task_id: Uuid,
    pub state: HashMap<String, String>,
}

pub struct TaskManager {
    tasks: Arc<Mutex<HashMap<Uuid, TaskContext>>>,
    event_bus: Arc<EventBus>,
    python_path: String,
    scraper_path: String,
    _executor_path: String,
}

impl TaskManager {
    pub fn new(event_bus: Arc<EventBus>) -> Self {
        let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
            .unwrap_or_else(|_| "/workspace/rust_core".to_string());
        let project_root = std::path::Path::new(&manifest_dir)
            .parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(|| "/workspace".to_string());

        Self {
            tasks: Arc::new(Mutex::new(HashMap::new())),
            event_bus,
            python_path: "python3".to_string(),
            scraper_path: format!("{}/scraper.py", project_root),
            _executor_path: format!("{}/agent_core/task_executor.py", project_root),
        }
    }

    pub fn create_task(&self) -> Uuid {
        let task_id = Uuid::new_v4();
        let ctx = TaskContext { task_id, state: HashMap::new() };
        self.tasks.lock().unwrap().insert(task_id, ctx);
        task_id
    }

    pub fn get_task(&self, task_id: &Uuid) -> Option<TaskContext> {
        self.tasks.lock().unwrap().get(task_id).cloned()
    }

    pub async fn execute_isolated_task(
        &self,
        target_url: String,
        user_rituals: Vec<String>,
        user_playlist: Vec<String>,
        user_envies: Vec<String>,
    ) -> Result<String, String> {
        let task_id = self.create_task();
        let started = Instant::now();

        let _ = self.event_bus.publish(AgentEvent::TaskStarted {
            task_id,
            agent_name: "TaskManager(rust_bridge_agent)".to_string(),
            input_summary: format!(
                "X profili kaziniyor: {}, ritualer: {}, playlist: {}, envies: {}",
                target_url, user_rituals.join(", "), user_playlist.join(", "), user_envies.join(", ")
            ),
        });

        let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
            .unwrap_or_else(|_| "/workspace/rust_core".to_string());
        let project_root = std::path::Path::new(&manifest_dir)
            .parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(|| "/workspace".to_string());

        let scraper_payload = json!({
            "target_url": target_url,
            "cookies": null
        });

        let mut scraper = Command::new(&self.python_path);
        scraper
            .current_dir(&project_root)
            .arg(&self.scraper_path)
            .arg("--stdin")
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped());

        let mut scraper_child = scraper
            .spawn()
            .map_err(|e| format!("Scraper süreci başlatılamadı: {}", e))?;
        if let Some(mut stdin) = scraper_child.stdin.take() {
            let payload = serde_json::to_vec(&scraper_payload).map_err(|e| format!("Scraper JSON oluşturulamadı: {}", e))?;
            stdin.write_all(&payload).await.map_err(|e| format!("Scraper stdin yazılamadı: {}", e))?;
        }
        let scraper_output = scraper_child
            .wait_with_output()
            .await
            .map_err(|e| format!("Scraper süreci okunamadı: {}", e))?;

        if !scraper_output.status.success() {
            let stderr = String::from_utf8_lossy(&scraper_output.stderr);
            let _ = self.event_bus.publish(AgentEvent::ErrorHalt {
                task_id,
                agent_name: "TaskManager(scraper)".to_string(),
                error_code: "SCRAPER_FAILED".to_string(),
                error_message: stderr.to_string(),
                severity: Severity::Critical,
            });
            return Err(format!("Scraper hatası: {}", stderr));
        }

        let profile_data: Value = serde_json::from_slice(&scraper_output.stdout)
            .map_err(|e| format!("Scraper JSON parse hatası: {}", e))?;

        let bridge_payload = json!({
            "target_url": target_url,
            "target_profile": profile_data,
            "user_context": {
                "rituals": user_rituals,
                "playlist": user_playlist,
                "envies": user_envies
            }
        });

        let mut bridge = Command::new(&self.python_path);
        bridge
            .current_dir(&project_root)
            .arg("-m")
            .arg("agent_core.agents.rust_bridge_agent")
            .arg("--stdin")
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped());

        let mut bridge_child = bridge
            .spawn()
            .map_err(|e| format!("Rust bridge süreci başlatılamadı: {}", e))?;
        if let Some(mut stdin) = bridge_child.stdin.take() {
            let payload = serde_json::to_vec(&bridge_payload).map_err(|e| format!("Bridge JSON oluşturulamadı: {}", e))?;
            stdin.write_all(&payload).await.map_err(|e| format!("Bridge stdin yazılamadı: {}", e))?;
        }

        let output = bridge_child
            .wait_with_output()
            .await
            .map_err(|e| format!("Python bridge süreci okunamadı: {}", e))?;
        let stdout = String::from_utf8_lossy(&output.stdout);
        let stderr = String::from_utf8_lossy(&output.stderr);

        if !output.status.success() {
            let _ = self.event_bus.publish(AgentEvent::ErrorHalt {
                task_id,
                agent_name: "TaskManager(PinealExecutor)".to_string(),
                error_code: "PYTHON_EXECUTOR_FAILED".to_string(),
                error_message: format!("{}\n{}", stderr, stdout),
                severity: Severity::Critical,
            });
            return Err(format!("Executor hatası: {}", stderr));
        }

        let json_result: Value = serde_json::from_str(&stdout)
            .map_err(|e| format!("JSON parse hatası: {}, çıktı: {}", e, stdout))?;

        let status = json_result.get("status").and_then(|v| v.as_str()).unwrap_or("failed");
        if status == "failed" {
            let error_msg = json_result.get("error").and_then(|v| v.as_str()).unwrap_or("Bilinmeyen hata");
            let _ = self.event_bus.publish(AgentEvent::ErrorHalt {
                task_id,
                agent_name: "TaskManager(PinealExecutor)".to_string(),
                error_code: "EXECUTOR_ERROR".to_string(),
                error_message: error_msg.to_string(),
                severity: Severity::High,
            });
            return Err(format!("Executor hatası: {}", error_msg));
        }

        let data = &json_result;
        if let Some(analysis) = data.get("mirror_analysis") {
            let alignment_score = analysis.get("alignment_score").and_then(|v| v.as_f64()).unwrap_or(0.0) as f32;
            let anchor_count = analysis.get("authentic_anchors").and_then(|v| v.as_array()).map(|v| v.len() as u32).unwrap_or(0);
            let overall_frequency = analysis.get("user_core_frequency").and_then(|v| v.as_str()).unwrap_or("unknown").to_string();

            let _ = self.event_bus.publish(AgentEvent::FrequencyUpdate {
                task_id,
                alignment_score,
                authentic_anchor_count: anchor_count,
                overall_frequency,
            });
        }

        let _ = self.event_bus.publish(AgentEvent::StepCompleted {
            task_id,
            agent_name: "TaskManager(rust_bridge_agent)".to_string(),
            step_name: "FullPipelineCompleted".to_string(),
            output_hash: format!("{:x}", md5::compute(data.to_string())),
        });

        let duration_ms = started.elapsed().as_millis() as u64;
        let _ = self.event_bus.publish(AgentEvent::TaskCompleted {
            task_id,
            agent_name: "TaskManager(rust_bridge_agent)".to_string(),
            final_result_hash: format!("{:x}", md5::compute(stdout.to_string())),
            duration_ms,
        });

        Ok(stdout.to_string())
    }
}
