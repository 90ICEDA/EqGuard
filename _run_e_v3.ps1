# _run_e_v3.ps1 -- after C_n v3, run E_n with label-conditioned kind1 (12,914 pairs).
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$wait = Join-Path $env:TEMP 'c_v3.done'
$log = Join-Path $root 'logs\e_v3.log'
$done = Join-Path $env:TEMP 'e_v3.done'
if (Test-Path $done) { Remove-Item $done -Force }
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(2)
while (-not (Test-Path $wait)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout waiting c_v3.done'; exit 1 }
  Start-Sleep -Seconds 20
}
while ((Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'train_test2.3' } | Measure-Object).Count -gt 0) {
  Start-Sleep -Seconds 10
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
  '--extra-node-file','satrel_node_feats_sat_p0clean3.npy',
  '--eq-loss-node','0.1','--pair-loss-node','0.1','--pair-margin','0.5',
  '--node-pair-cap','2048',
  '--node-pairs-file','satrel_node_pairs_labelclean_v2.npz'
)
Log '=== E_n v3: seed42/1/2 (kind1=12914) ==='
foreach ($seed in 42,1,2) {
  $tag = "fghtl_EncleanV3R$seed"
  Log ("--- {0}" -f $tag)
  $t0 = Get-Date
  & $gpy @common --seed $seed --tag $tag 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP ("ev3_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}
'E_V3_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== E_n v3 done ==='
