# _run_clean_validate_v2.ps1 -- rerun clean features after observable fix.
#   waits for clean_validate.done (current v1 queue)
#   builds satrel_node_feats_sat_p0clean2.npy  (old _p0clean files untouched)
#   clean C/D/E x seeds 42,1  (two seeds, as requested)
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$logdir = Join-Path $root 'logs'
if (-not (Test-Path $logdir)) { New-Item -ItemType Directory -Path $logdir | Out-Null }
$log = Join-Path $logdir 'clean_validate_v2.log'
$flag = Join-Path $env:TEMP 'clean_validate_v2.done'
$prev = Join-Path $env:TEMP 'clean_validate.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) {
  $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
function Wait-NoTrain {
  while ($true) {
    $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -match 'train_test2.3.py|make_clean_p0_feats' } |
             Measure-Object).Count -gt 0
    if (-not $busy) { return }
    Log '    [wait] training/feature writer still running -> sleep 30s'
    Start-Sleep -Seconds 30
  }
}
function Run-Gpu([string]$tag, [string[]]$argv) {
  Wait-NoTrain
  Log ("--- {0}" -f $tag)
  $t0 = Get-Date
  & $gpy @argv --tag $tag 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP ("clean2_{0}.out" -f $tag)) -Encoding UTF8
  $rc = $LASTEXITCODE
  $dt = [int]((Get-Date) - $t0).TotalMinutes
  Log ("    rc={0} elapsed={1}min" -f $rc, $dt)
  return $rc
}

Log '=== clean v2 queue: waiting for clean_validate.done ==='
$deadline = (Get-Date).AddHours(6)
while (-not (Test-Path $prev)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout 6h -> abort'; exit 1 }
  Start-Sleep -Seconds 60
}
Wait-NoTrain
Log 'v1 done; building p0clean2 (observable fixed)'

$p0csv = Join-Path $root '_p0pilot\functional_relations_agnostic.csv'
$feat = Join-Path $root 'generate_trans\folds\hosts_bt31\data\processed\satrel_node_feats_sat_p0clean2.npy'
$meta = Join-Path $root 'generate_trans\folds\hosts_bt31\data\processed\satrel_node_meta_sat_p0clean2.json'
if ((Test-Path $feat) -and (Test-Path $meta)) {
  Log 'p0clean2 already exists -> reuse it'
} else {
  & $py -X utf8 -u 'phase2\ys\make_clean_p0_feats_v2.py' --p0-csv $p0csv --tag-suffix '_p0clean2' 2>&1 |
    ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8; Write-Host $_ }
  if ($LASTEXITCODE -ne 0) { Log '[ABORT] p0clean2 build failed'; exit 1 }
}

if (Test-Path $meta) {
  $m = Get-Content $meta -Raw | ConvertFrom-Json
  Log ("    p0clean2: S={0} P={1} covered={2} S_trojan={3} obs_nonzero={4} core={5}" -f `
    $m.coverage_by_layer.'0_S', $m.coverage_by_layer.'1_P', $m.coverage_any_nodes, `
    $m.S_covered_of_trojan_named, $m.observable_nonzero, $m.core_dim)
  if ([int]$m.coverage_by_layer.'0_S' -le 0) { Log '[ABORT] S empty'; exit 1 }
  if ([int]$m.observable_nonzero -le 0) { Log '[ABORT] observable still empty'; exit 1 }
  if ([int]$m.core_dim -ne 12) { Log '[ABORT] expected 12-dim core'; exit 1 }
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
            '--extra-node-file', 'satrel_node_feats_sat_p0clean2.npy')

Log '=== smoke 2ep p0clean2 ==='
$rc = Run-Gpu 'clean2_probe4' ($common + @('--seed','42','--epochs','2'))
if ($rc -ne 0) { Log '[ABORT] p0clean2 smoke failed'; exit 1 }

foreach ($seed in 42,1) {
  Run-Gpu ("fghtl_CncleanV2{0}" -f $seed) ($common + @('--seed',"$seed")) | Out-Null
  Run-Gpu ("fghtl_DncleanV2{0}" -f $seed) ($common + @('--seed',"$seed",'--eq-loss-node','0.1','--node-pair-cap','2048')) | Out-Null
  Run-Gpu ("fghtl_EncleanV2{0}" -f $seed) ($common + @('--seed',"$seed",'--eq-loss-node','0.1','--pair-loss-node','0.1','--pair-margin','0.5','--node-pair-cap','2048')) | Out-Null
}

'CLEAN_VALIDATE_V2_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== clean v2 done ==='
