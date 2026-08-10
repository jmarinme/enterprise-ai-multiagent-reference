<#
.SYNOPSIS
    Builds the deployable package for the Claims Tool Layer / Durable Functions Azure Function
    App (PBI-06-01).

.DESCRIPTION
    Vendors the repo-root src/ domain library into this Function App directory as ./src, and
    (optionally) produces a deployment zip - mirroring apps/api/Dockerfile's own repo-root src/
    COPY convention (CLAUDE.md section 6: one reusable src/ library, no duplicated Tool logic).
    Azure Functions Python apps only put their own directory on sys.path, so this vendoring step
    is required for `import src.services.tools.*` / `import src.tools.*` to resolve at runtime,
    exactly as apps/api/Dockerfile already does for the API container.

.PARAMETER Zip
    When set, also produces claims_tools.zip in this directory, ready for
    `az functionapp deployment source config-zip` or `az functionapp deploy`.

.EXAMPLE
    ./build.ps1 -Zip
#>

param(
    [switch]$Zip
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = $PSScriptRoot
$repoRoot = Resolve-Path (Join-Path $scriptRoot '..\..\..')
$sourceSrc = Join-Path $repoRoot 'src'
$vendoredSrc = Join-Path $scriptRoot 'src'

if (-not (Test-Path $sourceSrc)) {
    throw "Repo-root src/ not found at $sourceSrc - is this script still under ops/functions/claims_tools/?"
}

Write-Host "Vendoring $sourceSrc -> $vendoredSrc"
if (Test-Path $vendoredSrc) {
    Remove-Item -Recurse -Force -Confirm:$false $vendoredSrc
}
Copy-Item -Recurse -Force $sourceSrc $vendoredSrc

# Never vendor bytecode caches or the domain library's own tests/dev tooling.
Get-ChildItem -Path $vendoredSrc -Recurse -Directory -Filter '__pycache__' |
    Remove-Item -Recurse -Force -Confirm:$false

$fileCount = (Get-ChildItem -Recurse -File $vendoredSrc | Measure-Object).Count
Write-Host "Vendored $fileCount files."

if ($Zip) {
    $zipPath = Join-Path $scriptRoot 'claims_tools.zip'
    if (Test-Path $zipPath) {
        Remove-Item -Force -Confirm:$false $zipPath
    }

    $exclude = @('build.ps1', 'local.settings.json', '.funcignore', 'claims_tools.zip')
    $itemsToZip = Get-ChildItem -Path $scriptRoot -Force | Where-Object { $exclude -notcontains $_.Name }
    Write-Host "Creating $zipPath"
    Compress-Archive -Path ($itemsToZip.FullName) -DestinationPath $zipPath -Force
    Write-Host "Done: $zipPath"
}
