# D2 —— 5 个未知 ABC 配方（keep=bnd 固定），每个配方沿用 D1 的 2 view × 2 scheme 口径。
# 只在机器空闲时跑（单进程串行 ✓，避免 RAM 紧张 ✗）。
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'

$recipes = [ordered]@{
  's1_fraig'  = '+strash;ifraig;scorr;dc2;dretime;strash;&get,-n;&dch,-f;&nf;&put'
  's2_dc2'    = '+strash;balance;resub;dc2;'
  's3_compress' = '+strash;compress2rs;'
  's4_dch'    = '+strash;&get,-n;&dch,-f;&nf;&put'
  's5_if'     = '+strash;if;mfs2;'
}

foreach ($k in $recipes.Keys) {
  $out = Join-Path $root ("generate_trans\keepab_" + $k)
  $tab = Join-Path $root ("10.15\04_ABC_AIG专项\D2_新abc配置\tables\" + $k)
  "[start] $k" | Out-File (Join-Path $env:TEMP "d2_$k.log") -Encoding utf8
  & $py -X utf8 -u (Join-Path $root 'phase2\ys\keep_ablation.py') `
    --hosts-root (Join-Path $root 'generate_trans\hosts_bt2') `
    --host rs232t1000 `
    --views 'rs232t1000__injalpha_d1_s42,rs232t1000__ctlmatcha_d1_s42' `
    --recipes abc --schemes bnd --abc-script $recipes[$k] `
    --out $out --tables $tab *>> (Join-Path $env:TEMP "d2_$k.log")
  "[done] $k rc=$LASTEXITCODE" | Out-File (Join-Path $env:TEMP "d2_$k.log") -Append -Encoding utf8
}
"D2_DONE" | Out-File (Join-Path $env:TEMP 'd2.done') -Encoding utf8
