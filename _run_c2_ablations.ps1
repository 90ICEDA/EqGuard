# Wait for ALL three v3.1 seed score dumps, then run the C2/C4 ablations on _dev4.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$dev = Join-Path $root 'generate_trans\folds\_dev4'
$log = Join-Path $env:TEMP ("c2ablate_" + (Get-Date -Format 'HHmmss') + ".log")

# 1) robust wait: all three seed dumps must exist AND no training python must be running
#    2026-10-19：加锁文件判断（避免在 seed 之间 30s 重试窗口里误判空闲 ✗）
$lockFile = Join-Path $root '_devcfg\.v31_train.lock'
$need = @('gnn_v31_s42.npz', 'gnn_v31_s1.npz', 'gnn_v31_s2.npz') | ForEach-Object { Join-Path $root ('_devcfg\' + $_) }
while ($true) {
  $missing = $need | Where-Object { -not (Test-Path $_) }
  $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -like '*train_test2.3.py*' }).Count
  $locked = Test-Path $lockFile
  if (-not $missing -and $busy -eq 0 -and -not $locked) { break }
  "[wait] missing=$($missing.Count) busy=$busy lock=$locked $(Get-Date -Format HH:mm:ss)" | Out-File $log -Append -Encoding utf8
  Start-Sleep -Seconds 120
}
"[go] v3.1 baseline complete $(Get-Date -Format s)" | Out-File $log -Append -Encoding utf8

# 防睡眠（复用 train runner 生成的脚本；宿主被关掉时重建一份）
$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
if (-not (Test-Path $kaFile)) {
  @'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
}
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $kaFile -PassThru -WindowStyle Hidden

# 2) consistency-weight ablation: lambda_const in {0, 0.3, 1.0, 3.0}
foreach ($lc in 0.0, 0.3, 1.0, 3.0) {
  $cfg = Join-Path $root ("_devcfg\dual_lc" + ($lc -replace '\.', 'p') + ".yaml")
  (Get-Content (Join-Path $root '_devcfg\dual.yaml') -Raw) -replace 'lambda_const: 1\.0', ("lambda_const: " + $lc) |
    Set-Content $cfg -Encoding utf8
  "[start] lc=$lc" | Out-File $log -Append -Encoding utf8
  & $gpy -X utf8 -u (Join-Path $root 'train_test2.3.py') --work-dir $dev --fold-json (Join-Path $dev 'views.json') `
    --pt-dir (Join-Path $dev 'data\processed') --config $cfg --fold-mode fold --epochs 60 --steps-per-epoch 1 `
    --val-every 5 --view-policy all --amp --seed 42 --extra-feats cone5 --label-mask trust `
    --dump-scores (Join-Path $root ("_devcfg\dev4_lc" + ($lc -replace '\.', 'p') + ".npz")) --tag ("lc" + $lc) *>> $log
  "[done] lc=$lc rc=$LASTEXITCODE" | Out-File $log -Append -Encoding utf8
}

# 3) full-representation vs functional-only consistency (ablation for "only functional branch")
& $gpy -X utf8 -u (Join-Path $root 'train_test2.3.py') --work-dir $dev --fold-json (Join-Path $dev 'views.json') `
  --pt-dir (Join-Path $dev 'data\processed') --config (Join-Path $root '_devcfg\dual.yaml') --fold-mode fold `
  --epochs 60 --steps-per-epoch 1 --val-every 5 --view-policy all --amp --seed 42 --extra-feats cone5 `
  --func-const --label-mask trust --dump-scores (Join-Path $root '_devcfg\dev4_funconly.npz') --tag funconly *>> $log
"[done] func-only rc=$LASTEXITCODE" | Out-File $log -Append -Encoding utf8
"DONE $(Get-Date -Format s)" | Out-File $log -Append -Encoding utf8
