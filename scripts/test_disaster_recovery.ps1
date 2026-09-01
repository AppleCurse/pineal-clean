Write-Host ">>> Disaster Recovery Test (Backup & Restore Simulation) <<<"
Write-Host "1. Building and starting the container..."
docker-compose up -d --build

Write-Host "2. Waiting for container to be ready (5 seconds)..."
Start-Sleep -Seconds 5

Write-Host "3. Injecting a critical memory file into the persistent volume..."
docker-compose exec pineal sh -c "mkdir -p /app/memory && echo '{\"status\": \"persisted_test_data\"}' > /app/memory/dr_test.json"

Write-Host "4. Simulating a disaster (Hard kill and remove container)..."
docker-compose down
Write-Host "5. Re-creating the container (Simulating a fresh deployment after crash)..."
docker-compose up -d pineal
Start-Sleep -Seconds 5

Write-Host "6. Verifying if memory survived the disaster..."
$check = docker-compose exec pineal cat /app/memory/dr_test.json
Write-Host "Memory content found: $check"

if ($check -match "persisted_test_data") {
    Write-Host "DISASTER RECOVERY PASSED: Memory survived container death! \u2705"
} else {
    Write-Host "DISASTER RECOVERY FAILED: Memory was wiped! \u274c"
    exit 1
}

Write-Host "7. Cleaning up..."
docker-compose down
