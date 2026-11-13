# N1.4+ ✓：等 F2 基础图出完（n1fig.done ✓）→ 导出实例名（node_idx → name ✓）→ 重画带名字的样例图 → 提交
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('n1names_' + (Get-Date -Format 'HHmmss') + '.log')

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while (-not (Test-Path (Join-Path $env:TEMP 'n1fig.done'))) {
  "[wait] n1fig not done $(Get-Date -Format HH:mm:ss)" | Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 120
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

& $py -X utf8 -u (Join-Path $root 'phase2\ys\export_node_names.py') `
  --fold (Join-Path $root 'generate_trans\folds\hosts_bt31') --split test *>> $log
"[1] export rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

$names = Join-Path $root '10.15\99_共用资产\node_names\hosts_bt31_test.json.gz'
foreach ($pair in @(@{npz='_devcfg\gnn_v31_s42.npz'; tag='named'},
                    @{npz='_devcfg\gnn_v31r_l100_s42.npz'; tag='named_region'})) {
  $p = Join-Path $root $pair.npz
  if (-not (Test-Path $p)) { continue }
  "[run] $($pair.tag)" | Out-File $log -Append -Encoding Unicode
  & $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n1_case_figs.py') --npz $p --tag $pair.tag --names $names *>> $log
  "[done] $($pair.tag) rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode
}

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N1.4): export node names (positional, gate-type validated) and draw named case figures' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
"N1NAMES_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'n1names.done') -Encoding utf8
