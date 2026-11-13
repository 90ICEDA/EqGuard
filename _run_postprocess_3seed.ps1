# 3-seed 自动接管：等 v3.1 三个 seed 的 npz 齐 → 主表 → 区域级 → G10/G03/G05 → 报告。
# 与训练**串行触发** ✓（靠锁文件判断 ✓），本身纯 CPU ✓。
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$lock = Join-Path $root '_devcfg\.v31_train.lock'
$need = @('gnn_v31_s42.npz', 'gnn_v31_s1.npz', 'gnn_v31_s2.npz') |
        ForEach-Object { Join-Path $root ('_devcfg\' + $_) }
$log = Join-Path $env:TEMP ('postprocess_' + (Get-Date -Format 'HHmmss') + '.log')
$done = Join-Path $env:TEMP 'postprocess.done'

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while ($true) {
  $missing = $need | Where-Object { -not (Test-Path $_) }
  if (-not $missing -and -not (Test-Path $lock)) { break }
  "[wait] missing=$($missing.Count) lock=$(Test-Path $lock) $(Get-Date -Format HH:mm:ss)" |
    Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 120
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

# 1) 3-seed 主表（节点级口径 ✓）
& $py -X utf8 -u (Join-Path $root 'phase2\ys\summarize_npz.py') `
  --pt (Join-Path $fold 'data\processed\trans_graph.pt') --npz $need `
  --out (Join-Path $root '_devcfg\v31_3seed_summary.csv') *>> $log
"[1] summarize rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

# 2) 区域级（node / DFF 锥 / PO 锥 / view ✓ 每 seed 一行 ✓）
$regdir = Join-Path $root '_devcfg\region_seeds'
& $py -X utf8 -u (Join-Path $root 'phase2\ys\region_eval_seeds.py') `
  --pt (Join-Path $fold 'data\processed\trans_graph.pt') --npz $need `
  --out-dir $regdir *>> $log
"[2] region rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

# 3) G10（多种子误差棒 ✓）
& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_g10_seedbars.py') `
  --pt (Join-Path $fold 'data\processed\trans_graph.pt') `
  --series 'EquiGuard_v31=_devcfg/gnn_v31_s*.npz' `
  --out (Join-Path $root '10.15\07_论文图表\G10_seed_bars_v31.png') `
  --csv (Join-Path $root '10.15\07_论文图表\tables\G10_seed_bars_v31.csv') *>> $log
"[3] g10 rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

# 4) G03 / G05（误差棒版 ✓）
& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_g03_g05_3seed.py') `
  --region-csv (Join-Path $regdir 'region_seeds.csv') *>> $log
"[4] g03g05 rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

# 5) 报告（数字全部来自 CSV ✓，不手填 ✓）
$rep = Join-Path $root '10.15\07_论文图表\3seed_report.md'
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# 3-seed 主表与图表（自动生成 ✓）'); $lines.Add('')
$lines.Add(('生成时间：' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ✓')); $lines.Add('')
$lines.Add('## 1. 节点级（逐视图均值 ✓ + pooled ⚠️ 仅供参考）'); $lines.Add('')
$lines.Add('| npz | view_AP | view_AUC | R@1% | R@5% | pooled_AP | pooled_AUC |')
$lines.Add('|---|---|---|---|---|---|---|')
if (Test-Path (Join-Path $root '_devcfg\v31_3seed_summary.csv')) {
  foreach ($r in (Import-Csv (Join-Path $root '_devcfg\v31_3seed_summary.csv'))) {
    $lines.Add(('| {0} | {1} | {2} | {3} | {4} | {5} | {6} |' -f $r.npz,
      [math]::Round([double]$r.view_ap,4), [math]::Round([double]$r.view_auc,4),
      [math]::Round([double]$r.r1,4), [math]::Round([double]$r.r5,4),
      [math]::Round([double]$r.pooled_ap,4), [math]::Round([double]$r.pooled_auc,4)))
  }
}
$lines.Add('')
$lines.Add('## 2. 区域级（每 seed ✓，mean ± std 见 region_seeds_mean.csv）'); $lines.Add('')
if (Test-Path (Join-Path $regdir 'region_seeds.csv')) {
  $lines.Add('| seed | node view_AP | DFF cone | PO cone | whole view |')
  $lines.Add('|---|---|---|---|---|')
  foreach ($r in (Import-Csv (Join-Path $regdir 'region_seeds.csv'))) {
    $lines.Add(('| {0} | {1} | {2} | {3} | {4} |' -f $r.seed,
      [math]::Round([double]$r.view_ap,4), [math]::Round([double]$r.dff_view_ap,4),
      [math]::Round([double]$r.po_cone_view_ap,4), [math]::Round([double]$r.view_view_ap,4)))
  }
  $lines.Add('')
  $lines.Add('### mean ± std')
  $lines.Add('| metric | mean | std | n |')
  $lines.Add('|---|---|---|---|')
  foreach ($r in (Import-Csv (Join-Path $regdir 'region_seeds_mean.csv'))) {
    $lines.Add(('| {0} | {1} | {2} | {3} |' -f $r.metric,
      [math]::Round([double]$r.mean,4), [math]::Round([double]$r.std,4), $r.n))
  }
}
$lines.Add('')
$lines.Add('## 3. 图'); $lines.Add('')
$lines.Add('- `G10_seed_bars_v31.png`（v3.1，3 seed ✓）')
$lines.Add('- `G03_granularity_3seed.png`（四粒度 + 误差棒 ✓）')
$lines.Add('- `G05_main_3seed.png`（(a) dev4 消融链 n=1 ⚠️｜(b) v3.1 基线 n=3 ✓）')
$lines.Add('')
$lines.Add('> 口径提醒 ✓：dev4 的 G0/G1/C2 **每个只有 1 个 seed** ✗ → 该面板不画误差棒 ✗；')
$lines.Add('> 若需要 3-seed 的主对比，必须补跑 G0/G1/C2 的 seed 1/2（6 次 × ~25 min ✗）。')
$lines | Out-File $rep -Encoding utf8
"[5] report -> $rep" | Out-File $log -Append -Encoding Unicode

"POSTPROCESS_DONE $(Get-Date -Format s)" | Out-File $done -Encoding utf8
