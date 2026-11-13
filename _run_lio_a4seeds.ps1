# 链式补跑 ✓：等 LIO@100ep（tag n4blio42b）结束 → ①刷新 T14 汇总 ②A4 seed 1,2 ③A4 3-seed 汇总 ④提交
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\_dev_a4'
$log = Join-Path $env:TEMP ('chain_' + (Get-Date -Format 'HHmmss') + '.log')
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$kaFile -PassThru -WindowStyle Hidden

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while ($true) {
  $busy = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
          Where-Object { $_.CommandLine -match 'n4blio42b' }
  if (-not $busy) { break }
  "[wait] lio busy $(Get-Date -Format HH:mm:ss)" | Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 60
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

# ① 刷新 N4 汇总（LIO@100ep 入表候选 ✓）
& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_summary.py') --match n4blio42b `
   --out-dir (Join-Path $root '10.15\06_统一评测协议\N4_三向泛化_100ep') *>> $log
"[sum] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

# ② A4 seed 1 / 2（60 ep，同 a4diag 配置 ✓）
foreach ($s in 1, 2) {
  $npz = Join-Path $root "_devcfg\gnn_a4_s$s.npz"
  $a4args = @('-X','utf8','-u',(Join-Path $root 'train_test2.3.py'),
    '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
    '--pt-dir', (Join-Path $fold 'data\processed'),
    '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', 'fold',
    '--epochs', '60', '--steps-per-epoch', '1', '--val-every', '5',
    '--view-policy', 'all', '--amp', '--seed', "$s", '--dump-scores', $npz,
    '--tag', "a4diag_s$s")
  "[run] a4 seed=$s $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
  $p = Start-Process -FilePath $gpy -ArgumentList $a4args -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $env:TEMP "a4s$s.out") `
        -RedirectStandardError  (Join-Path $env:TEMP "a4s$s.err")
  while (-not $p.HasExited) { Start-Sleep -Seconds 30 }
  "[exit] a4 seed=$s rc=$($p.ExitCode) npz=$(Test-Path $npz) $(Get-Date -Format s)" |
    Out-File $log -Append -Encoding Unicode
}

# ③ A4 3-seed 汇总 ✓
$npzs = @(Join-Path $root '_devcfg\gnn_a4_s42.npz') +
        (@(1,2) | ForEach-Object { Join-Path $root "_devcfg\gnn_a4_s$_.npz" }) |
        Where-Object { Test-Path $_ }
& $py -X utf8 -u (Join-Path $root 'phase2\ys\a4_triplet_diag.py') --fold $fold `
   --npz $npzs --out-dir (Join-Path $root '10.15\02_弱监督检测\N1_对照诊断\a4') *>> $log
"[a4tri] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N4/N1): LIO@100ep summary + A4 seeds 1,2 with 3-seed triplet summary' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
"CHAIN_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'chain.done') -Encoding utf8
