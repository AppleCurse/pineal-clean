//! [040] fix: GhostBrowser artık sahte kazıma verisi ÜRETMEZ.
//!
//! Eski davranış: execute_scrape() her çağrıda Ok("Scraped Data") döndürüyordu
//! — literal string, URL'e bağlı değildi ve crate'in resmî export'undaydı.
//! Gerçek implementasyon (playwright/HTTP kazıyıcı) bu tarafta YOK; bu yüzden
//! fail-closed davranış: açık hata. Gerçek kazıma tek sahiplikli platform_registry
//! (Python) üzerinden scripts/run_task.py ile yapılır ([W4.2]).

pub struct GhostBrowser {
    is_active: bool,
}

impl Default for GhostBrowser {
    fn default() -> Self {
        Self::new()
    }
}

impl GhostBrowser {
    pub fn new() -> Self {
        Self { is_active: true }
    }

    pub fn execute_scrape(&self, _url: &str) -> Result<String, String> {
        // Sahte "Scraped Data" YASAK: gerçek kazıma implementasyonu yoksa
        // başarı GÖRÜNÜMÜ üretilemez.
        Err(
            "GHOST_BROWSER_NOT_IMPLEMENTED: Rust tarafında gerçek kazıma \
             implementasyonu yok; sahte kazıma verisi ÜRETİLMEZ. Gerçek kazıma \
             scripts/run_task.py (platform_registry) üzerinden yapılır."
                .to_string(),
        )
    }
}

impl Drop for GhostBrowser {
    fn drop(&mut self) {
        self.is_active = false;
        // Clean up zombies
    }
}
