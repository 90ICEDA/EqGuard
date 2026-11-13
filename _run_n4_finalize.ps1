# N4 收尾 ✓：等 N4（LOCO/LRO ✓）跑完 → **T13 表** ✓ → 追加进 TABLES.md ✓ → 提交
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('t13_' + (Get-Date -Format 'HHmmss') + '.log')

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while (-not (Test-Path (Join-Path $env:TEMP 'n4.done'))) {
  "[wait] n4 not done $(Get-Date -Format HH:mm:ss)" | Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 120
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_t13_table.py') `
  --series 'A0 single=_devcfg/gnn_v31a_A0_s*.npz' `
  --series 'A1 +trust=_devcfg/gnn_v31a_A1_s*.npz' `
  --series 'A2 dual+trust=_devcfg/gnn_v31a_A2_s*.npz' `
  --series 'A3 +cone5 (base)=_devcfg/gnn_v31_s*.npz' `
  --series 'A5 +region l10=_devcfg/gnn_v31r_l100_s*.npz' *>> $log
"[t13] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

# 追加 T13 到 TABLES.md（幂等 ✓）
$md = Join-Path $root '10.15\03_特征与模型\N2_双分支复核\t13.md'
$tables = Join-Path $root '10.15\07_论文图表\TABLES.md'
if (Test-Path $md) {
  $cur = Get-Content $tables -Raw -Encoding UTF8
  if ($cur -notmatch '## T13') {
    "" | Out-File $tables -Append -Encoding utf8
    (Get-Content $md -Encoding UTF8 | Select-Object -Skip 1) | Out-File $tables -Append -Encoding utf8
    "[t13] appended to TABLES.md" | Out-File $log -Append -Encoding Unicode
  }
}

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N2): T13 3-seed ablation (A0/A1/A2/A3/A5) with cone-level AP; N6 supplement (trust/cone5 fold-dependent)' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
"T13_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 't13.done') -Encoding utf8
