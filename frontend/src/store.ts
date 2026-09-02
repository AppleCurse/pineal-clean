import { writable, get } from 'svelte/store';

// API adresi tek yerden yönetilir:
//  - Üretimde (FastAPI aynı origin'de servis eder): window.location.origin kullanılır.
//  - Geliştirmede (vite:5173 -> backend:8000): frontend/.env içinde VITE_API_BASE=http://127.0.0.1:8000 tanımlanır.
const envBase = (import.meta.env && (import.meta.env as any).VITE_API_BASE) as string | undefined;
const origin = typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8000';

export const API_BASE = (envBase && envBase.trim()) || origin;
export const WS_BASE = API_BASE.replace(/^http/, 'ws');

// FAZ 3: PINEAL_TOKEN kipinde UI da kimligini tasir.
// İki kaynak (öncelik sırasıyla):
//  1. Çalışma zamanı: kullanıcı arayüzden (Kasa) girdiği token — localStorage'da kalıcı.
//  2. Derleme zamanı: VITE_PINEAL_TOKEN (üretim imajına gömülür).
// Önceden token yalnızca derleme zamanında gömülebiliyordu; PINEAL_TOKEN set edilmiş
// ama VITE_PINEAL_TOKEN gömülmemişse arayüz 401'e takılıp "ağ hatası" gibi yanıltıcı
// mesajlar veriyordu (bkz. App.svelte onclose + UnifiedCompactPanel hata yolları).
const bakedToken = (((import.meta.env && (import.meta.env as any).VITE_PINEAL_TOKEN) as string | undefined) || '').trim();

const TOKEN_STORAGE_KEY = 'pineal_api_token';

function readStoredToken(): string {
  if (typeof window === 'undefined') return '';
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || '';
  } catch {
    return '';
  }
}

export const apiToken = writable<string>(readStoredToken() || bakedToken);

export function currentApiToken(): string {
  return (get(apiToken) || bakedToken).trim();
}

export function setApiToken(value: string): void {
  const v = (value || '').trim();
  apiToken.set(v);
  try {
    if (v) localStorage.setItem(TOKEN_STORAGE_KEY, v);
    else localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    /* localStorage erişilemiyorsa sessizce geç; token oturum boyunca bellekte kalır */
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  const token = currentApiToken();
  if (token) headers.set('X-API-Key', token);
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

// 401/403 yanıtını ağ hatasından ayırır; arayüzün dürüst mesaj basması için tek yardımcı.
export function isAuthFailure(res: Response): boolean {
  return res.status === 401 || res.status === 403;
}

export function wsUrl(clientId: string): string {
  // Secrets never enter URLs or proxy/access logs. The socket authenticates
  // with its first message instead.
  return `${WS_BASE}/ws/${clientId}`;
}

// Benzersiz bir istemci kimliği (session boyunca sabit)
export const clientId = writable(`client_${Math.random().toString(36).substring(2, 9)}`);

// Global state
export const logs = writable<Array<{ts: string, level: string, msg: string}>>([]);
export const taskStatus = writable<any>(null);
export const isProcessing = writable(false);
export const telemetryEvents = writable<any[]>([]);

// Scraper vb. state'ler
export const scrapedUsername = writable('');
export const scrapedBio = writable('');
export const scrapedPosts = writable<string[]>([]);
export const isScraping = writable(false);
export const autoTriggerLLM = writable(false);
