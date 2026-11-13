# Wait for the fold-v3 rebuild (parser2 + process_pt2) to finish, then run a 12-epoch smoke test.
# The smoke must show: loss decreasing, val_AP_trans not flat at ~0.0004, val_AP_orig finite.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$out = Join-Path $env:TEMP '_watch_then_smoke.out'
"watch start $(Get-Date -Format s)" | Out-File -FilePath $out -Encoding utf8
$feats = Join-Path $root 'generate_trans\folds\hosts_bt3\data\for_train\feats_trans.npy'
$t0 = (Get-Item $feats).LastWriteTime

# 1) wait for rebuild (max 120 min)
$deadline = (Get-Date).AddMinutes(120)
while ((Get-Date) -lt $deadline) {
  $n = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*parser2.py*' -or $_.CommandLine -like '*process_pt2.py*' } |
        Measure-Object).Count
  if ($n -eq 0) { break }
  Start-Sleep -Seconds 20
}
"rebuild done $(Get-Date -Format s)" | Out-File -FilePath $out -Encoding utf8 -Append
$t1 = (Get-Item $feats).LastWriteTime
"feats mtime: before=$t0 after=$t1 (changed=" + ($t1 -gt $t0) + ")" | Out-File -FilePath $out -Encoding utf8 -Append

# 2) smoke: 12 epochs, same settings as the baseline otherwise
& $py -X utf8 -u (Join-Path $root 'train_test2.3.py') `
  --work-dir (Join-Path $root 'generate_trans\folds\hosts_bt3') `
  --fold-json (Join-Path $root 'generate_trans\folds\hosts_bt3\views.json') `
  --pt-dir (Join-Path $root 'generate_trans\folds\hosts_bt3\data\processed') `
  --config (Join-Path $root 'config_bt3_gpu.yaml') `
  --fold-mode fold --epochs 12 --val-every 2 --view-policy random --view-budget 4 `
  --amp --seed 42 --tag smoke12_stage1 *> (Join-Path $env:TEMP 'bt3_smoke12.log')
"smoke rc=$LASTEXITCODE $(Get-Date -Format s)" | Out-File -FilePath $out -Encoding utf8 -Append

# 3) dump the train log tail for a quick look
$tl = Join-Path $root 'results\hosts_bt3_seed42mode4_randomb4_fold_smoke12_stage1\train_log.csv'
if (Test-Path $tl) { Get-Content $tl | Out-File -FilePath $out -Encoding utf8 -Append }
"DONE $(Get-Date -Format s)" | Out-File -FilePath $out -Encoding utf8 -Append
