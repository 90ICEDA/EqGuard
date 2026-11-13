# N1.4 电路图 ✓：等 CPU 阶段（ncpu.done ✓）结束 → 出 F2 样例图（基线 + 区域监督）→ 提交
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('n1fig_' + (Get-Date -Format 'HHmmss') + '.log')

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while (-not (Test-Path (Join-Path $env:TEMP 'ncpu.done'))) {
  "[wait] ncpu not done $(Get-Date -Format HH:mm:ss)" | Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 120
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

foreach ($pair in @(@{npz='_devcfg\gnn_v31_s42.npz'; tag='base'},
                    @{npz='_devcfg\gnn_v31r_l100_s42.npz'; tag='region'})) {
  $p = Join-Path $root $pair.npz
  if (-not (Test-Path $p)) { "[skip] 缺 $($pair.npz)" | Out-File $log -Append -Encoding Unicode; continue }
  "[run] $($pair.tag)" | Out-File $log -Append -Encoding Unicode
  & $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n1_case_figs.py') --npz $p --tag $pair.tag *>> $log
  "[done] $($pair.tag) rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode
}

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N1.4): case circuit figures with node risk scores (F2, base + region)' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
"N1FIG_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'n1fig.done') -Encoding utf8
