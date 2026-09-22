import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'
import { enableGPUAcceleration } from './lib/tauriBridge'

// Tauri native GPU hızlandırma - tarayıcı sınırlarından kurtul
enableGPUAcceleration()

const app = mount(App, {
  target: document.getElementById('app')!,
})

export default app
