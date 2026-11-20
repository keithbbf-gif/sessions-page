# Installs the cmCode AI harness as a separate program.
# cmSessions stays sessions_page.exe. A missing network, Git, or Python
# prints a manual install line and exits 0 so setup is not rolled back.
$ErrorActionPreference = 'Continue'

$Manual = 'pip install git+https://github.com/keithbbf-gif/cmCode.git'
$Log = Join-Path $PSScriptRoot 'install_cmcode_dep.log'
$Repo = 'https://github.com/keithbbf-gif/cmCode.git'
$Dest = Join-Path $env:LOCALAPPDATA 'Programs\cmCode'
$CosmosCopy = Join-Path $env:LOCALAPPDATA 'Programs\COSMOS\cmCode'
$DevTree = 'V:\a\ai\cmCode'

function Say([string]$Text) {
    $line = "cmCode dependency: $Text"
    Write-Host $line
    Add-Content -LiteralPath $Log -Value $line -Encoding ASCII -ErrorAction SilentlyContinue
}

function Note-Manual([string]$Why) {
    Say $Why
    Say 'cmSessions is installed and was not changed.'
    Say "Install the AI harness later with: $Manual"
}

function Test-Tree([string]$Root) {
    if (-not $Root) { return $false }
    if (Test-Path -LiteralPath (Join-Path $Root 'cmcode.cmd')) { return $true }
    if (Test-Path -LiteralPath (Join-Path $Root 'pyproject.toml')) { return $true }
    if (Test-Path -LiteralPath (Join-Path $Root 'cosmos_code\__main__.py')) { return $true }
    return $false
}

function Find-Existing {
    foreach ($name in @('cmcode', 'cosmos-code', 'cmcode.cmd', 'cosmos-code.cmd')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return "PATH $($cmd.Source)" }
    }
    if (Test-Tree $Dest) { return $Dest }
    if (Test-Tree $CosmosCopy) { return $CosmosCopy }
    return $null
}

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Exe = 'py'; Prefix = @('-3') }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Exe = 'python'; Prefix = @() }
    }
    return $null
}

function Add-UserPath([string]$Dir) {
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not $current) { $current = '' }
    $needle = $Dir.TrimEnd('\')
    $parts = @($current -split ';' | Where-Object { $_ -ne '' })
    foreach ($part in $parts) {
        if ($part.TrimEnd('\').Equals($needle, [System.StringComparison]::OrdinalIgnoreCase)) {
            Say "per-user PATH already includes $Dir"
            return
        }
    }
    if ($current -and -not $current.TrimEnd().EndsWith(';')) {
        $current = $current + ';'
    }
    [Environment]::SetEnvironmentVariable('Path', ($current + $Dir), 'User')
    Say "added $Dir to the per-user PATH (new terminals see cmcode.cmd)"
}

function Write-Shim([string]$Root) {
    $path = Join-Path $Root 'cmcode.cmd'
    $lines = @(
        '@echo off',
        'setlocal',
        'set "ROOT=%~dp0"',
        'set "PYTHONPATH=%ROOT%;%ROOT%cosmos_harness;%ROOT%harness\G47;%PYTHONPATH%"',
        'where py >nul 2>&1',
        'if %ERRORLEVEL%==0 (',
        '  py -3 -m cosmos_code %*',
        '  exit /b %ERRORLEVEL%',
        ')',
        'where python >nul 2>&1',
        'if %ERRORLEVEL%==0 (',
        '  python -m cosmos_code %*',
        '  exit /b %ERRORLEVEL%',
        ')',
        'echo cmCode needs Python 3.11 or newer on PATH. 1>&2',
        "echo Install with: $Manual 1>&2",
        'exit /b 1'
    )
    Set-Content -LiteralPath $path -Value $lines -Encoding ASCII
    Say "wrote $path"
}

function Copy-Tree([string]$Source, [string]$Target) {
    Say "copying $Source"
    Say "into $Target"
    if (-not (Test-Path -LiteralPath $Target)) {
        New-Item -ItemType Directory -Path $Target -Force | Out-Null
    }
    $null = & robocopy $Source $Target /E /NFL /NDL /NJH /NJS /nc /ns /np /XD __pycache__ .git .venv node_modules .mypy_cache .ruff_cache /XF *.pyc
    $code = $LASTEXITCODE
    if ($code -ge 8) {
        Say "copy stopped with robocopy code $code"
        return $false
    }
    return (Test-Path -LiteralPath (Join-Path $Target 'pyproject.toml'))
}

function Resolve-Source {
    if (Test-Path -LiteralPath (Join-Path $DevTree 'pyproject.toml')) {
        Say "using the local tree $DevTree"
        return $DevTree
    }
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        Note-Manual 'Git is not on PATH and V:\a\ai\cmCode is not on this PC.'
        return $null
    }
    $clone = Join-Path $env:TEMP ('cmCode-clone-' + [Guid]::NewGuid().ToString('n'))
    Say "cloning $Repo"
    $null = & git clone --depth 1 $Repo $clone
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $clone 'pyproject.toml'))) {
        Note-Manual 'git clone did not finish (offline, or the repository could not be read).'
        if (Test-Path -LiteralPath $clone) {
            Remove-Item -LiteralPath $clone -Recurse -Force -ErrorAction SilentlyContinue
        }
        return $null
    }
    return $clone
}

try {
    $found = Find-Existing
    if ($found) {
        Say "already present ($found). Nothing to install."
        exit 0
    }

    Say 'cmCode was not found on PATH or under %LOCALAPPDATA%\Programs.'
    $source = Resolve-Source
    if (-not $source) { exit 0 }

    if (-not (Copy-Tree $source $Dest)) {
        Note-Manual 'The cmCode tree was not copied into %LOCALAPPDATA%\Programs\cmCode.'
        exit 0
    }
    Write-Shim $Dest
    Add-UserPath $Dest

    $python = Find-Python
    if (-not $python) {
        Say 'Python was not found, so pip install --user was skipped.'
        Say "The tree and cmcode.cmd are in $Dest."
        Say "When Python is installed: $Manual"
        exit 0
    }

    Say "running $($python.Exe) -m pip install --user"
    & $python.Exe @($python.Prefix + @('-m', 'pip', 'install', '--user', $Dest))
    if ($LASTEXITCODE -ne 0) {
        Say 'pip install --user did not finish. The copied tree and cmcode.cmd are still in place.'
        Say "You can retry with: $Manual"
    } else {
        Say 'pip install --user finished.'
    }
    Say "cmCode is separate from sessions_page.exe. Launcher: $Dest\cmcode.cmd"
    exit 0
} catch {
    Note-Manual ("installer step stopped: " + $_.Exception.Message)
    exit 0
}
