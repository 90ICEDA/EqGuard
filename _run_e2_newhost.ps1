# E2 —— 新电路泛化：用**未参与训练的新实例** s38417t300（hosts_bt2 里只有 s38417t100 ✓）
# 重建一个 host：注入 → 4 项验证 → bnd 转换 + CEC → inst_prov 标记。
# 单进程串行 ✓；只在机器空闲时跑（RAM 需 ≥ 4 GB ✓）。
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$e2 = Join-Path $root 'generate_trans\hosts_e2'
$hostName = 's38417t300'
$log = Join-Path $env:TEMP 'e2.log'

"[step1] inject_trojan build $hostName" | Out-File $log -Encoding utf8
& $py -X utf8 -u (Join-Path $root 'phase2\inject_trojan.py') build --hosts $hostName --out-dir $e2 `
  --instances 6 --controls 8 --seed 42 *>> $log
"[step1] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding utf8

"[step2] inject_newfamily (injcmp / injflip)" | Out-File $log -Append -Encoding utf8
& $py -X utf8 -u (Join-Path $root 'phase2\ys\inject_newfamily.py') --hosts $hostName --out $e2 `
  --instances 8 --controls 10 --seed 42 *>> $log
"[step2] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding utf8

"[step3] verify_e1 (4 checks)" | Out-File $log -Append -Encoding utf8
& $py -X utf8 -u (Join-Path $root 'phase2\ys\verify_e1.py') --hosts-root $e2 `
  --golden-root (Join-Path $root 'generate_trans\hosts_bt2') `
  --out (Join-Path $root '10.15\05_木马家族扩展\E2_新电路\tables') *>> $log
"[step3] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding utf8

"[step4] keep=bnd 转换 + CEC" | Out-File $log -Append -Encoding utf8
& $py -X utf8 -u (Join-Path $root 'phase2\ys\keep_ablation.py') --hosts-root $e2 --host $hostName `
  --recipes abc,nand,aig --schemes bnd `
  --out (Join-Path $root 'generate_trans\keepab_e2') `
  --tables (Join-Path $root '10.15\05_木马家族扩展\E2_新电路\tables') *>> $log
"[step4] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding utf8

"E2_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'e2.done') -Encoding utf8
