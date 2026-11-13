# _monitor_p3_56_rest.ps1 -- monitor the 3-split 56-dim LRO resume.
$root = $PSScriptRoot
$out = Join-Path $env:TEMP 'cp3_56_rest.out'
$res = Join-Path $root 'results\hosts_bt31_seed42mode4_allb1_lro_fghtl_P3lroC5S42\done_splits.json'
$log = Join-Path $root 'logs\monitor_56_rest.log'
$done = Join-Path $env:TEMP 'p3_56.done'
function W($m) { Add-Content -Path $log -Value $m -Encoding UTF8 }
W ("[{0}] monitor rest start" -f (Get-Date -Format 'HH:mm:ss'))
while (-not (Test-Path $done)) {
  $now = Get-Date
  $epoch = '?'
  if (Test-Path $out) {
    $m = Select-String -Path $out -Pattern '\[EPOCH (\d+)/100\]' | Select-Object -Last 1
    if ($m) { $epoch = $m.Matches[0].Groups[1].Value }
  }
  $ds = '[]'
  if (Test-Path $res) { $ds = ((Get-Content $res -Raw) -replace '\s+', ' ').Trim() }
  $gpu = (& nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader 2>$null) -join '; '
  $np = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
         Where-Object { $_.CommandLine -match 'train_test2.3' } | Measure-Object).Count
  W ("[{0}] epoch={1}/100 done={2} gpu={3} procs={4}" -f `
      $now.ToString('HH:mm:ss'), $epoch, $ds, $gpu, $np)
  Start-Sleep -Seconds 60
}
W ("[{0}] P3_56_DONE" -f (Get-Date -Format 'HH:mm:ss'))
