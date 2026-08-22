import { writable } from 'svelte/store';

// API adresi tek yerden yönetilir:
//  - Üretimde (FastAPI aynı origin'de servis eder): window.location.origin kullanılır.
//  - Geliştirmede (vite:5173 -> backend:8000): frontend/.env içinde VITE_API_BASE=http://127.0.0.1:8000 tanımlanır.
const envBase = (import.meta.env && (import.meta.env as any).VITE_API_BASE) as string | undefined;
const origin = typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8000';

export const API_BASE = (envBase && envBase.trim()) || origin;
export const WS_BASE = API_BASE.replace(/^http/, 'ws');

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
