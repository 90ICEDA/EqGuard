# 收官队列 ✓：等 LIO 结束（lio.done ✓）→ ①重画 8 张 N1 图（新版分层布局 ✓）
#                               → ②N4 补 seed 1,2（loco ✓ + lro ✓，同 60 epoch ✓）→ ③刷新汇总 → ④提交
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('final_' + (Get-Date -Format 'HHmmss') + '.log')

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $kaFile -PassThru -WindowStyle Hidden

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while (-not (Test-Path (Join-Path $env:TEMP 'lio.done'))) {
  "[wait] lio not done $(Get-Date -Format HH:mm:ss)" | Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 120
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

# ---------- S1：重画 N1 图（新版 ✓）----------
Remove-Item (Join-Path $root '10.15\07_论文图表\figs\N1_case_*.png') -Force -ErrorAction SilentlyContinue
foreach ($pair in @(@{npz='_devcfg\gnn_v31_s42.npz'; tag='base'},
                    @{npz='_devcfg\gnn_v31r_l100_s42.npz'; tag='region'})) {
  $p = Join-Path $root $pair.npz
  if (-not (Test-Path $p)) { continue }
  & $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n1_case_figs.py') --npz $p --tag $pair.tag *>> $log
  "[fig] $($pair.tag) rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode
}
git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N1.4): redraw case figures (layered layout, score labels, legend, top-8 inset)' 2>&1 |
  Out-File $log -Append -Encoding Unicode

# ---------- S2：N4 补 seed 1,2 ----------
function Run-Protocol($mode, $seed) {
  $tag = "n4$($mode)s$seed"
  $argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
    '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
    '--pt-dir', (Join-Path $fold 'data\processed'),
    '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', $mode,
    '--circuits', 's38584t100', '--epochs', '60', '--steps-per-epoch', '1', '--val-every', '5',
    '--view-policy', 'all', '--amp', '--seed', "$seed", '--extra-feats', 'cone5',
    '--label-mask', 'trust', '--tag', $tag)
  "[run] $tag $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
  $outF = Join-Path $env:TEMP "$tag.out"
  $errF = Join-Path $env:TEMP "$tag.err"
  $p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
         -RedirectStandardOutput $outF -RedirectStandardError $errF
  while (-not $p.HasExited) {
    Start-Sleep -Seconds 60
    "[hb] $tag $((Get-Content $outF -Tail 1 -ErrorAction SilentlyContinue))" |
      Out-File $log -Append -Encoding Unicode
  }
  "[exit] $tag rc=$($p.ExitCode) $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
}
foreach ($s in 1, 2) {
  Run-Protocol 'loco' $s
}
foreach ($s in 1, 2) {
  Run-Protocol 'lro' $s
}

# ---------- S3：刷新三向汇总 ----------
& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_summary.py') *>> $log
"[sum] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N4): loco/lro seeds 1,2 (60 epoch pilot protocol) + refreshed three-way summary' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
"FINAL_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'final.done') -Encoding utf8
