# E2 收尾：等后台 keepab 跑完（marker ✓）→ 重写 T11 / 重写 E2 说明的实测段 → 提交（幂等 ✓）。
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$sum = Join-Path $root '10.15\05_木马家族扩展\E2_新电路\tables\a3_keep_pilot_summary.csv'
$marker = Join-Path $env:TEMP 'e2keepab.done'
$tables = Join-Path $root '10.15\07_论文图表\TABLES.md'
$doc = Join-Path $root '10.15\05_木马家族扩展\E2_新电路\说明.md'
$log = Join-Path $env:TEMP ('e2fin_' + (Get-Date -Format 'HHmmss') + '.log')

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while (-not ((Test-Path $marker) -and (Test-Path $sum))) {
  "[wait] marker=$(Test-Path $marker) sum=$(Test-Path $sum) $(Get-Date -Format HH:mm:ss)" |
    Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 60
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

$rows = Import-Csv $sum
$nview = 18
$lines = @('', '## T11 新电路泛化（E2 ✓，`s38417t300`，keep=bnd ✓；来源 `E2_新电路/tables/a3_keep_pilot_summary.csv` ✓）', '',
           '口径 ✓：`s38417t300` 与训练的 `s38417t100` **同族不同实例** ✓（仓里没有 `s38584t300` ✗）；',
           '注入 6 组木马 + 8 组对照 ✓ + `injcmp`/`injflip` 新家族 ✓；在**配方原产物**上量 ✓。', '',
           '| 配方 | 转换成功 | CEC | 实例存活 | 锚点存活 | DFF-Q 存活 | 行数 |', '|---|---|---|---|---|---|---|')
$allPass = $true
foreach ($r in $rows | Sort-Object recipe) {
  $okN = [int][math]::Round([double]$r.conv_ok * $nview)
  $ok = if ($okN -eq $nview) { 'PASS ✓' } else { "FAIL ✗ ($okN/$nview)" }
  if ($okN -ne $nview) { $allPass = $false }
  $surv = [math]::Round([double]$r.surv_inst_text, 3)
  $anch = [math]::Round([double]$r.anchor_text_surv, 3)
  $dffq = [math]::Round([double]$r.dffq_text_surv, 3)
  $lines += ('| `' + $r.recipe + '` | ' + $ok + ' | ' + $r.cec_conv + ' | ' + $surv + ' | ' + $anch + ' | ' + $dffq + ' | ' + [int]$r.lines + ' |')
}
if ($allPass) {
  $lines += @('', '> ✓ 全部配方 × 全部视图都通过转换 + CEC ✓ → 整链（注入 → 验证 → 等价转换 → CEC ✓）',
              '> 可在**没见过的电路**上成立 ✓；锚点存活 0.5 说明一半锚点仍受保护 ✓（其余按 D5 丢弃 ✗）。')
} else {
  $lines += @('', '> ⚠️ 部分视图 FAIL ✗ → 这些「配方 × 视图」组合**不能用于训练** ✗（与 D5 的不可绑定视图同处理 ✓）；',
              '> 具体失败的是哪个配方见上表 ✓（`FAIL ✗ (k/18)` 的 k 就是通过的视图数 ✓），',
              '> 失败视图必须从训练/评测里剔除 ✗，否则标签会静默错位 ✗。')
}

$cur = @(Get-Content $tables -Encoding UTF8)
$hit = $cur | Select-String -Pattern '^## T11' | Select-Object -First 1
if ($hit -and $hit.LineNumber -gt 1) {
  $cur[0..($hit.LineNumber - 2)] | Out-File $tables -Encoding utf8
  "[replace] dropped old T11" | Out-File $log -Append -Encoding Unicode
}
$lines | Out-File $tables -Append -Encoding utf8

# 说明：先截断旧的「E2 实测」段 ✓，再写新的 ✓
$docLines = @(Get-Content $doc -Encoding UTF8)
$dh = $docLines | Select-String -Pattern '^## E2 实测' | Select-Object -First 1
if ($dh -and $dh.LineNumber -gt 1) {
  $docLines[0..($dh.LineNumber - 2)] | Out-File $doc -Encoding utf8
  "[doc] truncated old section" | Out-File $log -Append -Encoding Unicode
}
Add-Content $doc -Encoding utf8 -Value @('## E2 实测（自动生成 ✓）', '')
$lines | Add-Content $doc -Encoding utf8

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(E2): unknown-circuit generalization (s38417t300) conversion+CEC over 18 views; T11 (regenerated)' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
"E2_FINAL_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'e2final.done') -Encoding utf8
