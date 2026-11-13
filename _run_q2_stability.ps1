# _run_q2_stability.ps1 -- after P2 C seed2, run the 832 positive-pair stability analysis.
$root = $PSScriptRoot
Set-Location $root
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$p2 = Join-Path $env:TEMP 'p2_c2.done'
$log = Join-Path $root 'logs\q2_stability.log'
$done = Join-Path $env:TEMP 'q2_stability.done'
if (Test-Path $done) { Remove-Item $done -Force }
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(2)
while (-not (Test-Path $p2)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout waiting p2_c2.done'; exit 1 }
  Start-Sleep -Seconds 20
}
while ((Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'train_test2.3' } | Measure-Object).Count -gt 0) {
  Start-Sleep -Seconds 10
}
Log '--- Q2 stability 832 (C_v2 vs C_v1_clean)'
& $gpy -X utf8 -u phase2\ys\fghtl_stability_832.py --device cuda:0 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'q2_stability.out') -Encoding UTF8
Log ("    rc={0}" -f $LASTEXITCODE)
'Q2_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== Q2 done ==='
