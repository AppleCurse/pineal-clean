import { writable } from 'svelte/store';

export type Language = 'tr' | 'en';

export const currentLang = writable<Language>('tr');

export const t = {
  tr: {
    // Header & Brand
    appTitle: "PINEAL-HERETIC v3.0",
    appSubtitle: "360° BÜTÜNCÜL İNSAN TANIMA VE REZONANS İSTASYONU",
    footerText: "PINEAL 3.0 • ÇOKLU MODLU GÖRSEL ZEKA • SIFIR HALÜSİNASYON • CANLI TELEMETRİ",

    // Left Panel: Telemetry & Vault
    engineTelemetry: "MOTOR TELEMETRİSİ",
    ritualMatch: "RİTÜEL UYUMU",
    playlistResonance: "MÜZİK REZONANSI",
    envyIntensity: "TUTKU VE DERİNLİK",
    sigintFeed: "CANLI SİSTEM LOGLARI",
    active: "AKTİF",
    vaultTitle: "GÜVENLİ KASA (VAULT)",
    vaultReady: "KASA • HAZIR",
    vaultSaving: "KAYDEDİLİYOR...",
    vaultActive: "KASA • AKTİF (MÜHÜRLENDİ)",
    vaultError: "HATA",
    vaultDesc: "İstemci tabanlı • Bellekte mühürlü",
    apiKeyPlaceholder: "OPENROUTER API ANAHTARI (sk-or-v1-...)",
    cookiePlaceholder: "X/INSTAGRAM COOKIE (Opsiyonel)",
    sealBtn: "KASAYI MÜHÜRLE",

    // Center Panel: Target Input & Controls
    targetHeader: "HEDEF PROFİL VE BAĞLAM GİRİŞİ",
    liveStatus: "CANLI",
    targetUrlLabel: "HEDEF SOSYAL MEDYA URL'İ VEYA KULLANICI ADI",
    targetUrlPlaceholder: "https://instagram.com/kullanici veya @kullanici",
    ritualsLabel: "KİŞİSEL RİTÜELLER",
    ritualsPlaceholder: "Gece okumaları, felsefe, kahve",
    playlistLabel: "ÇALMA LİSTESİ / MÜZİK",
    playlistPlaceholder: "Neşet Ertaş, Klasik, Ambient",
    enviesLabel: "DERİN ARZULAR / HEDEFLER",
    enviesPlaceholder: "Sahici ve derin diyalog kurmak",
    modelSelect: "YAPAY ZEKA MOTORU",
    localBtn: "YEREL (OLLAMA)",
    apiBtn: "BULUT (OPENROUTER)",
    confidence: "GÜVEN",
    initiateBtn: "ANALİZİ BAŞLAT",
    runningBtn: "İŞLENİYOR...",

    // Aspasia & Agent Deck
    agentDeckTitle: "ASPASIA KOKPİT ŞEFİ VE DİYALOG",
    memoryStatus: "BELLEK: 1 Bütüncül Profil • Hash Doğrulandı",
    aspasiaRole: "Sistem Gözlemcisi",
    aspasiaWelcome: "Sistem çevrimiçi. Hedef verilerini ve telemetriyi incelemeye hazırım şefim.",
    you: "SİZ",
    system: "SİSTEM",
    chatPlaceholder: "Aspasia'ya soru sorun veya yönlendirin...",
    sendBtn: "GÖNDER",
    explainStateBtn: "DURUMU ÖZETLE (Neden?)",
    aspasiaObserverMode: "Aspasia Gözlemci Modu Aktif (Karar Verici Değildir)",

    // 360° Holistic Profile
    holisticTitle: "360° BÜTÜNCÜL İNSAN ÇÖZÜMLEMESİ",
    fullMap: "TAM HARİTA",
    passionsTitle: "✨ TUTKULAR VE NEŞE",
    energizingLabel: "Enerji Veren:",
    noPassions: "Henüz tespit edilmedi",
    frictionsTitle: "🛡️ HASSASİYETLER VE SINIRLAR",
    boundariesLabel: "Sınırlar:",
    noFrictions: "Belirgin sınır tespit edilmedi",
    cognitiveTitle: "💬 İLETİŞİM VE BİLİŞSEL ÜSLUP",
    toneLabel: "İletişim Tonu:",
    complexityLabel: "Karmaşıklık Düzeyi:",
    socialLabel: "Sosyal Yaklaşım:",
    bridgeTitle: "🌿 SAHİCİ DİYALOG KÖPRÜSÜ (ÖNERİLEN İLK TEMAS)",
    resonanceScore: "Rezonans",
    openingTopic: "Önerilen Açılış Konusu:",
    copyBtn: "📋 METNİ KOPYALA",
    copiedBtn: "✓ KOPYALANDI",

    // Right Panel: Agent Chain
    agentChainTitle: "AJAN ZİNCİRİ VE DURUM",
    taskLabel: "GÖREV:",
    haltedReasonTitle: "DURDURMA BİLGİSİ:",
    overallConfidence: "TOPLAM SİSTEM GÜVENİ",
    statusWait: "BEKLİYOR",
    statusRunning: "ÇALIŞIYOR",
    statusDone: "TAMAMLANDI",
    statusHalt: "DURDURULDU",
    statusFail: "BAŞARISIZ"
  },
  en: {
    // Header & Brand
    appTitle: "PINEAL-HERETIC v3.0",
    appSubtitle: "360° HOLISTIC HUMAN RECOGNITION & RESONANCE STATION",
    footerText: "PINEAL 3.0 • MULTIMODAL VISION • ZERO HALLUCINATION • REAL-TIME TELEMETRY",

    // Left Panel: Telemetry & Vault
    engineTelemetry: "ENGINE TELEMETRY",
    ritualMatch: "RITUAL MATCH",
    playlistResonance: "PLAYLIST RESONANCE",
    envyIntensity: "PASSION & DEPTH",
    sigintFeed: "SYSTEM TELEMETRY LOGS",
    active: "ACTIVE",
    vaultTitle: "SECURE VAULT (KEYSTORE)",
    vaultReady: "VAULT • READY",
    vaultSaving: "SAVING...",
    vaultActive: "VAULT • ACTIVE (SEALED)",
    vaultError: "ERROR",
    vaultDesc: "Client-based • Memory sealed",
    apiKeyPlaceholder: "OPENROUTER API KEY (sk-or-v1-...)",
    cookiePlaceholder: "X/INSTAGRAM COOKIE (Optional)",
    sealBtn: "SEAL VAULT",

    // Center Panel: Target Input & Controls
    targetHeader: "TARGET PROFILE & CONTEXT INPUT",
    liveStatus: "LIVE",
    targetUrlLabel: "TARGET SOCIAL MEDIA URL OR USERNAME",
    targetUrlPlaceholder: "https://instagram.com/target or @username",
    ritualsLabel: "PERSONAL RITUALS",
    ritualsPlaceholder: "Night reading, philosophy, coffee",
    playlistLabel: "PLAYLIST / MUSIC",
    playlistPlaceholder: "Neşet Ertaş, Classical, Ambient",
    enviesLabel: "CORE ASPIRATIONS / DESIRES",
    enviesPlaceholder: "Establishing authentic and deep dialogue",
    modelSelect: "AI ENGINE SELECTION",
    localBtn: "LOCAL (OLLAMA)",
    apiBtn: "CLOUD (OPENROUTER)",
    confidence: "CONFIDENCE",
    initiateBtn: "START ANALYSIS",
    runningBtn: "PROCESSING...",

    // Aspasia & Agent Deck
    agentDeckTitle: "ASPASIA COCKPIT CHIEF & DIALOGUE",
    memoryStatus: "MEMORY: 1 Holistic Profile • Hash Verified",
    aspasiaRole: "System Observer",
    aspasiaWelcome: "System online. Ready to inspect target evidence and telemetry chief.",
    you: "YOU",
    system: "SYSTEM",
    chatPlaceholder: "Ask Aspasia or guide the system...",
    sendBtn: "SEND",
    explainStateBtn: "EXPLAIN STATE (Why?)",
    aspasiaObserverMode: "Aspasia Observer Mode Active (Non-decision maker)",

    // 360° Holistic Profile
    holisticTitle: "360° HOLISTIC HUMAN RECOGNITION",
    fullMap: "FULL MAP",
    passionsTitle: "✨ PASSIONS & ENERGIZERS",
    energizingLabel: "Energizers:",
    noPassions: "Not detected yet",
    frictionsTitle: "🛡️ SENSITIVITIES & BOUNDARIES",
    boundariesLabel: "Boundaries:",
    noFrictions: "No distinct boundary detected",
    cognitiveTitle: "💬 COGNITIVE & COMMUNICATION STYLE",
    toneLabel: "Tone:",
    complexityLabel: "Complexity:",
    socialLabel: "Orientation:",
    bridgeTitle: "🌿 AUTHENTIC DIALOGUE BRIDGE (OPENING MESSAGE)",
    resonanceScore: "Resonance",
    openingTopic: "Opening Topic:",
    copyBtn: "📋 COPY MESSAGE",
    copiedBtn: "✓ COPIED",

    // Right Panel: Agent Chain
    agentChainTitle: "AGENT CHAIN & STATUS",
    taskLabel: "TASK:",
    haltedReasonTitle: "HALT REASON:",
    overallConfidence: "OVERALL SYSTEM CONFIDENCE",
    statusWait: "WAITING",
    statusRunning: "RUNNING",
    statusDone: "DONE",
    statusHalt: "HALTED",
    statusFail: "FAILED"
  }
};
