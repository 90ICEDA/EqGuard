# N4 ✓：三向泛化试点（等 N1 名字图跑完 ✓）→ host-LOCO（1 折 ✓）+ recipe-LRO（5 折 ✓）→ 汇总 → 提交
#   预算口径 ✓：**统一 60 epoch**（试点 ✓，与正式 100 epoch 不同 ✗ → 表里必须注明 ⚠️）
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('n4_' + (Get-Date -Format 'HHmmss') + '.log')

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while (-not (Test-Path (Join-Path $env:TEMP 'n1names.done'))) {
  "[wait] n1names not done $(Get-Date -Format HH:mm:ss)" | Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 180
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

function Run-Protocol($mode, $tag) {
  $argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
    '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
    '--pt-dir', (Join-Path $fold 'data\processed'),
    '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', $mode,
    '--circuits', 's38584t100', '--epochs', '60', '--steps-per-epoch', '1', '--val-every', '5',
    '--view-policy', 'all', '--amp', '--seed', '42', '--extra-feats', 'cone5',
    '--label-mask', 'trust', '--tag', $tag)
  "[run] $mode ($tag) $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
  $outF = Join-Path $env:TEMP ("n4_$tag.out")
  $errF = Join-Path $env:TEMP ("n4_$tag.err")
  $p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
         -RedirectStandardOutput $outF -RedirectStandardError $errF
  while (-not $p.HasExited) {
    Start-Sleep -Seconds 60
    "[hb] $tag $((Get-Content $outF -Tail 1 -ErrorAction SilentlyContinue))" |
      Out-File $log -Append -Encoding Unicode
  }
  "[exit] $tag rc=$($p.ExitCode) $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
}

Run-Protocol 'loco' 'n4loco'
Run-Protocol 'lro'  'n4lro'

& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_summary.py') *>> $log
"[sum] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N4): --fold-mode lro + host-LOCO/recipe-LRO pilot (60 epoch, 1 seed) + protocol summary' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
"N4_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'n4.done') -Encoding utf8
