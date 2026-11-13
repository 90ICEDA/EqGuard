# _run_c_v3.ps1 -- C_n v3: 10-dim functional core + is_S/is_P + covered; seeds 42/1/2 (+SW42).
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\c_v3.log'
$done = Join-Path $env:TEMP 'c_v3.done'
if (Test-Path $done) { Remove-Item $done -Force }
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$common = @(
  '-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
  '--work-dir', $fold,
  '--fold-json', (Join-Path $fold 'views.json'),
  '--pt-dir', (Join-Path $fold 'data\processed'),
  '--config', (Join-Path $root '_devcfg\dual.yaml'),
  '--fold-mode','fold','--steps-per-epoch','1','--val-every','5',
  '--view-policy','all','--amp','--resume','--epochs','100',
  '--train-mode','4','--label-mask','trust','--save-ckpt',
  '--extra-feats','satrel_node',
  '--extra-node-file','satrel_node_feats_sat_p0clean3.npy'
)
function Run-One([string]$tag, [string]$seed, [string]$file) {
  Log ("--- {0} (seed {1}, {2})" -f $tag, $seed, $file)
  $argv = $common.Clone()
  # replace feature file if needed
  for ($i=0; $i -lt $argv.Count; $i++) { if ($argv[$i] -eq 'satrel_node_feats_sat_p0clean3.npy') { $argv[$i] = $file } }
  $t0 = Get-Date
  & $gpy @argv --seed $seed --tag $tag 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP ("cv3_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}
Log '=== C_n v3: seed42/1/2 + SW42 ==='
Run-One 'fghtl_CncleanV3R42' '42' 'satrel_node_feats_sat_p0clean3.npy'
Run-One 'fghtl_CncleanV3R1'  '1'  'satrel_node_feats_sat_p0clean3.npy'
Run-One 'fghtl_CncleanV3R2'  '2'  'satrel_node_feats_sat_p0clean3.npy'
Run-One 'fghtl_CncleanV3SW42' '42' 'satrel_node_feats_sat_p0clean3_sw.npy'
'C_V3_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== C_n v3 done ==='
