# scripts/test_disaster_recovery.ps1
# Disaster Recovery testi (Windows PowerShell / Docker Desktop)
# Docker Compose v2 plugin gerektirir: `docker compose` (tire yok)

Write-Host ">>> Disaster Recovery Test — Volume Persistence <<<"

Write-Host "1. Container build ve başlatma..."
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Write-Error "Build başarısız"; exit 1 }

Write-Host "2. Healthcheck bekleniyor (max 60s)..."
$ready = $false
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 5
    $status = docker compose ps --format json | ConvertFrom-Json | Select-Object -First 1
    if ($status.Health -eq "healthy" -or $status.State -eq "running") {
        $ready = $true; break
    }
}
if (-not $ready) { Write-Warning "Healthcheck zaman aşımı — devam ediliyor." }

Write-Host "3. Kalıcı volume'a test verisi yazılıyor..."
docker compose exec pineal sh -c "echo '{\"status\": \"persisted_test_data\"}' > /app/memory/dr_test.json"
if ($LASTEXITCODE -ne 0) { Write-Error "Veri yazılamadı"; exit 1 }

Write-Host "4. Felaket simülasyonu: container hard-kill + kaldır (-v YOK = volume korunur)..."
docker compose down
Write-Host "5. Sıfırdan yeniden başlatma..."
docker compose up -d pineal
Start-Sleep -Seconds 10

Write-Host "6. Volume persistance doğrulama..."
$check = docker compose exec pineal cat /app/memory/dr_test.json 2>&1
Write-Host "Volume içeriği: $check"

if ($check -match "persisted_test_data") {
    Write-Host "DISASTER RECOVERY PASSED: Veri container yeniden başlatma sonrası korundu! ✅"
} else {
    Write-Error "DISASTER RECOVERY FAILED: Veri silindi! Volume mount eksik olabilir. ❌"
    docker compose down
    exit 1
}

Write-Host "7. Temizleme..."
docker compose down
Write-Host "Test tamamlandı."
