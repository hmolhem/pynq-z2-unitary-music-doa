# =====================================================================
# run_dse.ps1 -- synthesis-only design-space variants (Vitis HLS 2025.2)
#
#   powershell -ExecutionPolicy Bypass -File hls\run_dse.ps1
#
#   dse/scm_mul9      SCM kernel with at most 9 shared multipliers
#   dse/jac_cordic16  Jacobi kernel with 16 CORDIC iterations
#   dse/jac_cordic20  Jacobi kernel with 20 CORDIC iterations
#
# Reports go to hls/dse/<variant>/reports/. Accuracy of the CORDIC variants
# comes from python/dse_cordic.py (the C model of a variant is not run).
# =====================================================================
param([string]$XilinxRoot = "C:\AMDXilinx\2025.2")
$ErrorActionPreference = "Stop"
foreach ($v in @("dse\scm_mul9", "dse\jac_cordic16", "dse\jac_cordic20")) {
    Write-Host ""
    Write-Host "##### $v #####" -ForegroundColor Yellow
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run_hls.ps1") -Kernel $v -Steps synth -XilinxRoot $XilinxRoot
    if ($LASTEXITCODE -ne 0) { throw "$v failed" }
}
Write-Host "DSE synthesis done." -ForegroundColor Green
