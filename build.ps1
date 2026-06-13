param(
    [switch]$OneFile,
    [string]$DistPath = 'dist'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$buildVenv = Join-Path $projectRoot '.venv-build'
$workPath = Join-Path $projectRoot ("build-" + [IO.Path]::GetFileName($DistPath))
$pythonExe = Join-Path $buildVenv 'Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    py -3.11 -m venv $buildVenv
}

$pythonExe = Join-Path $buildVenv 'Scripts\python.exe'

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install msal python-dotenv requests pyinstaller

$pythonBase = (& $pythonExe -c "import sys; print(sys.base_prefix)").Trim()
$dllDir = Join-Path $pythonBase 'DLLs'
$libBinDir = Join-Path $pythonBase 'Library\bin'
$tclLibDir = Join-Path $pythonBase 'Library\lib\tcl8.6'
$tkLibDir = Join-Path $pythonBase 'Library\lib\tk8.6'

# Ensure binary dependency discovery can resolve tkinter and ssl dependencies.
$env:PATH = "$dllDir;$libBinDir;$env:PATH"

$pyInstallerArgs = @(
    '--noconfirm',
    '--clean',
    '--windowed',
    '--distpath', $DistPath,
    '--workpath', $workPath,
    '--name', 'OneDriveSearch',
    '--add-binary', "$libBinDir\tcl86t.dll;.",
    '--add-binary', "$libBinDir\tk86t.dll;.",
    '--add-binary', "$libBinDir\libcrypto-1_1-x64.dll;.",
    '--add-binary', "$libBinDir\libssl-1_1-x64.dll;.",
    '--add-binary', "$libBinDir\liblzma.dll;.",
    '--add-binary', "$libBinDir\libbz2.dll;.",
    '--add-data', "$tclLibDir;tcl8.6",
    '--add-data', "$tkLibDir;tk8.6",
    'main.py'
)

if ($OneFile) {
    $pyInstallerArgs = @('--onefile') + $pyInstallerArgs
}

& $pythonExe -m PyInstaller @pyInstallerArgs

Write-Host ''
Write-Host 'Build completed.'
if ($OneFile) {
    Write-Host 'Executable: dist\OneDriveSearch.exe'
} else {
    Write-Host "Executable: $DistPath\OneDriveSearch\OneDriveSearch.exe"
}
