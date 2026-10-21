# Convert the WaitLess user guide to a Microsoft Word document.
#
# Requires pandoc: https://pandoc.org/installing.html
#
#   winget install --id JohnMacFarlane.Pandoc
#
# Usage (run from the repository root):
#
#   .\docs\convert_to_docx.ps1
#
# The output is docs/17-user-guide.docx. The generated .docx is a build
# artefact and is not tracked in git.

param(
    [string]$Source = "docs/17-user-guide.md",
    [string]$Output = "docs/17-user-guide.docx"
)

$ErrorActionPreference = "Stop"

function Resolve-Pandoc {
    # 1. Already on PATH?
    $onPath = Get-Command pandoc -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    # 2. The usual install locations, which are not always on PATH.
    $candidates = @(
        "$env:LOCALAPPDATA\Pandoc\pandoc.exe",
        "$env:ProgramFiles\Pandoc\pandoc.exe",
        "${env:ProgramFiles(x86)}\Pandoc\pandoc.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    return $null
}

$pandoc = Resolve-Pandoc
if (-not $pandoc) {
    Write-Host "pandoc was not found."
    Write-Host ""
    Write-Host "Install it with:"
    Write-Host "    winget install --id JohnMacFarlane.Pandoc"
    Write-Host ""
    Write-Host "Then run this script again."
    exit 1
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $repoRoot $Source
$outputPath = Join-Path $repoRoot $Output

if (-not (Test-Path $sourcePath)) {
    Write-Host "Source not found: $sourcePath"
    exit 1
}

Write-Host "Using pandoc: $pandoc"
Write-Host "Converting $Source -> $Output"

& $pandoc $sourcePath `
    --from=gfm `
    --to=docx `
    --standalone `
    --toc `
    --toc-depth=2 `
    --output=$outputPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "pandoc failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Done: $outputPath"
