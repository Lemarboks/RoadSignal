$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Set-Location $root

Write-Output "# SafeRoute evidence snapshot"
Write-Output ""
Write-Output "## Git"
git status -sb
git log --oneline -10
Write-Output ""
Write-Output "## Tests present"
Get-ChildItem apps\web -Recurse -Filter "*.test.ts" | ForEach-Object FullName
Get-ChildItem apps\api\tests -Filter "test_*.py" | ForEach-Object FullName
Write-Output ""
Write-Output "## Screenshots and presentation assets"
Get-ChildItem docs\screenshots,docs\presentation -File -ErrorAction SilentlyContinue |
  Select-Object FullName,Length,LastWriteTime
Write-Output ""
Write-Output "Learner must still verify personal details, contacts, manual acceptance results, and reflection."
