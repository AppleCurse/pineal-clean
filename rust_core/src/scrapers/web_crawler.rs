use crate::scrapers::{OsintResult, OsintScraper};
use async_trait::async_trait;
use reqwest::Client;
use scraper::{Html, Selector};
use std::time::Duration;

pub struct WebCrawler {
    client: Client,
}

impl WebCrawler {
    pub fn new() -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(15))
            .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (Pineal Heretic OSINT Bot)")
            .build()
            .unwrap_or_default();
        Self { client }
    }
}

#[async_trait]
impl OsintScraper for WebCrawler {
    async fn scan(&self, target_url: &str) -> Result<Vec<OsintResult>, String> {
        let mut results = Vec::new();
        
        match self.client.get(target_url).send().await {
            Ok(response) => {
                if response.status().is_success() {
                    let text_content = response.text().await.unwrap_or_default();
                    let document = Html::parse_document(&text_content);
                    
                    // Sayfa başlığını çek (Örnek Metadata)
                    let title_selector = Selector::parse("title").unwrap();
                    let title = document.select(&title_selector).next()
                        .map(|el| el.text().collect::<String>())
                        .unwrap_or_else(|| "Bilinmeyen Başlık".to_string());
                        
                    // Sayfadaki metinleri topla (Çok temel bir ekstraksiyon)
                    let p_selector = Selector::parse("p").unwrap();
                    let mut paragraphs = Vec::new();
                    for el in document.select(&p_selector).take(5) {
                        paragraphs.push(el.text().collect::<String>());
                    }
                    
                    let mut metadata_map = serde_json::Map::new();
                    metadata_map.insert("title".to_string(), serde_json::Value::String(title));
                    metadata_map.insert("paragraphs".to_string(), serde_json::to_value(paragraphs).unwrap_or(serde_json::Value::Null));

                    results.push(OsintResult {
                        target: target_url.to_string(),
                        platform: "Web Crawl".to_string(),
                        exists: true,
                        url: Some(target_url.to_string()),
                        metadata: Some(serde_json::Value::Object(metadata_map)),
                    });
                } else {
                    results.push(OsintResult {
                        target: target_url.to_string(),
                        platform: "Web Crawl".to_string(),
                        exists: false,
                        url: None,
                        metadata: None,
                    });
                }
            }
            Err(e) => {
                tracing::warn!("WebCrawler başarısız ({}): {}", target_url, e);
                return Err(format!("Crawl Hatası: {}", e));
            }
        }

        Ok(results)
    }
}
