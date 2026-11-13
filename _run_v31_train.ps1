# v3.1 fold training (graphs already built). 3 seeds × **60 epoch**（与 dev4 全套消融同口径 ✓）
# 2026-10-19 修复：
#   ① 防睡眠（SetThreadExecutionState ✓）——上一轮就是被"睡眠"杀掉的 ✗
#   ② 锁文件（CPU 脚本据此判断"训练在跑" ✓，避免抢 GPU ✗）
#   ③ 每 60 s 心跳日志（epoch 内部无打印 ✗ → 用 GPU 占用 + 耗时估算 ETA ✓）
#   ④ 子进程用 Start-Process 重定向 ✓（日志统一 UTF-8 ✓，不再 UTF-16 混排 ✗）
#   ⑤ 全部 3 seed 完成 → 自动 summarize_npz（3-seed 主表 ✓）
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$lock = Join-Path $root '_devcfg\.v31_train.lock'
$hb = Join-Path $env:TEMP 'v31_heartbeat.log'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
# v3.1 显存硬约束 ✓：3.22 M 节点 4 层双分支在 8.15 GB 上 backward 必 OOM ✗
#   → 梯度检查点（重算换显存 ✓，数值等价 ✓）+ 可扩展段分配（防碎片 ✗）
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$stamp = Get-Date -Format 'HHmmss'

# ---- 防睡眠：后台进程按住 ES_SYSTEM_REQUIRED|ES_DISPLAY_REQUIRED ----
$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $kaFile -PassThru -WindowStyle Hidden

New-Item -ItemType File -Path $lock -Force | Out-Null
"=== v3.1 train start $stamp ===" | Out-File $hb -Append -Encoding utf8
try {
  foreach ($s in 42, 1, 2) {
    $npz = Join-Path $root ("_devcfg\gnn_v31_s" + $s + ".npz")
    if (Test-Path $npz) { "[skip] seed=$s already has npz" | Out-File $hb -Append -Encoding utf8; continue }
    foreach ($attempt in 1, 2) {
      $outF = Join-Path $env:TEMP ("v31_s" + $s + "_a" + $attempt + "_" + $stamp + ".out")
      $errF = Join-Path $env:TEMP ("v31_s" + $s + "_a" + $attempt + "_" + $stamp + ".err")
      $argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
        '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
        '--pt-dir', (Join-Path $fold 'data\processed'),
        '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', 'fold',
        '--epochs', '100', '--steps-per-epoch', '1', '--val-every', '5', '--view-policy', 'all',
        '--amp', '--seed', "$s", '--extra-feats', 'cone5', '--label-mask', 'trust',
        '--dump-scores', $npz, '--tag', ("v31s" + $s))
      "[start] seed=$s attempt=$attempt $(Get-Date -Format s)" | Out-File $hb -Append -Encoding utf8
      $t0 = Get-Date
      $p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
             -RedirectStandardOutput $outF -RedirectStandardError $errF
      while (-not $p.HasExited) {
        Start-Sleep -Seconds 60
        $g = (nvidia-smi --query-gpu=memory.used --format=csv,noheader) -replace "`r", ""
        $mins = [int]((Get-Date) - $t0).TotalMinutes
        "seed=$s a=$attempt elapsed=${mins}m gpu=$g" | Out-File $hb -Append -Encoding utf8
      }
      $rc = $p.ExitCode
      if ($null -eq $rc) { $p.WaitForExit(); $rc = $p.ExitCode }
      "[exit] seed=$s attempt=$attempt rc=$rc after $([int]((Get-Date)-$t0).TotalMinutes)m $(Get-Date -Format s)" |
        Out-File $hb -Append -Encoding utf8
      if (Test-Path $npz) { break }
      Start-Sleep -Seconds 30
    }
  }

  $need = @('gnn_v31_s42.npz', 'gnn_v31_s1.npz', 'gnn_v31_s2.npz') |
          ForEach-Object { Join-Path $root ('_devcfg\' + $_) }
  if (-not ($need | Where-Object { -not (Test-Path $_) })) {
    & $py -X utf8 -u (Join-Path $root 'phase2\ys\summarize_npz.py') `
      --pt (Join-Path $fold 'data\processed\trans_graph.pt') --npz $need `
      --out (Join-Path $root '_devcfg\v31_3seed_summary.csv') *>> (Join-Path $env:TEMP 'v31_summary.log')
    "[summary] rc=$LASTEXITCODE $(Get-Date -Format s)" | Out-File $hb -Append -Encoding utf8
  }
}
finally {
  Remove-Item $lock -Force -ErrorAction SilentlyContinue
  if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
  "V31_TRAIN_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'v31_train.done') -Encoding utf8
  "=== v3.1 train end ===" | Out-File $hb -Append -Encoding utf8
}
