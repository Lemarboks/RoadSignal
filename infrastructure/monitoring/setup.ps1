param(
  [ValidateSet('monitoring', 'models', 'routing', 'retrieval', 'training')]
  [string]$Mode = 'monitoring',
  [switch]$ImportWorkflows
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Push-Location $projectRoot
$composeArgs = @('-f', 'docker-compose.yml', '-f', 'compose.ai.yml', '-f', 'compose.monitoring.yml', '--profile', 'monitoring', '--profile', 'sensors')
function Compose {
  & docker compose @composeArgs @args
  if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed (exit $LASTEXITCODE)" }
}
function Wait-Web([string]$Url) {
  $deadline = (Get-Date).AddMinutes(10)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
      if ($response.StatusCode -eq 200) { return }
    } catch { }
    Start-Sleep -Seconds 3
  }
  throw "Service did not become ready: $Url. Check docker compose logs; no data was removed."
}
try {
  if ($Mode -eq 'monitoring') {
    # The 8 GB Docker budget cannot support all Qwen workers plus ThingsBoard.
    Compose stop embeddings reranker whisper verification vision
    Compose --profile monitoring --profile sensors pull --quiet n8n traccar thingsboard thingsboard-db
    Compose --profile monitoring run --rm monitoring-init
    Compose --profile monitoring --profile sensors up -d --wait --wait-timeout 180 traccar thingsboard-db n8n
    $schema = Compose exec -T thingsboard-db psql -U postgres -d thingsboard -Atc "SELECT to_regclass('public.tb_user');"
    if (-not ($schema -join '').Trim()) {
      Compose --profile monitoring --profile sensors run --rm -e INSTALL_TB=true -e LOAD_DEMO=true thingsboard
    }
    Compose --profile monitoring --profile sensors up -d thingsboard
    Compose --profile routing up -d valhalla
    Wait-Web 'http://localhost:5678/healthz'
    Wait-Web 'http://localhost:8082/api/server'
    Wait-Web 'http://localhost:8080/'
    foreach ($service in @('traccar', 'thingsboard', 'n8n')) {
      Compose --profile monitoring run --rm monitoring-init python /integration/bootstrap.py $service
    }
    $importState = Compose --profile monitoring run --rm monitoring-init python /integration/bootstrap.py imports-state
    if ($ImportWorkflows -or ($importState -join '').Trim() -eq 'pending') {
      Compose stop n8n
      Compose --profile monitoring run --rm --entrypoint sh n8n /import-workflows.sh
      Compose --profile monitoring up -d n8n
      Compose --profile monitoring run --rm monitoring-init python /integration/bootstrap.py mark-imported
    }
    Compose up -d --build --wait --wait-timeout 180 api web
    Compose exec -T --user root -e PYTHONPATH=/app api python /integration/provision_operator.py
    Compose --profile monitoring up -d monitoring-bridge
    Write-Host 'Monitoring installed. App :3000, n8n :5678, GPS :8082, sensors :8080. All device inputs are demo.'
  } elseif ($Mode -eq 'models') {
    Compose stop embeddings reranker whisper
    # The model Dockerfile reuses this CPU runtime; a fresh clone has no local tag.
    # Building it does not start retrieval or download the Qwen checkpoints.
    Compose --profile retrieval build embeddings
    Compose --profile verification --profile vision up -d --build verification vision
    Write-Host 'CPU model workers started. Wait for healthy, then run /service/smoke.py in each container.'
  } elseif ($Mode -eq 'routing') {
    # Build this regional graph in isolation; restart sensors/models afterward.
    Compose stop embeddings reranker whisper verification vision thingsboard
    Compose --profile routing up -d valhalla
    Write-Host 'Western Cape graph building. The monitoring overlay selects Valhalla, with open-routing fallback while it warms up.'
  } elseif ($Mode -eq 'retrieval') {
    Compose stop thingsboard verification vision
    Compose --profile retrieval --profile rerank --profile voice up -d embeddings reranker whisper
    Write-Host 'Retrieval/voice mode. Sensor and new model services paused; persisted data remains available.'
  } elseif ($Mode -eq 'training') {
    Compose --profile training build risk-training
    # Adopt only the output mount root from the older root-run CLI image.
    # No datasets or existing candidate files are changed.
    Compose --profile training run --rm --user root risk-training chown 10001:10001 /candidates
    Compose --profile training run --rm risk-training
    Write-Host 'Training toolchain installed. A reviewed real dataset is still required; no model was trained.'
  }
} finally { Pop-Location }
