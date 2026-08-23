use reqwest::Client;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize)]
struct Message {
    role: String,
    content: String,
}

#[derive(Debug, Serialize)]
struct RequestBody {
    model: String,
    messages: Vec<Message>,
    max_tokens: u32,
    temperature: f32,
}

#[derive(Debug, Deserialize)]
struct Choice {
    message: MessageResponse,
}

#[derive(Debug, Deserialize)]
struct MessageResponse {
    content: String,
}

#[derive(Debug, Deserialize)]
struct ApiResponse {
    choices: Vec<Choice>,
}

pub struct LLMClient {
    client: Client,
    api_key: String,
}

impl LLMClient {
    pub fn new(api_key: String) -> Self {
        Self {
            client: Client::new(),
            api_key,
        }
    }

    pub async fn analyze_target(
        &self,
        username: &str,
        bio: &str,
        posts: &[String],
    ) -> Result<String, String> {
        let prompt = format!(
            r#"Sen bir OSINT (Açık Kaynak İstihbarat) analistisin.

HEDEF PROFİL:
Kullanıcı Adı: @{}
Biyografi: "{}"

SON PAYLAŞIMLAR (gerçek metinler):
{}

GÖREVİN:
1. Bu kişinin GERÇEK psikolojik profilini çıkar (şablon kullanma)
2. Biyografisindeki ve paylaşımlarındaki spesifik detayları bul (kitap adı, mekan, şarkı, duygu)
3. Bağlanma stilini tespit et (anksiyetik/kaçıngan/güvenli) - NEDEN?
4. "Core Wound" (temel yara) nedir? Hangi cümle bunu gösteriyor?
5. Bu kişiye özel, şablon OLMAYAN bir ilk mesaj öner. Mesaj, bulduğun spesifik detaya referans vermeli.

ÇIKTI FORMATI (JSON):
{{
    "real_desire": "gerçek arzusu",
    "specific_detail": "bulduğun spesifik detay",
    "attachment_style": "anksiyetik/kaçıngan/güvenli",
    "core_wound": "temel yara",
    "first_message": "şablon olmayan özel mesaj",
    "confidence": 0.0-1.0
}}"#,
            username,
            bio,
            posts.iter().map(|p| format!("- {}", p)).collect::<Vec<_>>().join("\n")
        );

        let body = RequestBody {
            model: "anthropic/claude-3.5-sonnet".to_string(),
            messages: vec![Message {
                role: "user".to_string(),
                content: prompt,
            }],
            max_tokens: 1000,
            temperature: 0.7,
        };

        let response = self
            .client
            .post("https://openrouter.ai/api/v1/chat/completions")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("API isteği başarısız: {}", e))?;

        let api_response: ApiResponse = response
            .json()
            .await
            .map_err(|e| format!("JSON parse hatası: {}", e))?;

        api_response
            .choices
            .first()
            .map(|c| c.message.content.clone())
            .ok_or_else(|| "API yanıt vermedi".to_string())
    }
}
