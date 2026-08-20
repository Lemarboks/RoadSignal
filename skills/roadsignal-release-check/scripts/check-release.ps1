$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Set-Location $root

& .\apps\web\node_modules\.bin\tsc.CMD --noEmit -p apps\web\tsconfig.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& .\apps\web\node_modules\.bin\vitest.CMD run --root apps\web
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:GITHUB_ACTIONS = "true"
$env:GITHUB_REPOSITORY = "Lemarboks/RoadSignal"
& .\apps\web\node_modules\.bin\next.CMD build apps\web
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$html = Get-Content apps\web\out\index.html -Raw
if (-not $html.Contains("/RoadSignal/_next/")) {
  throw "Static export does not contain the GitHub Pages base path."
}

Write-Output "RoadSignal release gate passed."
