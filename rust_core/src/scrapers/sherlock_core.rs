use crate::scrapers::{OsintResult, OsintScraper};
use async_trait::async_trait;
use reqwest::Client;
use std::time::Duration;

pub struct SherlockCore {
    client: Client,
    platforms: Vec<(&'static str, &'static str)>,
}

impl SherlockCore {
    pub fn new() -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(10))
            .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .build()
            .unwrap_or_default();
            
        // Gerçek Sherlock gibi temel bir platform listesi
        let platforms = vec![
            ("GitHub", "https://github.com/{}"),
            ("Instagram", "https://www.instagram.com/{}/"),
            ("Twitter", "https://twitter.com/{}"),
            ("Reddit", "https://www.reddit.com/user/{}"),
            ("HackerNews", "https://news.ycombinator.com/user?id={}"),
        ];

        Self { client, platforms }
    }
}

#[async_trait]
impl OsintScraper for SherlockCore {
    async fn scan(&self, target: &str) -> Result<Vec<OsintResult>, String> {
        let mut results = Vec::new();

        for (platform, url_template) in &self.platforms {
            let target_url = url_template.replace("{}", target);
            
            // Gerçek HTTP çağrısı
            match self.client.get(&target_url).send().await {
                Ok(response) => {
                    let exists = response.status().is_success();
                    
                    // Sahte pozitifleri (404 yerine 200 dönüp 'user not found' diyen siteleri)
                    // engellemek için içerik analizi eklenebilir, şimdilik statü kodu ile yetiniyoruz.
                    results.push(OsintResult {
                        target: target.to_string(),
                        platform: platform.to_string(),
                        exists,
                        url: if exists { Some(target_url.clone()) } else { None },
                        metadata: None,
                    });
                }
                Err(e) => {
                    // Ağ hatası (timeout vb.) durumunda logla ama devam et
                    tracing::warn!("SherlockCore ağı hatası ({}): {}", platform, e);
                }
            }
        }

        Ok(results)
    }
}
