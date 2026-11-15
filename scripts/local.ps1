param(
    [ValidateSet('start', 'stop', 'status', 'check', 'app')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root '.env'
$baseFile = Join-Path $root 'compose.yaml'
$storageFile = Join-Path $root 'compose.minio.yaml'
$environmentNames = @(
    'MINIO_LICENSE_FILE', 'MINIO_ROOT_USER_FILE', 'MINIO_ROOT_PASSWORD_FILE',
    'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY', 'MINIO_BUCKET'
)
$originalEnvironment = @{}
foreach ($name in $environmentNames) {
    $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

function Invoke-Compose {
    param([string[]]$Arguments, [switch]$AppOnly)
    $files = @('-p', 'zeroshot-local', '-f', $baseFile)
    if (-not $AppOnly) {
        $files += @('-f', $storageFile)
    }
    if (Test-Path -LiteralPath $envFile -PathType Leaf) {
        $files += @('--env-file', '.env')
    }
    & docker compose @files @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose failed. Follow the reported diagnostics; do not blindly retry uncertain writes.'
    }
}

function New-LocalConfiguration {
    Write-Host 'First-time setup: provide existing external MinIO license and root credential files.'
    Write-Host 'Keep these files outside the repository. Their contents will not be copied.'
    $license = Read-Host 'License file path'
    $rootUser = Read-Host 'Root user file path'
    $rootPassword = Read-Host 'Root password file path'
    Write-Host 'The required default bucket zeroshot_learning_output may be rejected by MinIO.'
    $bucket = Read-Host 'Bucket name (press Enter for the required default, or enter a valid override)'
    if (-not $bucket) {
        $bucket = 'zeroshot_learning_output'
    }

    foreach ($value in @($license, $rootUser, $rootPassword, $bucket)) {
        if ([string]::IsNullOrWhiteSpace($value) -or $value -match "['`r`n]") {
            throw 'Each value must be nonempty and cannot contain a single quote or newline. Run setup again.'
        }
    }
    foreach ($path in @($license, $rootUser, $rootPassword)) {
        if ($path -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+)') {
            throw 'Use absolute paths to existing external files. Run setup again.'
        }
    }

    $env:MINIO_LICENSE_FILE = $license
    $env:MINIO_ROOT_USER_FILE = $rootUser
    $env:MINIO_ROOT_PASSWORD_FILE = $rootPassword
    $env:MINIO_BUCKET = $bucket
    & uv run --locked python scripts\check_deployment.py preflight
    if ($LASTEXITCODE -ne 0) {
        throw 'File validation failed. Correct the inputs and run setup again.'
    }

    $lines = @(
        '# Local deployment paths and bucket only; do not put credentials here.'
        "MINIO_LICENSE_FILE='$license'"
        "MINIO_ROOT_USER_FILE='$rootUser'"
        "MINIO_ROOT_PASSWORD_FILE='$rootPassword'"
        "MINIO_BUCKET='$bucket'"
    )
    $stream = [System.IO.File]::Open($envFile, 'CreateNew', 'Write', 'None')
    try {
        $writer = [System.IO.StreamWriter]::new($stream, [System.Text.UTF8Encoding]::new($false))
        try {
            foreach ($line in $lines) {
                $writer.WriteLine($line)
            }
        }
        finally {
            $writer.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
    Write-Host 'Local configuration saved in ignored .env; no credential values were saved.'
}

Push-Location $root
try {
    if ($Action -eq 'app') {
        Invoke-Compose -AppOnly -Arguments @('up', '-d', '--build', 'app')
        Write-Host 'App started. Open http://localhost:8501; storage is not configured by this command.'
    }
    else {
        if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
            if ($Action -ne 'start') {
                throw 'No .env configuration found. Start the full deployment first or use the manual instructions.'
            }
            New-LocalConfiguration
        }
        if ($Action -eq 'start') {
            & uv run --env-file .env --locked python scripts\check_deployment.py preflight
            if ($LASTEXITCODE -ne 0) {
                throw 'File validation failed. Correct .env or the overriding process environment.'
            }
            $credential = Get-Credential -Message 'Enter authorized MinIO application credentials'
            if ($null -eq $credential -or [string]::IsNullOrWhiteSpace($credential.UserName)) {
                throw 'Application credentials are required to start the full deployment.'
            }
            $env:MINIO_ACCESS_KEY = $credential.UserName
            $env:MINIO_SECRET_KEY = $credential.GetNetworkCredential().Password
            if ([string]::IsNullOrWhiteSpace($env:MINIO_SECRET_KEY)) {
                throw 'The application secret key must not be empty.'
            }
            Invoke-Compose -Arguments @('config', '--quiet')
            Invoke-Compose -Arguments @('up', '-d', '--build')
            Write-Host 'Containers started. Open http://localhost:8501; storage readiness is not yet verified.'
            Write-Host 'Use .\scripts\local.ps1 status and .\scripts\local.ps1 check to verify readiness.'
        }
        elseif ($Action -eq 'stop') {
            Invoke-Compose -Arguments @('stop')
            Write-Host 'Services stopped; named volumes were retained. Resolve uncertain writes before retrying.'
        }
        elseif ($Action -eq 'check') {
            Write-Host 'Checking storage with one temporary owned object; uncertain writes require inspection.'
            Invoke-Compose -Arguments @(
                'exec', '-T', 'app', 'python', 'scripts/check_deployment.py', 'storage', '--write-probe'
            )
        }
        else {
            Invoke-Compose -Arguments @('ps')
            Write-Host 'Container status does not establish that storage writes are permitted.'
        }
    }
}
finally {
    Pop-Location
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
}
