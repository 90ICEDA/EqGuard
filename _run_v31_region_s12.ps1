# C6/P1 复核：λ_region=10（损失尺度对齐后 ✓）× seed 1,2（seed 42 已完成 ✓）
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log = Join-Path $env:TEMP ('v31r_s12_' + (Get-Date -Format 'HHmmss') + '.log')

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $kaFile -PassThru -WindowStyle Hidden

"[start] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
foreach ($s in 1, 2) {
  $npz = Join-Path $root ("_devcfg\gnn_v31r_l100_s" + $s + ".npz")
  if (Test-Path $npz) { "[skip] seed=$s" | Out-File $log -Append -Encoding Unicode; continue }
  $argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
    '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
    '--pt-dir', (Join-Path $fold 'data\processed'),
    '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', 'fold',
    '--epochs', '100', '--steps-per-epoch', '1', '--val-every', '5', '--view-policy', 'all',
    '--amp', '--seed', "$s", '--extra-feats', 'cone5', '--label-mask', 'trust',
    '--region-loss', '10.0', '--region-mode', 'dff',
    '--dump-scores', $npz, '--tag', ("v31r_l100s" + $s))
  $outF = Join-Path $env:TEMP ("v31r_l100_s" + $s + ".out")
  $errF = Join-Path $env:TEMP ("v31r_l100_s" + $s + ".err")
  "[run] seed=$s $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
  $p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
         -RedirectStandardOutput $outF -RedirectStandardError $errF
  while (-not $p.HasExited) {
    Start-Sleep -Seconds 60
    "[hb] seed=$s $((Get-Content $outF -Tail 1 -ErrorAction SilentlyContinue))" |
      Out-File $log -Append -Encoding Unicode
  }
  "[exit] seed=$s rc=$($p.ExitCode) npz=$(Test-Path $npz) $(Get-Date -Format s)" |
    Out-File $log -Append -Encoding Unicode
}
if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
"V31R_S12_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'v31r_s12.done') -Encoding utf8
