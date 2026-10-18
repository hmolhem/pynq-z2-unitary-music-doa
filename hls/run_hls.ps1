# =====================================================================
# run_hls.ps1 -- Vitis HLS 2025.2 flow for one kernel (Windows PowerShell)
#
#   powershell -ExecutionPolicy Bypass -File run_hls.ps1 -Kernel scm
#   powershell -ExecutionPolicy Bypass -File run_hls.ps1 -Kernel scm -Steps csim,synth
#
# Steps (default: all, in this order):
#   csim     C simulation          (vitis-run --mode hls --csim)
#   synth    C synthesis           (v++ -c --mode hls)
#   cosim    C/RTL co-simulation   (vitis-run --mode hls --cosim)
#   package  IP catalog export     (vitis-run --mode hls --package)
#
# Work directory: hls/<kernel>/work   (ignored by git)
# Key reports are copied to hls/<kernel>/reports/ (committed as evidence).
# =====================================================================
param(
    [Parameter(Mandatory = $true)][string]$Kernel,
    [string[]]$Steps = @("csim", "synth", "cosim", "package"),
    [string]$XilinxRoot = "C:\AMDXilinx\2025.2"
)

$ErrorActionPreference = "Stop"
$hlsDir    = $PSScriptRoot
$kernelDir = Join-Path $hlsDir $Kernel
$config    = Join-Path $kernelDir "hls_config.cfg"
$work      = Join-Path $kernelDir "work"
$reports   = Join-Path $kernelDir "reports"

if (-not (Test-Path $config)) { throw "No hls_config.cfg in $kernelDir" }

function Find-Tool([string]$name) {
    $candidate = Join-Path $XilinxRoot "Vitis\bin\$name.bat"
    if (Test-Path $candidate) { return $candidate }
    $found = Get-ChildItem $XilinxRoot -Filter "$name.bat" -Recurse -Depth 4 -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if ($found) { return $found.FullName }
    throw "Cannot find $name.bat under $XilinxRoot (use -XilinxRoot to point at your install)"
}

$vitisRun = Find-Tool "vitis-run"
$vpp      = Find-Tool "v++"
Write-Host "vitis-run: $vitisRun"
Write-Host "v++      : $vpp"

function Invoke-Step([string]$label, [string]$exe, [string[]]$toolArgs) {
    Write-Host ""
    Write-Host "=== $label ===" -ForegroundColor Cyan
    Write-Host "$exe $($toolArgs -join ' ')"
    $t0 = Get-Date
    & $exe @toolArgs
    $code = $LASTEXITCODE
    $dt = [int]((Get-Date) - $t0).TotalSeconds
    if ($code -ne 0) {
        Write-Host "=== $label FAILED (exit $code, $dt s) ===" -ForegroundColor Red
        exit $code
    }
    Write-Host "=== $label OK ($dt s) ===" -ForegroundColor Green
}

Push-Location $kernelDir
try {
    foreach ($s in $Steps) {
        switch ($s) {
            "csim"    { Invoke-Step "C simulation"  $vitisRun @("--mode", "hls", "--csim",    "--config", $config, "--work_dir", $work) }
            "synth"   { Invoke-Step "C synthesis"   $vpp      @("-c", "--mode", "hls",        "--config", $config, "--work_dir", $work) }
            "cosim"   { Invoke-Step "Co-simulation" $vitisRun @("--mode", "hls", "--cosim",   "--config", $config, "--work_dir", $work) }
            "package" { Invoke-Step "IP export"     $vitisRun @("--mode", "hls", "--package", "--config", $config, "--work_dir", $work) }
            default   { throw "Unknown step '$s' (use csim, synth, cosim, package)" }
        }
    }
} finally {
    Pop-Location
}

# Copy the evidence that belongs in the repository
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$patterns = @("*_csynth.rpt", "*_cosim.rpt", "csynth.rpt")
foreach ($p in $patterns) {
    Get-ChildItem $work -Filter $p -Recurse -ErrorAction SilentlyContinue |
        ForEach-Object { Copy-Item $_.FullName $reports -Force; Write-Host "report: $($_.Name)" }
}
$ip = Get-ChildItem $work -Filter "component.xml" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($ip) { Write-Host "IP repository: $($ip.DirectoryName)" -ForegroundColor Green }

Write-Host ""
Write-Host "Done. Reports in $reports"
