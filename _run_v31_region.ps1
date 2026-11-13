# P1 —— v3.1 正式训练 + **区域级损失**（C6 ✓）。默认不动现有结果 ✓：新 npz / 新 tag ✓。
# 先用 seed 42 跑 λ∈{0.5, 1.0}（各 ~15 min ✓），确认优于基线 0.1404 再扩到 3 seed ✓。
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log = Join-Path $env:TEMP ('v31r_' + (Get-Date -Format 'HHmmss') + '.log')

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $kaFile -PassThru -WindowStyle Hidden

"[start] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
foreach ($cfg in @(@{lam='0.5'; tag='l05'}, @{lam='1.0'; tag='l10'}, @{lam='5.0'; tag='l50'}, @{lam='10.0'; tag='l100'})) {
  $npz = Join-Path $root ("_devcfg\gnn_v31r_" + $cfg.tag + "_s42.npz")
  if (Test-Path $npz) { "[skip] $($cfg.tag) 已有 npz" | Out-File $log -Append -Encoding Unicode; continue }
  $argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
    '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
    '--pt-dir', (Join-Path $fold 'data\processed'),
    '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', 'fold',
    '--epochs', '100', '--steps-per-epoch', '1', '--val-every', '5', '--view-policy', 'all',
    '--amp', '--seed', '42', '--extra-feats', 'cone5', '--label-mask', 'trust',
    '--region-loss', $cfg.lam, '--region-mode', 'dff',
    '--dump-scores', $npz, '--tag', ('v31r_' + $cfg.tag + 's42'))
  $outF = Join-Path $env:TEMP ("v31r_" + $cfg.tag + ".out")
  $errF = Join-Path $env:TEMP ("v31r_" + $cfg.tag + ".err")
  "[run] lambda=$($cfg.lam) $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
  $p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
         -RedirectStandardOutput $outF -RedirectStandardError $errF
  while (-not $p.HasExited) {
    Start-Sleep -Seconds 60
    "[hb] lambda=$($cfg.lam) $((Get-Content $outF -Tail 1 -ErrorAction SilentlyContinue))" |
      Out-File $log -Append -Encoding Unicode
  }
  "[exit] lambda=$($cfg.lam) rc=$($p.ExitCode) npz=$(Test-Path $npz) $(Get-Date -Format s)" |
    Out-File $log -Append -Encoding Unicode
}
if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
"V31R_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'v31r.done') -Encoding utf8
