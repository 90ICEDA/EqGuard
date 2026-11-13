# _stop_c_v3_after_r42.ps1 -- wait for C v3 seed42 summary, then stop the queue (no R1/R2/SW).
$root = $PSScriptRoot
$res = Join-Path $root 'results\hosts_bt31_seed42mode4_allb1_fold_fghtl_CncleanV3R42\circuit_level_summary.csv'
$log = Join-Path $root 'logs\stop_c_v3.log'
function W($m) { Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) -Encoding UTF8 }
W 'waiting C_v3 seed42 summary'
$deadline = (Get-Date).AddHours(1)
while (-not (Test-Path $res)) {
  if ((Get-Date) -gt $deadline) { W 'timeout'; exit 1 }
  Start-Sleep -Seconds 15
}
W 'seed42 summary found; stopping queue + R42 process'
$ps = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'train_test2.3' -and $_.CommandLine -match 'fghtl_CncleanV3R42' }
foreach ($p in $ps) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; W "stop python $($p.ProcessId)" }
Stop-Process -Id 105244 -Force -ErrorAction SilentlyContinue
W 'stopped; keep seed42 result, no R1/R2/SW'
