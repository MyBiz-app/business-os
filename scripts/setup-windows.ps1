# Business OS - developer machine setup for Windows.
# Safe to run more than once: installs only what is missing.
#
# Usage (PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\setup-windows.ps1
#   powershell -ExecutionPolicy Bypass -File .\setup-windows.ps1 -DevRoot "D:\dev"

param(
    [string]$DevRoot = "C:\dev",
    [string]$RepoUrl = "https://github.com/adiredri/business-os.git",
    [string]$Branch = "claude/kind-maxwell-e86wk9",
    [string]$PythonVersion = "3.13"
)

$ErrorActionPreference = "Stop"

function Write-Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }
function Write-Ok($message) { Write-Host "    OK  $message" -ForegroundColor Green }
function Write-Warn($message) { Write-Host "    !!  $message" -ForegroundColor Yellow }

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Test-Command($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

# --- 1. Prerequisites the owner installed manually -------------------------------------------
Write-Step "Checking prerequisites"
$missing = @()
foreach ($tool in @("git", "node", "npm", "docker", "code")) {
    if (Test-Command $tool) { Write-Ok "$tool found" } else { $missing += $tool; Write-Warn "$tool NOT found" }
}
if ($missing.Count -gt 0) {
    Write-Warn "Install the missing tools, open a NEW PowerShell window and run this script again."
    exit 1
}
Write-Ok ("node " + (node --version))

# --- 2. pnpm ----------------------------------------------------------------------------------
Write-Step "pnpm (JavaScript package manager)"
if (Test-Command "pnpm") {
    Write-Ok ("pnpm " + (pnpm --version) + " already installed")
} else {
    npm install -g pnpm
    Update-SessionPath
    Write-Ok ("pnpm " + (pnpm --version) + " installed")
}

# --- 3. uv (Python package and version manager) ------------------------------------------------
Write-Step "uv (Python manager)"
if (Test-Command "uv") {
    Write-Ok ((uv --version) + " already installed")
} else {
    if (Test-Command "winget") {
        winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
    } else {
        powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    }
    Update-SessionPath
    if (-not (Test-Command "uv")) { $env:Path += ";$env:USERPROFILE\.local\bin" }
    Write-Ok ((uv --version) + " installed")
}

# --- 4. Python (managed by uv, does not touch any other Python on the machine) -----------------
Write-Step "Python $PythonVersion via uv"
uv python install $PythonVersion
Write-Ok "Python $PythonVersion ready"

# --- 5. Docker must be running for the local database ------------------------------------------
Write-Step "Docker"
$dockerRunning = $false
try { docker info *> $null; $dockerRunning = ($LASTEXITCODE -eq 0) } catch { $dockerRunning = $false }
if ($dockerRunning) { Write-Ok "Docker is running" } else { Write-Warn "Docker Desktop is installed but not running. Start it before running the app." }

# --- 6. Clone the repository -------------------------------------------------------------------
Write-Step "Repository in $DevRoot"
New-Item -ItemType Directory -Force -Path $DevRoot | Out-Null
$repoPath = Join-Path $DevRoot "business-os"
if (Test-Path (Join-Path $repoPath ".git")) {
    Write-Ok "Already cloned at $repoPath - pulling latest"
    git -C $repoPath fetch origin
    git -C $repoPath checkout $Branch
    git -C $repoPath pull origin $Branch
} else {
    git clone --branch $Branch $RepoUrl $repoPath
    Write-Ok "Cloned to $repoPath"
}

# --- Summary -----------------------------------------------------------------------------------
Write-Step "Done"
Write-Host "    git    $(git --version)"
Write-Host "    node   $(node --version)"
Write-Host "    pnpm   $(pnpm --version)"
Write-Host "    uv     $(uv --version)"
Write-Host "    python $(uv python find $PythonVersion)"
Write-Host "    repo   $repoPath"
Write-Host "`nOpen the project with:  code `"$repoPath`"" -ForegroundColor Cyan
