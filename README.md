# PINEAL 3.0: 360° Bütüncül İnsan Tanıma ve Sahici Rezonans Mimarisi

**PINEAL 3.0**, hedef sosyal medya profillerini (Instagram / X) anonim ve otonom olarak tarayan, fotoğrafları çoklu modlu görsel zeka (Multimodal Vision) ile inceleyen ve hedef kişiyi basmakalıp astroloji genellemelerine kaçmadan **360 derece bütüncül bir yaklaşımla (Tutkular, Neşe, Hassasiyetler, Sınırlar ve Bilişsel Üslup)** çözümleyen yeni nesil bir analiz platformudur.

---

## 1. Temel Mühendislik Felsefesi

1. **Açık Aramak Değil, İnsanı Bir Bütün Olarak Tanımak:**  
   İletişim yalnızca insanların yaraları veya zaafları üzerine kurulmaz. Sistem; kişinin hem neşelendiği, tutku duyduğu alanları hem de mesafeli durduğu sınır ve hassasiyetleri eş zamanlı haritalandırır.
2. **Klişe ve Astroloji Yasağı (Sıfır Halüsinasyon):**  
   Genel geçer kalıplar, Barnum etkisi veya temelsiz psikolojik tahminler üretilmez. Her çıkarım, profil metinlerindeki veya fotoğraflardaki **somut nesne, mekan ve alıntılara** dayanmak zorundadır.
3. **Multimodal Görsel Zeka (Vision):**  
   Instagram gibi görsel platformlarda fotoğraflar kör geçilmez; kadrajdaki nesneler (kitaplar, analog kameralar, seramikler, mekanlar, estetik dil) yapay zeka ile taranıp kanıt zincirine eklenir.
4. **Hibrit Akıl Modeli (Yerel + Küresel Güç):**  
   Hızlı durum takibi ve telemetri yerel modellerle (Ollama / Dolphin-Llama3, Gemma2) çalışırken; görsel kavrayış ve yüksek muhakeme küresel çok modlu modellerle (Gemini-2.0, Claude-3.5, GPT-4o) icra edilir.

---

## 2. Sistem Mimarisi ve Ajan Boru Hattı

```
                                  [ HEDEF PROFİL (URL / Veri) ]
                                                │
                                                ▼
                                    [ Hayalet Tarayıcı ]
                              (Playwright System Chrome + Stealth)
                                                │
                                                ▼
                                     [ VisionAnalyzer ]
                          (Multimodal Görsel Zeka: Nesne/Mekan)
                                                │
                                                ▼
                                        PinealExecutor
                                       (Merkezi Beyin)
                                                │
    ┌───────────────────────────────────────────┴───────────────────────────────────────────┐
    ▼                                           ▼                                           ▼
[ MirrorOfTruth ]                     [ AutonomousVerifier ]                     [ HumanBehaviorAnalyzer ]
(Kullanıcı Öz Frekansı)                 (Web İddia Teyidi)                         (Mikro Davranış İzleri)
    │                                           │                                           │
    └───────────────────────────────────────────┬───────────────────────────────────────────┘
                                                │
    ┌───────────────────────────────────────────┴───────────────────────────────────────────┐
    ▼                                           ▼                                           ▼
[ PassionMapper ]                      [ FrictionDetector ]                      [ CognitiveProfiler ]
(Tutkular & Neşe)                      (Hassasiyet & Sınırlar)                   (Dil Tonu & Düşünce)
    │                                           │                                           │
    └───────────────────────────────────────────┬───────────────────────────────────────────┘
                                                │
                                                ▼
                                      [ ResonanceCalculator ]
                                     (Objektif Değer Uyumu)
                                                │
                                                ▼
                                    [ ResonanceSynthesizer ]
                                  (Sahici İlk Temas Köprüsü)
                                                │
                                                ▼
                                       [ HolisticProfile ]
                                   (360° Mühürlenmiş Rapor)
                                                │
                                                ▼
                             [ Svelte UI & Aspasia Raporlaması ]
```

---

## 3. 360° Veri Modelleri (`agent_core/domain/memory_models.py`)

Sistem tüm analiz çıktılarını Pydantic V2 tip güvenliği ile doğrular:

- **`PassionProfile`**: Kişinin neşe, yaratıcılık, entelektüel merak ve coşku duyduğu somut alanlar (`core_passions`, `energizing_topics`, `flow_triggers`, `sentiment_polarity`, `evidence_quotes`).
- **`FrictionProfile`**: Kişinin sınırları, hassasiyetleri, yorulma/şikayet noktaları (`sensitivities`, `stress_triggers`, `boundary_signals`, `evidence_quotes`).
- **`CognitiveStyle`**: Dilbilimsel ton, düşünce kalıbı ve sosyal yaklaşım (`communication_tone`, `complexity_level`, `humor_style`, `social_orientation`).
- **`AuthenticBridge`**: Kullanıcı ile hedef arasındaki sahici ortak paydalar ve manipülasyondan uzak saygılı açılış mesajı (`shared_passions`, `resonance_score`, `authentic_opening_topic`, `suggested_opening_message`).
- **`HolisticProfile`**: Yukarıdaki 4 boyutun tek bir çatı altında birleştiği tam insan haritası.

---

## 4. Kurulum ve Çalıştırma

### Gereksinimler
- Python 3.10+
- Node.js & npm (Frontend için)
- Google Chrome (Playwright hayalet tarayıcı için)

### Bağımlılıkların Yüklenmesi
```bash
pip install -r requirements.txt
playwright install chromium
```

### Test Paketinin Koşturulması (123 Test)
Tüm birim, entegrasyon ve uçtan uca testleri çalıştırmak için:
```bash
python -m pytest tests/ -v
```

### Canlı Profil Çözümleme Testi
```bash
python analyze_target_instagram.py
```

### Web Arayüzü ve API Sunucusunun Başlatılması
```bash
# Backend (FastAPI - Port 8000)
python main.py

# Frontend (Svelte - Port 5173)
cd frontend
npm run dev
```

---

## 5. Doğrulama ve Test Kapsamı

Projedeki tüm fonksiyonlar ve rotalar otomatik testlerle mühürlenmiştir:
- **Toplam Test Sayısı:** 123
- **Birim Testler:** 360° Ajanlar (`passion_mapper`, `friction_detector`, `cognitive_profiler`, `resonance_synthesizer`), `uncertainty_engine`, `memory_models`.
- **Entegrasyon Testleri:** Uçtan uca `test_holistic_e2e.py`, `test_p2_release_gate.py`, `test_rust_bridge_e2e.py`.
- **Başarı Oranı:** %100 (123/123 Geçti).
