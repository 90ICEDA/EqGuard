# _run_clean_validate.ps1 -- queue clean P0 features + validation training
#   1) wait for p0_agnostic.done
#   2) build satrel_node_feats_sat_p0clean.npy (new file, old files untouched)
#   3) 2-epoch smoke
#   4) clean C_n / D_n / E_n x seeds 42,1,2
#      tags: fghtl_Cnclean<seed>, fghtl_Dnclean<seed>, fghtl_Enclean<seed>
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$logdir = Join-Path $root 'logs'
if (-not (Test-Path $logdir)) { New-Item -ItemType Directory -Path $logdir | Out-Null }
$log = Join-Path $logdir 'clean_validate.log'
$flag = Join-Path $env:TEMP 'clean_validate.done'
$p0flag = Join-Path $env:TEMP 'p0_agnostic.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) {
  $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
function Wait-NoSat {
  while ($true) {
    $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -match 'sat_functional_relations|sat_node_pairs|satrel_node_feats|make_clean_p0_feats' } |
             Measure-Object).Count -gt 0
    if (-not $busy) { return }
    Log '    [wait] P0/feature writer still running -> sleep 60s'
    Start-Sleep -Seconds 60
  }
}
function Run-Gpu([string]$tag, [string[]]$argv) {
  Wait-NoSat
  Log ("--- {0}" -f $tag)
  $t0 = Get-Date
  & $gpy @argv --tag $tag 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP ("clean_{0}.out" -f $tag)) -Encoding UTF8
  $rc = $LASTEXITCODE
  $dt = [int]((Get-Date) - $t0).TotalMinutes
  Log ("    rc={0} elapsed={1}min" -f $rc, $dt)
  return $rc
}

Log '=== clean validation queue: waiting for p0_agnostic.done ==='
$deadline = (Get-Date).AddHours(16)
while (-not (Test-Path $p0flag)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout 16h -> abort'; exit 1 }
  Start-Sleep -Seconds 60
}
Wait-NoSat
Log 'P0 done; building clean features'

$p0csv = Join-Path $root '_p0pilot\functional_relations_agnostic.csv'
if (-not (Test-Path $p0csv)) {
  Log 'merged P0 CSV missing -> merge full_*.csv'
  & $py -X utf8 -c "import pandas as pd,glob; fs=glob.glob(r'_p0pilot/full_*.csv'); ds=[pd.read_csv(f,encoding='utf-8-sig') for f in fs]; d=pd.concat(ds,ignore_index=True).drop_duplicates(subset=['design','target'],keep='last'); d.to_csv(r'_p0pilot/functional_relations_agnostic.csv',index=False,encoding='utf-8-sig'); print('merged',len(d),'rows from',len(fs))" 2>&1 |
    ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8; Write-Host $_ }
}
if (-not (Test-Path $p0csv)) { Log '[ABORT] no merged P0 CSV'; exit 1 }

& $py -X utf8 -u 'phase2\ys\make_clean_p0_feats.py' --p0-csv $p0csv --tag-suffix '_p0clean' 2>&1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8; Write-Host $_ }
if ($LASTEXITCODE -ne 0) { Log '[ABORT] clean feature build failed'; exit 1 }

$meta = Join-Path $root 'generate_trans\folds\hosts_bt31\data\processed\satrel_node_meta_sat_p0clean.json'
if (Test-Path $meta) {
  $m = Get-Content $meta -Raw | ConvertFrom-Json
  Log ("    clean meta: S={0} P={1} covered={2} trojan_named={3} S_trojan={4}" -f `
    $m.coverage_by_layer.'0_S', $m.coverage_by_layer.'1_P', $m.coverage_any_nodes, `
    $m.trojan_named_nodes, $m.S_covered_of_trojan_named)
  if ([int]$m.coverage_by_layer.'0_S' -le 0) { Log '[ABORT] clean S layer is empty'; exit 1 }
}

$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$common = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
            '--work-dir', $fold,
            '--fold-json', (Join-Path $fold 'views.json'),
            '--pt-dir', (Join-Path $fold 'data\processed'),
            '--config', (Join-Path $root '_devcfg\dual.yaml'),
            '--fold-mode', 'fold', '--steps-per-epoch', '1', '--val-every', '5',
            '--view-policy', 'all', '--amp', '--resume', '--epochs', '100',
            '--train-mode', '4', '--label-mask', 'trust', '--save-ckpt',
            '--extra-feats', 'satrel_node',
            '--extra-node-file', 'satrel_node_feats_sat_p0clean.npy')

Log '=== smoke 2ep clean features ==='
$rc = Run-Gpu 'clean_probe4' ($common + @('--seed','42','--epochs','2'))
if ($rc -ne 0) { Log '[ABORT] clean smoke failed'; exit 1 }

foreach ($seed in 42,1,2) {
  $rc = Run-Gpu ("fghtl_Cnclean{0}" -f $seed) ($common + @('--seed',"$seed"))
  if ($rc -ne 0) { Log ("    [warn] C_n seed {0} failed" -f $seed) }
  $rc = Run-Gpu ("fghtl_Dnclean{0}" -f $seed) ($common + @('--seed',"$seed",'--eq-loss-node','0.1','--node-pair-cap','2048'))
  if ($rc -ne 0) { Log ("    [warn] D_n seed {0} failed" -f $seed) }
  $rc = Run-Gpu ("fghtl_Enclean{0}" -f $seed) ($common + @('--seed',"$seed",'--eq-loss-node','0.1','--pair-loss-node','0.1','--pair-margin','0.5','--node-pair-cap','2048'))
  if ($rc -ne 0) { Log ("    [warn] E_n seed {0} failed" -f $seed) }
}

Log '--- refresh fg_htl_ablation.csv ---'
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8; Write-Host $_ }

'CLEAN_VALIDATE_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== clean validation done ==='
