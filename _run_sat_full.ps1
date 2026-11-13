# _run_sat_full.ps1  -- SAT 全网表批次（76 组 = 389 个 .v 全覆盖，含 ctl*/a4*）
$root = $PSScriptRoot
Set-Location $root
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$out = Join-Path $root '10.15\06_统一评测协议\N4_三向泛化\logs\batch_stdout.log'
& $py -X utf8 -u 'phase2\ys\sat_full_batch.py' --sleep 2 *>> $out
'rc=' + $LASTEXITCODE | Add-Content -Path $out -Encoding UTF8
