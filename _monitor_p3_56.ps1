# _monitor_p3_56.ps1 -- non-interactive monitor for 56-dim LOCO/LRO.
$root = $PSScriptRoot
$out = Join-Path $env:TEMP 'cp3_56_fghtl_P3lroC5S42.out'
$res = Join-Path $root 'results\hosts_bt31_seed42mode4_allb1_lro_fghtl_P3lroC5S42\done_splits.json'
$log = Join-Path $root 'logs\monitor_56.log'
$done = Join-Path $env:TEMP 'p3_56.done'
$decision = Join-Path $env:TEMP 'p3_56_decision.txt'
$start = [datetime]'2026-10-24 17:03:26'
$flagged = $false
if (Test-Path $decision) { Remove-Item $decision -Force }
function W($m) { Add-Content -Path $log -Value $m -Encoding UTF8 }
W ("[{0}] monitor start (lro_start={1:HH:mm:ss})" -f (Get-Date -Format 'HH:mm:ss'), $start)
while (-not (Test-Path $done)) {
  $now = Get-Date
  $epoch = '?'
  $split = '?'
  if (Test-Path $out) {
    $m = Select-String -Path $out -Pattern '\[EPOCH (\d+)/100\]' | Select-Object -Last 1
    if ($m) { $epoch = $m.Matches[0].Groups[1].Value }
    $s = Select-String -Path $out -Pattern 'train_views=\d+' | Select-Object -Last 1
    if ($s) { $split = ($s.Line -replace '\s+', ' ') }
  }
  $ds = '[]'
  if (Test-Path $res) { $ds = ((Get-Content $res -Raw) -replace '\s+', ' ').Trim() }
  $gpu = (& nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader 2>$null) -join '; '
  $np = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
         Where-Object { $_.CommandLine -match 'train_test2.3' } | Measure-Object).Count
  W ("[{0}] split={1} epoch={2}/100 done={3} gpu={4} procs={5}" -f `
      $now.ToString('HH:mm:ss'), $split, $epoch, $ds, $gpu, $np)
  if (-not $flagged -and $ds -match 'ys_abc') {
    $mt = (Get-Item $res).LastWriteTime
    $mins = [math]::Round(($mt - $start).TotalMinutes, 1)
    $d = if ($mins -gt 30) { 'SWITCH_3' } else { 'KEEP_5' }
    W ("FIRST_SPLIT_DONE elapsed={0} min decision={1}" -f $mins, $d)
    Set-Content -Path $decision -Value ("{0} {1}" -f $d, $mins) -Encoding UTF8
    $flagged = $true
  }
  Start-Sleep -Seconds 60
}
W ("[{0}] P3_56_DONE" -f (Get-Date -Format 'HH:mm:ss'))
