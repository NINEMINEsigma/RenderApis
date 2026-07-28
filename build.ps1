<#
.SYNOPSIS
    构建 RenderDoc Python 绑定 (renderdoc.pyd)。

.DESCRIPTION
    Windows 上 RenderDoc 不用 CMake，直接用 MSBuild 构建 renderdoc.sln。
    所有工具路径通过参数指定，不猜测任何环境。
    构建完成后只报告产物路径，不做任何安装操作。

    仓库自带 SWIG (qrenderdoc/3rdparty/swig/) 和 Python 3.6 嵌入版
    (qrenderdoc/3rdparty/python/)，这些不需要额外指定。

    如果要用自己的 Python 版本而非仓库自带的 3.6，通过 -PythonPrefix 传入。
    对于 venv 环境，脚本会自动补齐 python.props 所需的 python3X.zip 和 libs\python3X.lib。

.PARAMETER VsPath
    Visual Studio 安装路径。例如 D:\VS2022
    需要包含 MSBuild.exe（在 MSBuild\Current\Bin\ 下）

.PARAMETER PythonPrefix
    可选。自定义 Python 安装路径（覆盖仓库自带的 3.6）。
    如果不传，使用仓库自带的 qrenderdoc\3rdparty\python

.PARAMETER Configuration
    构建配置。Release 或 Debug。默认 Release。

.PARAMETER Platform
    目标平台。x64 或 Win32。默认 x64。

.EXAMPLE
    .\build.ps1 -VsPath "D:\VS2022"
    .\build.ps1 -VsPath "D:\VS2022" -PythonPrefix "D:\RenderApis\venv" -Configuration Release
#>

param(
    [Parameter(Mandatory=$true, HelpMessage="Visual Studio 安装路径，如 D:\VS2022")]
    [string]$VsPath,

    [Parameter(Mandatory=$false)]
    [string]$PythonPrefix = "",

    [Parameter(Mandatory=$false)]
    [ValidateSet("Release", "Debug")]
    [string]$Configuration = "Release",

    [Parameter(Mandatory=$false)]
    [ValidateSet("x64", "Win32")]
    [string]$Platform = "x64"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# ------------------------------------------------------------------ #
# Helper: 确保 PythonPrefix 满足 python.props 的三个文件要求
# ------------------------------------------------------------------ #

function _PreparePythonPrefix {
    param([string]$Prefix, [string]$Plat)

    $pyExe = Join-Path $Prefix "Scripts\python.exe"
    if (-not (Test-Path $pyExe)) { $pyExe = Join-Path $Prefix "python.exe" }
    if (-not (Test-Path $pyExe)) {
        Write-Warning "  python.exe not found in $Prefix, skipping preparation"
        return
    }

    $verRaw = & $pyExe -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')"
    $pyZipName = "python$verRaw.zip"
    $pyZip = Join-Path $Prefix $pyZipName
    $pyLib = Join-Path $Prefix "libs\python$verRaw.lib"
    $pyInclude = Join-Path $Prefix "Include\Python.h"
    if (-not (Test-Path $pyInclude)) { $pyInclude = Join-Path $Prefix "include\Python.h" }

    $hasInclude = Test-Path $pyInclude
    $hasLib = Test-Path $pyLib
    $hasZip = $false
    $zipValid = $false
    if (Test-Path $pyZip) {
        $hasZip = $true
        $zipSize = (Get-Item $pyZip).Length
        if ($zipSize -gt 100000) { $zipValid = $true }
    }

    # --- Ensure python3X.zip exists and is valid ---
    # python.props needs the file to exist for compilation.
    # qrenderdoc.exe needs it to contain the real standard library at runtime.
    # Strategy: if no valid zip, create one from the Lib\ directory (standard library .py files).
    if (-not $zipValid) {
        # Remove invalid placeholder if exists
        if ($hasZip) {
            Remove-Item $pyZip -Force
            Write-Host "  Removed invalid $pyZipName" -ForegroundColor Yellow
        }

        # Try to find existing zip from: venv base, parent dirs, then create from Lib\
        $srcZip = $null

        # 1. If venv, check pyvenv.cfg for base Python
        $cfgPath = Join-Path $Prefix "pyvenv.cfg"
        if (Test-Path $cfgPath) {
            $baseDir = $null
            foreach ($line in Get-Content $cfgPath) {
                if ($line -match '^\s*home\s*=\s*(.+)$') { $baseDir = $matches[1].Trim(); break }
                if ($line -match '^\s*base_prefix\s*=\s*(.+)$') { $baseDir = $matches[1].Trim(); break }
            }
            if ($baseDir) {
                $candidate = Join-Path $baseDir $pyZipName
                if ((Test-Path $candidate) -and ((Get-Item $candidate).Length -gt 100000)) { $srcZip = $candidate }
            }
        }

        # 2. Check if Lib\ directory exists — create zip from it
        if (-not $srcZip) {
            $libDir = Join-Path $Prefix "Lib"
            if (Test-Path $libDir) {
                Write-Host "  Creating $pyZipName from $libDir ..." -ForegroundColor Yellow
                # Use Python's own zipfile to create the zip (works on any machine)
                & $pyExe -c @"
import zipfile, os, sys
lib_dir = os.path.join(sys.prefix, 'Lib')
zip_path = os.path.join(sys.prefix, '$pyZipName')
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(lib_dir):
        for f in files:
            if f.endswith('.py') or f.endswith('.pth') or f.endswith('.txt'):
                full = os.path.join(root, f)
                arc = os.path.relpath(full, lib_dir)
                zf.write(full, arc)
print(f'Created {zip_path} ({os.path.getsize(zip_path)} bytes)')
"@
                if (Test-Path $pyZip) {
                    $zipValid = $true
                    Write-Host "    Created: $pyZip ($((Get-Item $pyZip).Length) bytes)" -ForegroundColor Green
                }
            }
        }

        # 3. Copy from found source
        if (-not $zipValid -and $srcZip) {
            Copy-Item $srcZip $pyZip -Force
            $zipValid = $true
            Write-Host "  Copied $pyZipName from $srcZip" -ForegroundColor Green
        }

        if (-not $zipValid) {
            Write-Warning "  Could not create $pyZipName. GUI will not work."
            Write-Warning "  Place a real python$verRaw.zip (from python.org embeddable package) at: $pyZip"
        }
    }

    # --- Ensure libs\python3X.lib exists ---
    if (-not $hasLib) {
        # For venv: find from base Python
        $srcLib = $null
        $cfgPath = Join-Path $Prefix "pyvenv.cfg"
        if (Test-Path $cfgPath) {
            $baseDir = $null
            foreach ($line in Get-Content $cfgPath) {
                if ($line -match '^\s*home\s*=\s*(.+)$') { $baseDir = $matches[1].Trim(); break }
            }
            if ($baseDir) {
                $candidate = Join-Path $baseDir "libs\python$verRaw.lib"
                if (Test-Path $candidate) { $srcLib = $candidate }
            }
        }
        if ($srcLib) {
            $destDir = Join-Path $Prefix "libs"
            if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
            Copy-Item $srcLib (Join-Path $destDir "python$verRaw.lib") -Force
            Write-Host "  Copied python$verRaw.lib from $srcLib" -ForegroundColor Green
        } else {
            Write-Warning "  libs\python$verRaw.lib not found. Build may fail."
        }
    }

    if (-not $hasInclude) {
        Write-Warning "  Include\Python.h not found in $Prefix. Build may fail."
    }
}

# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

# 1. 定位 MSBuild
$MsBuildCandidates = @(
    Join-Path $VsPath "MSBuild\Current\Bin\MSBuild.exe"
    Join-Path $VsPath "MSBuild\15.0\Bin\MSBuild.exe"
)
$MsBuild = $null
foreach ($p in $MsBuildCandidates) {
    if (Test-Path $p) { $MsBuild = $p; break }
}
if (-not $MsBuild) {
    Write-Error "MSBuild.exe not found under '$VsPath'. Expected at MSBuild\Current\Bin\MSBuild.exe"
    exit 1
}
Write-Host "[1/4] MSBuild: $MsBuild" -ForegroundColor Cyan

# 2. 确定 Python 路径
$EnvVars = @{}
if ($PythonPrefix -and (Test-Path $PythonPrefix)) {
    Write-Host "[2/4] Using custom Python: $PythonPrefix" -ForegroundColor Cyan
    _PreparePythonPrefix -Prefix $PythonPrefix -Plat $Platform
    if ($Platform -eq "x64") {
        $EnvVars["RENDERDOC_PYTHON_PREFIX64"] = $PythonPrefix
    } else {
        $EnvVars["RENDERDOC_PYTHON_PREFIX32"] = $PythonPrefix
    }
} else {
    Write-Host "[2/4] Using bundled Python 3.6 from qrenderdoc\3rdparty\python" -ForegroundColor Cyan
}

# 3. 构建
$Solution = Join-Path $RepoRoot "renderdoc.sln"
Write-Host "[3/4] Build solution: $Solution" -ForegroundColor Cyan
Write-Host "      Configuration: $Configuration, Platform: $Platform"

$msbuildArgs = @(
    $Solution
    "/p:Configuration=$Configuration"
    "/p:Platform=$Platform"
    "/m"
    "/v:minimal"
)
foreach ($k in $EnvVars.Keys) {
    $msbuildArgs += "/p:$k=$($EnvVars[$k])"
}
& $MsBuild @msbuildArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed (exit code $LASTEXITCODE)"
    exit $LASTEXITCODE
}
Write-Host "  Solution build OK" -ForegroundColor Green

# 4. 定位构建产物
Write-Host ""
Write-Host "[4/4] Locating build artifacts..." -ForegroundColor Cyan

$BuildDir = Join-Path $RepoRoot "x64\$Configuration"
if (-not (Test-Path $BuildDir)) {
    $BuildDir = Join-Path $RepoRoot "build\$Configuration\$Platform"
}
if (-not (Test-Path $BuildDir)) {
    $BuildDir = Join-Path $RepoRoot "build\$Configuration"
}
if (-not (Test-Path $BuildDir)) {
    $BuildDir = Join-Path $RepoRoot "Win32\$Configuration"
}

$RenderdocDll = Join-Path $BuildDir "renderdoc.dll"
$PymodulesDir = Join-Path $BuildDir "pymodules"
$RenderdocPyd = Join-Path $PymodulesDir "renderdoc.pyd"
if (-not (Test-Path $RenderdocPyd)) { $RenderdocPyd = Join-Path $PymodulesDir "_renderdoc.pyd" }
if (-not (Test-Path $RenderdocPyd)) { $RenderdocPyd = Join-Path $BuildDir "renderdoc.pyd" }
if (-not (Test-Path $RenderdocPyd)) { $RenderdocPyd = Join-Path $BuildDir "_renderdoc.pyd" }

# --- Post-build file placement ---
# MSBuild outputs .pyd to pymodules\ but .exe/.dll to build root.
# Both GUI (qrenderdoc.exe) and Python (import renderdoc) need all files accessible.

# 1. Copy .pyd files from pymodules\ to build root (for qrenderdoc.exe)
$QRenderdocPyd = Join-Path $PymodulesDir "qrenderdoc.pyd"
if (Test-Path $QRenderdocPyd) {
    $Dest = Join-Path $BuildDir "qrenderdoc.pyd"
    if (-not (Test-Path $Dest)) {
        Copy-Item $QRenderdocPyd $BuildDir -Force
        Write-Host "  Copied qrenderdoc.pyd -> $BuildDir" -ForegroundColor Yellow
    }
}
if (Test-Path (Join-Path $PymodulesDir "renderdoc.pyd")) {
    $Dest = Join-Path $BuildDir "renderdoc.pyd"
    if (-not (Test-Path $Dest)) {
        Copy-Item (Join-Path $PymodulesDir "renderdoc.pyd") $BuildDir -Force
        Write-Host "  Copied renderdoc.pyd -> $BuildDir" -ForegroundColor Yellow
    }
}

# 2. Copy renderdoc.dll to pymodules\ (for Python import renderdoc)
$DllInPymodules = Join-Path $PymodulesDir "renderdoc.dll"
if ((Test-Path $RenderdocDll) -and (Test-Path $PymodulesDir) -and (-not (Test-Path $DllInPymodules))) {
    Copy-Item $RenderdocDll $PymodulesDir -Force
    Write-Host "  Copied renderdoc.dll -> $PymodulesDir" -ForegroundColor Yellow
}

# 3. Copy python3X.dll and python3X.zip to build dir and pymodules\
# (qrenderdoc.exe needs stdlib zip in its directory to initialize embedded Python)
$PyVer = $null
$PyExeInVenv = Join-Path $PythonPrefix "Scripts\python.exe"
if (-not (Test-Path $PyExeInVenv)) { $PyExeInVenv = Join-Path $PythonPrefix "python.exe" }
if (Test-Path $PyExeInVenv) {
    $PyVer = & $PyExeInVenv -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')"
}
if ($PyVer) {
    $PyDllName = "python$PyVer.dll"
    $PyZipName = "python$PyVer.zip"

    # Copy to build dir (for qrenderdoc.exe) — always overwrite
    foreach ($fname in @($PyDllName, $PyZipName)) {
        $src = Join-Path $PythonPrefix $fname
        if (-not (Test-Path $src)) { $src = Join-Path $BuildDir $fname }
        $dst = Join-Path $BuildDir $fname
        if (Test-Path $src) {
            Copy-Item $src $dst -Force
            $srcSize = (Get-Item $src).Length
            $dstSize = (Get-Item $dst).Length
            if ($srcSize -ne $dstSize) {
                Write-Host "  Updated $fname ($dstSize -> $srcSize bytes) -> $BuildDir" -ForegroundColor Yellow
            }
        }
    }

    # Copy to pymodules (for Python import renderdoc) — always overwrite
    if (Test-Path $PymodulesDir) {
        foreach ($fname in @($PyDllName, $PyZipName)) {
            $src = Join-Path $BuildDir $fname
            $dst = Join-Path $PymodulesDir $fname
            if (Test-Path $src) {
                Copy-Item $src $dst -Force
            }
        }
    }
}

Write-Host ""
Write-Host "==== Build Output ====" -ForegroundColor Green
if (Test-Path $RenderdocPyd) {
    Write-Host "  renderdoc.pyd : $RenderdocPyd" -ForegroundColor Green
} else {
    Write-Host "  renderdoc.pyd : NOT FOUND" -ForegroundColor Red
}
if (Test-Path $RenderdocDll) {
    Write-Host "  renderdoc.dll  : $RenderdocDll" -ForegroundColor Green
} else {
    Write-Host "  renderdoc.dll  : NOT FOUND" -ForegroundColor Red
}

Write-Host ""
Write-Host "==== Usage ====" -ForegroundColor Green
$PydDir = Split-Path $RenderdocPyd -Parent
Write-Host "  set PYTHONPATH=$PydDir" -ForegroundColor White
Write-Host "  python -c `"import renderdoc; print('OK')`"" -ForegroundColor White
Write-Host ""
Write-Host "  # renderquery 不需要安装，直接加到 PYTHONPATH 即可"
Write-Host "  set PYTHONPATH=$PydDir;$(Join-Path $RepoRoot 'renderquery')"
Write-Host "  python -m renderquery.examples.top10_gpu_drawcall_screenshots <capture.rdc> --output-dir ./out/"