# _run_leak_ablation.ps1 -- after the main queue: run C_n ablations removing leaky feature groups
#   -noregion : zero region_edges (the Trojan-name-derived feature)
#   -nocovprov: zero proved_cnt / proved_ratio / covered
#   -funconly : keep only functional [0..3]
#   Writes only new npz files + new result dirs; does NOT touch the main features.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\leak_ablation.log'
$flag = Join-Path $env:TEMP 'leak_ablation.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

Log '=== leak ablation: waiting for gpu_final2.done ==='
$dl = (Get-Date).AddHours(12)
while (-not (Test-Path (Join-Path $env:TEMP 'gpu_final2.done'))) {
  if ((Get-Date) -gt $dl) { Log 'timeout 12h -> abort'; exit 1 }
  Start-Sleep -Seconds 60
}
while ($true) {
  $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -match 'train_test2.3.py' } | Measure-Object).Count -gt 0
  if (-not $busy) { break }
  Start-Sleep -Seconds 30
}
Log 'main queue done'

& $py -X utf8 -u 'phase2\ys\make_leak_ablation_feats.py' 2>&1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8; Write-Host $_ }

$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$common = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
            '--work-dir', $fold,
            '--fold-json', (Join-Path $fold 'views.json'),
            '--pt-dir', (Join-Path $fold 'data\processed'),
            '--config', (Join-Path $root '_devcfg\dual.yaml'),
            '--fold-mode', 'fold', '--steps-per-epoch', '1', '--val-every', '5',
            '--view-policy', 'all', '--amp', '--resume', '--epochs', '100',
            '--train-mode', '4', '--label-mask', 'trust', '--save-ckpt',
            '--seed', '42', '--extra-feats', 'satrel_node')

$runs = @(
  @('fghtl_Cnlk_noregion42',  'satrel_node_feats_sat_noregion.npy'),
  @('fghtl_Cnlk_nocovprov42', 'satrel_node_feats_sat_nocovprov.npy'),
  @('fghtl_Cnlk_funconly42',  'satrel_node_feats_sat_funconly.npy')
)
foreach ($r in $runs) {
  $tag = $r[0]; $nf = $r[1]
  Log ("--- {0} (extra-node-file={1})" -f $tag, $nf)
  $t0 = Get-Date
  & $gpy @common --tag $tag --extra-node-file $nf 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP ("leak_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}

'LEAK_ABLATION_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== leak ablation done ==='
