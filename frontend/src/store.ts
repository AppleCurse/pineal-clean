import { writable } from 'svelte/store';

// Benzersiz bir istemci kimliği (session boyunca sabit)
export const clientId = writable(`client_${Math.random().toString(36).substring(2, 9)}`);

// API URL (FastAPI)
export const API_BASE = 'http://127.0.0.1:8000';
export const WS_BASE = 'ws://127.0.0.1:8000';

// Global state
export const logs = writable<Array<{ts: string, level: string, msg: string}>>([]);
export const taskStatus = writable<any>(null);
export const isProcessing = writable(false);
export const telemetryEvents = writable<any[]>([]);

// Eski Ghost scraper vb. state'leri (eğer hala lazımsa)
export const scrapedUsername = writable('');
export const scrapedBio = writable('');
export const scrapedPosts = writable<string[]>([]);
export const isScraping = writable(false);
export const autoTriggerLLM = writable(false);
