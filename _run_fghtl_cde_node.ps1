# _run_fghtl_cde_node.ps1 -- P2 C/D/E with NODE-LEVEL SAT evidence + NODE-LEVEL losses
#   Cn = B(mode4+trust) + --extra-feats satrel_node              (9-dim core SAT features)
#   Dn = Cn + --eq-loss-node 0.1      (L_eq only on SAT-proved node pairs, kind=0)
#   En = Dn + --pair-loss-node 0.1    (L_pair on a4trojan-vs-control SAT pairs, kind=1)
#   9 runs = {Cn,Dn,En} x seed {42,1,2}, 100 ep, SEQUENTIAL (single 8GB GPU)
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI -> CJK literals break)
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy  = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$d15  = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4   = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log  = Join-Path $n4.FullName 'logs\fghtl_cde_node.log'
$flag = Join-Path $env:TEMP 'fghtl_cde_node.done'
if (Test-Path $flag) { Remove-Item $flag -Force }

function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $line -Encoding UTF8
  Write-Host $line
}

$fold   = Join-Path $root 'generate_trans\folds\hosts_bt31'
$common = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
            '--work-dir', $fold,
            '--fold-json', (Join-Path $fold 'views.json'),
            '--pt-dir', (Join-Path $fold 'data\processed'),
            '--config', (Join-Path $root '_devcfg\dual.yaml'),
            '--fold-mode', 'fold', '--epochs', '100', '--steps-per-epoch', '1',
            '--val-every', '5', '--view-policy', 'all', '--amp', '--resume',
            '--extra-feats', 'satrel_node', '--train-mode', '4', '--label-mask', 'trust')

function Wait-Ram {
  while (((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB) -lt 6) {
    Log '    [wait] free RAM < 6GB -> sleep 30s'; Start-Sleep -Seconds 30
  }
}

Log '=== FGHTL C/D/E (node-level, SAT-first) start ==='
foreach ($seed in 42,1,2) {
  foreach ($grp in @(
      @{n='Cn'; extra=@()},
      @{n='Dn'; extra=@('--eq-loss-node','0.1')},
      @{n='En'; extra=@('--eq-loss-node','0.1','--pair-loss-node','0.1','--pair-margin','0.5')})) {
    $tag = "fghtl_$($grp.n)s$seed"
    Wait-Ram
    Log ("--- $($grp.n) seed=$seed tag=$tag")
    $ex = @('--seed',"$seed",'--tag',$tag) + $grp.extra
    & $gpy @common @ex 2>&1 | Out-File -FilePath (Join-Path $env:TEMP "$tag.out") -Encoding UTF8
    Log ("    $($grp.n) seed=$seed rc=$LASTEXITCODE")
  }
}

'FGHTL_CDE_NODE_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== FGHTL C/D/E (node-level) done ==='
