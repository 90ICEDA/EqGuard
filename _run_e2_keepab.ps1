# E2 第二步：在后台串行跑 18 视图 × 3 配方（abc/nand/aig，keep=bnd ✓），带 CEC ✓。
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('e2keepab_' + (Get-Date -Format 'HHmmss') + '.log')

$vs = (Get-ChildItem 'generate_trans\hosts_e2\s38417t300' -Filter '*.v' | ForEach-Object { $_.BaseName }) -join ','
"[start] views=$(($vs -split ',').Count) $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
& $py -X utf8 -u (Join-Path $root 'phase2\ys\keep_ablation.py') `
  --hosts-root (Join-Path $root 'generate_trans\hosts_e2') --host s38417t300 `
  --views $vs --recipes abc,nand,aig --schemes bnd --measure-raw `
  --out (Join-Path $root 'generate_trans\keepab_e2') `
  --tables (Join-Path $root '10.15\05_木马家族扩展\E2_新电路\tables') *>> $log
"[exit] rc=$LASTEXITCODE $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
"E2_KEEPAB_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'e2keepab.done') -Encoding utf8
