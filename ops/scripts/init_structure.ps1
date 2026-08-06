# Project: TMX Enterprise AI Reference Platform
# Component: Repository Initialization
# Description: Creates and validates the mandatory repository structure.
# Owner Role: Development Platform Team
# Created: 2026-08

[CmdletBinding()]
param(
    [string]$RootPath = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$CreateReadmeForReservedFolders
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$requiredDirectories = @(
    ".vscode",
    "apps/api/src",
    "apps/web/src",
    "artifacts",
    "configs/prompts/supervisor",
    "configs/prompts/claims",
    "configs/prompts/broker_services",
    "configs/prompts/commercial_intake",
    "configs/security",
    "data/external",
    "data/interim",
    "data/processed",
    "data/raw",
    "docs/Architecture/adr",
    "docs/Architecture/diagrams",
    "docs/Architecture/openapi",
    "docs/sprint_00/evidence",
    "models",
    "notebooks",
    "ops/bicep/modules",
    "ops/bicep/parameters",
    "ops/docker",
    "ops/k8s",
    "ops/scripts",
    "reports",
    "src/agents",
    "src/common",
    "src/config",
    "src/core",
    "src/dl",
    "src/domain",
    "src/ml",
    "src/observability",
    "src/pipelines",
    "src/rag",
    "src/services",
    "tests/e2e",
    "tests/integration",
    "tests/unit",
    "tests/conversational",
    "azure-pipelines/templates"
)

$reservedDirectories = @(
    "models",
    "notebooks",
    "src/dl",
    "src/ml",
    "ops/k8s"
)

$created = [System.Collections.Generic.List[string]]::new()
$existing = [System.Collections.Generic.List[string]]::new()
$failed = [System.Collections.Generic.List[string]]::new()
$placeholdersCreated = [System.Collections.Generic.List[string]]::new()

Write-Host "Initializing repository structure at: $RootPath" -ForegroundColor Cyan

foreach ($relativePath in $requiredDirectories) {
    try {
        $fullPath = Join-Path $RootPath $relativePath

        if (Test-Path -LiteralPath $fullPath) {
            $existing.Add($relativePath)
        }
        else {
            New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
            $created.Add($relativePath)
        }

        $items = @(Get-ChildItem -LiteralPath $fullPath -Force -ErrorAction Stop)
        if ($items.Count -eq 0) {
            $gitkeepPath = Join-Path $fullPath ".gitkeep"
            if (-not (Test-Path -LiteralPath $gitkeepPath)) {
                New-Item -ItemType File -Path $gitkeepPath -Force | Out-Null
                $placeholdersCreated.Add((Join-Path $relativePath ".gitkeep"))
            }
        }
    }
    catch {
        $failed.Add("$relativePath — $($_.Exception.Message)")
    }
}

if ($CreateReadmeForReservedFolders) {
    foreach ($relativePath in $reservedDirectories) {
        $fullPath = Join-Path $RootPath $relativePath
        $readmePath = Join-Path $fullPath "README.md"

        if (-not (Test-Path -LiteralPath $readmePath)) {
            $purpose = switch ($relativePath) {
                "models" { "Reserved for approved model artifacts or version metadata. Do not store provider model binaries here." }
                "notebooks" { "Reserved for exploration. Production logic must be moved to tested source modules before delivery." }
                "src/dl" { "Reserved for future deep-learning code. Not used by the MVP." }
                "src/ml" { "Reserved for future classical machine-learning code. Not used by the MVP." }
                "ops/k8s" { "Reserved by the academic repository template. The MVP uses Azure Container Apps, not AKS." }
                default { "Reserved for future use." }
            }

            @"
# Reserved folder

$purpose
"@ | Set-Content -LiteralPath $readmePath -Encoding UTF8
        }
    }
}

Write-Host ""
Write-Host "Repository initialization summary" -ForegroundColor Green
Write-Host ("Created directories:      {0}" -f $created.Count)
Write-Host ("Existing directories:     {0}" -f $existing.Count)
Write-Host ("Placeholders created:     {0}" -f $placeholdersCreated.Count)
Write-Host ("Failures:                 {0}" -f $failed.Count)

if ($created.Count -gt 0) {
    Write-Host "`nCreated:" -ForegroundColor Green
    $created | ForEach-Object { Write-Host "  + $_" }
}

if ($failed.Count -gt 0) {
    Write-Host "`nFailures:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  ! $_" }
    exit 1
}

Write-Host "`nPASS — mandatory repository structure exists." -ForegroundColor Green
exit 0
