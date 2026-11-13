# C4 自动接管：等 5 个 dev4 消融 npz 齐（λ=0/0.3/1/3 + func-only ✓）且无训练进程 → 出 λ 表。
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$need = @('dev4_lc0.npz', 'dev4_lc0p3.npz', 'dev4_lc1.npz', 'dev4_lc3.npz', 'dev4_funconly.npz') |
        ForEach-Object { Join-Path $root ('_devcfg\' + $_) }
$log = Join-Path $env:TEMP ('c4table_' + (Get-Date -Format 'HHmmss') + '.log')

"[wait] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
while ($true) {
  $missing = $need | Where-Object { -not (Test-Path $_) }
  $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -like '*train_test2.3.py*' }).Count
  if (-not $missing -and $busy -eq 0) { break }
  "[wait] missing=$($missing.Count) busy=$busy $(Get-Date -Format HH:mm:ss)" |
    Out-File $log -Append -Encoding Unicode
  Start-Sleep -Seconds 90
}
"[go] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_c4_lambda_table.py') *>> $log
"[c4] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

"# C4 汇总（自动追加 ✓）`n" | Out-File (Join-Path $root '10.15\03_特征与模型\C4_等价一致性\说明.md') -Append -Encoding utf8
Get-Content (Join-Path $root '10.15\03_特征与模型\C4_等价一致性\C4_lambda_table.md') -Encoding UTF8 |
  Out-File (Join-Path $root '10.15\03_特征与模型\C4_等价一致性\说明.md') -Append -Encoding utf8

"C4_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'c4table.done') -Encoding utf8
