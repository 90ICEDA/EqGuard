# 等 C4 的 λ 表**完整生成**（marker ✓）后，把 T09 追加/替换进 TABLES.md（幂等 ✓）。
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$c4md = Join-Path $root '10.15\03_特征与模型\C4_等价一致性\C4_lambda_table.md'
$done = Join-Path $env:TEMP 'c4table.done'
$tables = Join-Path $root '10.15\07_论文图表\TABLES.md'
$log = Join-Path $env:TEMP ('t09_' + (Get-Date -Format 'HHmmss') + '.log')

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while (-not ((Test-Path $done) -and (Test-Path $c4md))) {
  "[wait] done=$(Test-Path $done) c4md=$(Test-Path $c4md) $(Get-Date -Format HH:mm:ss)" |
    Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 60
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

# 去掉旧的 T09 段（若有 ✓），保证只保留最新一版 ✓
$lines = @(Get-Content $tables -Encoding UTF8)
$hit = $lines | Select-String -Pattern '^## T09' | Select-Object -First 1
if ($hit) {
  $keep = if ($hit.LineNumber -gt 1) { $lines[0..($hit.LineNumber - 2)] } else { @() }
  $keep | Out-File $tables -Encoding utf8
  "[replace] dropped old T09 at line $($hit.LineNumber)" | Out-File $log -Append -Encoding Unicode
}

"" | Out-File $tables -Append -Encoding utf8
"## T09 一致性权重 λ 消融（dev4，seed 42 ✓；来源 ``C4_lambda_table.csv`` ✓）" |
  Out-File $tables -Append -Encoding utf8
"" | Out-File $tables -Append -Encoding utf8
(Get-Content $c4md -Encoding UTF8 | Select-Object -Skip 1) | Out-File $tables -Append -Encoding utf8
"" | Out-File $tables -Append -Encoding utf8
"> 判读 ✓：λ 控制「仅功能分支一致性」的权重 ✓；λ=0 即完全不加一致性损失 ✓；func-only 为全表示一致性消融 ✓。" |
  Out-File $tables -Append -Encoding utf8
"[appended] T09 -> TABLES.md $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
"T09_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 't09.done') -Encoding utf8
