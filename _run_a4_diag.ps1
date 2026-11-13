# A4 全量诊断 ✓：等 N4-100ep 跑完（n4b.done ✓）→ 建 `_dev_a4` fold → 训练 60 epoch → 三胞胎诊断 → 提交
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\_dev_a4'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('a4_' + (Get-Date -Format 'HHmmss') + '.log')
New-Item -ItemType File -Path (Join-Path $root '_devcfg\.v31_train.lock') -Force | Out-Null

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $kaFile -PassThru -WindowStyle Hidden

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while (-not (Test-Path (Join-Path $env:TEMP 'n4b.done'))) {
  "[wait] n4b not done $(Get-Date -Format HH:mm:ss)" | Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 120
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

try {
  # 1) 建 fold（只读 hosts_a4 ✓）
  & $py -X utf8 -u (Join-Path $root 'phase2\ys\build_a4_fold.py') *>> $log
  "[build] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

  # 2) 在 _dev_a4 上训练（60 epoch，无 trust / 无 cone5 ✓ 该 fold 没有这些文件 ✗）
  $npz = Join-Path $root '_devcfg\gnn_a4_s42.npz'
  $argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
    '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
    '--pt-dir', (Join-Path $fold 'data\processed'),
    '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', 'fold',
    '--epochs', '60', '--steps-per-epoch', '1', '--val-every', '5', '--view-policy', 'all',
    '--amp', '--seed', '42', '--dump-scores', $npz, '--tag', 'a4diag')
  $outF = Join-Path $env:TEMP 'a4train.out'
  $errF = Join-Path $env:TEMP 'a4train.err'
  "[run] train $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
  $p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
         -RedirectStandardOutput $outF -RedirectStandardError $errF
  while (-not $p.HasExited) {
    Start-Sleep -Seconds 60
    "[hb] $((Get-Content $outF -Tail 1 -ErrorAction SilentlyContinue))" |
      Out-File $log -Append -Encoding Unicode
  }
  "[exit] train rc=$($p.ExitCode) npz=$(Test-Path $npz) $(Get-Date -Format s)" |
    Out-File $log -Append -Encoding Unicode

  # 3) 三胞胎诊断 ✓
  if (Test-Path $npz) {
    & $py -X utf8 -u (Join-Path $root 'phase2\ys\a4_family_diag.py') --npz $npz *>> $log
    "[diag] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode
  }

  git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
  git commit -q -m 'feat(N1): build _dev_a4 fold (5 hosts x 8 shapes x 3 kinds) + triplet diagnosis (trojan vs ctldead/ctlequiv)' 2>&1 |
    Out-File $log -Append -Encoding Unicode
  "[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
}
finally {
  if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
  Remove-Item (Join-Path $root '_devcfg\.v31_train.lock') -Force -ErrorAction SilentlyContinue
  "A4_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'a4.done') -Encoding utf8
}
