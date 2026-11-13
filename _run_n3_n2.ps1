# N3 + N2 顺序执行 ✓（v3.1 正式 fold；不覆盖任何已有 npz ✗）
#   S1 = N3 收尾：λ=5 × seed 1,2（补 3-seed）
#   S2 = N2 复核：A0 单分支 / A1 单分支+trust / A2 双分支+trust / (A3=现有基线含 cone5 ✓)
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log = Join-Path $env:TEMP ('n3n2_' + (Get-Date -Format 'HHmmss') + '.log')
$lock = Join-Path $root '_devcfg\.v31_train.lock'
New-Item -ItemType File -Path $lock -Force | Out-Null

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $kaFile -PassThru -WindowStyle Hidden

function Run-One($tag, $npz, $cfgPath, $mode, $trust, $region, $seed) {
  if (Test-Path $npz) { "[skip] $tag (已有 npz)" | Out-File $log -Append -Encoding Unicode; return }
  $argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
    '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
    '--pt-dir', (Join-Path $fold 'data\processed'), '--config', $cfgPath, '--fold-mode', 'fold',
    '--epochs', '100', '--steps-per-epoch', '1', '--val-every', '5', '--view-policy', 'all',
    '--amp', '--seed', "$seed", '--train-mode', "$mode", '--dump-scores', $npz, '--tag', $tag)
  if ($trust) { $argList += @('--label-mask', 'trust') }
  if ($region -gt 0) { $argList += @('--region-loss', "$region", '--region-mode', 'dff') }
  if ($tag -like '*A3*' -or $tag -like '*A4*') { $argList += @('--extra-feats', 'cone5') }
  $outF = Join-Path $env:TEMP ("$tag.out")
  $errF = Join-Path $env:TEMP ("$tag.err")
  "[run] $tag $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
  $p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
         -RedirectStandardOutput $outF -RedirectStandardError $errF
  while (-not $p.HasExited) {
    Start-Sleep -Seconds 60
    "[hb] $tag $((Get-Content $outF -Tail 1 -ErrorAction SilentlyContinue))" |
      Out-File $log -Append -Encoding Unicode
  }
  "[exit] $tag rc=$($p.ExitCode) npz=$(Test-Path $npz) $(Get-Date -Format s)" |
    Out-File $log -Append -Encoding Unicode
}

try {
  # ---------- S1：N3 收尾（λ=5 补 seed 1,2）----------
  "=== S1 N3 lambda=5 seeds 1,2 ===" | Out-File $log -Append -Encoding Unicode
  foreach ($s in 1, 2) {
    Run-One "v31r_l50s$s" (Join-Path $root "_devcfg\gnn_v31r_l50_s$s.npz") `
      (Join-Path $root '_devcfg\dual.yaml') 4 $true 5.0 $s
  }
  "N3_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'n3.done') -Encoding utf8

  # ---------- S2：N2 四变体（A3=现有基线 ✓）----------
  "=== S2 N2 A0/A1/A2 x seeds ===" | Out-File $log -Append -Encoding Unicode
  foreach ($s in 42, 1, 2) {
    Run-One "v31a_A0s$s" (Join-Path $root "_devcfg\gnn_v31a_A0_s$s.npz") `
      (Join-Path $root '_devcfg\asl.yaml') 2 $false 0 $s
    Run-One "v31a_A1s$s" (Join-Path $root "_devcfg\gnn_v31a_A1_s$s.npz") `
      (Join-Path $root '_devcfg\asl.yaml') 2 $true 0 $s
    Run-One "v31a_A2s$s" (Join-Path $root "_devcfg\gnn_v31a_A2_s$s.npz") `
      (Join-Path $root '_devcfg\dual.yaml') 4 $true 0 $s
  }
  "N2_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'n2.done') -Encoding utf8
}
finally {
  if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
  Remove-Item $lock -Force -ErrorAction SilentlyContinue
  "N3N2_ALL_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'n3n2.done') -Encoding utf8
}
