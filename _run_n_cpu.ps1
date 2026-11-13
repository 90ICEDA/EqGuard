# CPU 阶段 ✓：等 N3+N2 训练结束（marker ✓）→ 解释性指标 → N1 对照诊断 → N5 图 → 复现索引 → 提交
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('ncpu_' + (Get-Date -Format 'HHmmss') + '.log')

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while (-not (Test-Path (Join-Path $env:TEMP 'n3n2.done'))) {
  "[wait] n3n2 not done $(Get-Date -Format HH:mm:ss)" | Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 120
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

# 1) 解释性指标（head_fp / tail_pos）✓
$npzAll = @()
foreach ($pat in @('gnn_v31_s42.npz', 'gnn_v31_s1.npz', 'gnn_v31_s2.npz',
                   'gnn_v31r_l100_s42.npz', 'gnn_v31r_l100_s1.npz', 'gnn_v31r_l100_s2.npz',
                   'gnn_v31r_l05_s42.npz', 'gnn_v31r_l10_s42.npz', 'gnn_v31r_l50_s42.npz',
                   'gnn_v31r_l50_s1.npz', 'gnn_v31r_l50_s2.npz')) {
  $p = Join-Path $root ('_devcfg\' + $pat)
  if (Test-Path $p) { $npzAll += $p }
}
& $py -X utf8 -u (Join-Path $root 'phase2\ys\diag_head_fp.py') --npz $npzAll `
  --out (Join-Path $root '10.15\03_特征与模型\C6_区域级监督\tables\head_fp.csv') *>> $log
"[1] head_fp rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

# 2) N1：木马 vs 匹配对照诊断（基线 + 区域监督）✓
& $py -X utf8 -u (Join-Path $root 'phase2\ys\a4_pair_diag.py') `
  --npz (Join-Path $root '_devcfg\gnn_v31_s42.npz') (Join-Path $root '_devcfg\gnn_v31r_l100_s42.npz') *>> $log
"[2] n1 rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

# 3) N5：图 F1/F3/F4/F5 ✓
& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n5_figs.py') *>> $log
"[3] figs rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

# 4) 复现索引 ✓
& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_repro_index.py') *>> $log
"[4] repro rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N1/N3/N5): head_fp diagnostics, trojan-vs-matched-control analysis, F1/F3/F4/F5 figures, repro index' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
"NCPU_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'ncpu.done') -Encoding utf8
