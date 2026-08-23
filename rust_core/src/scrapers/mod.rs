use async_trait::async_trait;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct OsintResult {
    pub target: String,
    pub platform: String,
    pub exists: bool,
    pub url: Option<String>,
    pub metadata: Option<serde_json::Value>,
}

#[async_trait]
pub trait OsintScraper: Send + Sync {
    async fn scan(&self, target: &str) -> Result<Vec<OsintResult>, String>;
}

pub mod sherlock_core;
pub mod web_crawler;
