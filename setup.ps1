param(
    [string]$ModelRepoId = "",
    [switch]$ForceDownload
)

$ErrorActionPreference = "Stop"

function Get-EnvValue {
    param(
        [string]$FilePath,
        [string]$Key
    )

    if (-not (Test-Path $FilePath)) {
        return ""
    }

    $line = Get-Content $FilePath | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1
    if (-not $line) {
        return ""
    }

    return ($line -split "=", 2)[1].Trim()
}

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

Write-Host "Installing Python dependencies..."
python -m pip install -r requirements.txt

if ([string]::IsNullOrWhiteSpace($ModelRepoId)) {
    $ModelRepoId = $env:MODEL_REPO_ID
}

if ([string]::IsNullOrWhiteSpace($ModelRepoId)) {
    $ModelRepoId = Get-EnvValue -FilePath ".env" -Key "MODEL_REPO_ID"
}

if ([string]::IsNullOrWhiteSpace($ModelRepoId)) {
    $ModelRepoId = Get-EnvValue -FilePath ".env.example" -Key "MODEL_REPO_ID"
}

$hfToken = $env:HF_TOKEN
if ([string]::IsNullOrWhiteSpace($hfToken)) {
    $hfToken = Get-EnvValue -FilePath ".env" -Key "HF_TOKEN"
}

if ([string]::IsNullOrWhiteSpace($hfToken)) {
    $hfToken = Get-EnvValue -FilePath ".env.example" -Key "HF_TOKEN"
}

if ([string]::IsNullOrWhiteSpace($ModelRepoId)) {
    Write-Host "MODEL_REPO_ID is empty. Skipping model download."
    Write-Host "Set MODEL_REPO_ID in .env or pass -ModelRepoId <user/repo>."
    exit 0
}

Write-Host "Downloading ONNX models from $ModelRepoId ..."
$downloadArgs = @("download_models.py", "--repo-id", $ModelRepoId)

if (-not [string]::IsNullOrWhiteSpace($hfToken)) {
    $downloadArgs += @("--token", $hfToken)
}

if ($ForceDownload) {
    $downloadArgs += "--force"
}

python @downloadArgs

Write-Host "Setup completed."
