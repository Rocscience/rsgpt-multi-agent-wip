#Requires -Version 5.1
<#
.SYNOPSIS
  Clone or link Rocscience multi-agent integration repos.

.DESCRIPTION
  By default clones into repos/ under this WIP repo.
  Use -UseLocal to symlink/junction from an existing parent folder (e.g. c:\Users\...\rsgpt).

.EXAMPLE
  .\scripts\clone-all.ps1
  .\scripts\clone-all.ps1 -UseLocal "c:\Users\KexuanZhang\rsgpt"
#>
param(
    [string]$UseLocal = "",
    [switch]$SkipDesktop
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ReposDir = Join-Path $Root "repos"

$RepoList = @(
    @{ Name = "rsgpt-ai-core"; Branch = "feat/multi-agent-production-integration"; Url = "https://github.com/Rocscience/rsgpt-ai-core.git" },
    @{ Name = "rsgpt-be";      Branch = "feat/multi-agent-production-integration"; Url = "https://github.com/Rocscience/rsgpt-be.git" },
    @{ Name = "rsgpt-fe";      Branch = "feat/multi-agent-production-integration"; Url = "https://github.com/Rocscience/rsgpt-fe.git" }
)
if (-not $SkipDesktop) {
    $RepoList += @{ Name = "rsgpt-desktop"; Branch = "main"; Url = "https://github.com/Rocscience/rsgpt-desktop.git" }
}

New-Item -ItemType Directory -Force -Path $ReposDir | Out-Null

foreach ($r in $RepoList) {
    $dest = Join-Path $ReposDir $r.Name
    if ($UseLocal) {
        $src = Join-Path $UseLocal $r.Name
        if (-not (Test-Path $src)) {
            Write-Warning "Local path missing: $src - skipping"
            continue
        }
        if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue }
        cmd /c mklink /J "$dest" "$src" | Out-Null
        Write-Host "Linked $dest -> $src"
        continue
    }

    if (Test-Path (Join-Path $dest ".git")) {
        Write-Host "Updating $($r.Name)..."
        Push-Location $dest
        git fetch origin
        git checkout $r.Branch 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Branch $($r.Branch) not on remote yet - staying on current branch"
        } else {
            git pull origin $r.Branch
        }
        Pop-Location
    } else {
        Write-Host "Cloning $($r.Name) @ $($r.Branch)..."
        git clone -b $r.Branch --single-branch $r.Url $dest 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Branch $($r.Branch) missing on remote - cloning default branch"
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
            git clone $r.Url $dest
            Write-Warning "Checkout feat/multi-agent-production-integration locally in $dest"
        }
    }
}

Write-Host ""
Write-Host "Done. Repos under: $ReposDir"
Write-Host "Next: see docs/RUNNING.md"
