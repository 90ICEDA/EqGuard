# Build fold v3.1 graphs (parser2 + process_pt2) then run the 3-seed baseline.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log = Join-Path $env:TEMP ("v31_base_" + (Get-Date -Format 'HHmmss') + ".log")

Push-Location $fold
& $py -X utf8 -u (Join-Path $root 'data\verilog_data\parser2.py') --out-root ./data/for_train --skip-debug --cycle-mode contract --prov-root (Join-Path $root 'generate_trans\hosts_bt2'),(Join-Path $root 'generate_trans\hosts_a4') *>> $log
"[parser2] rc=$LASTEXITCODE" | Out-File -FilePath $log -Encoding utf8 -Append
Pop-Location

& $py -X utf8 -u (Join-Path $root 'process_pt2.py') --work-dir $fold --fold-json (Join-Path $fold 'views.json') --matrix-root $fold --trans-label transported *>> $log
"[process_pt2] rc=$LASTEXITCODE" | Out-File -FilePath $log -Encoding utf8 -Append

# trust mask for B1 ✓
& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_trust_mask.py') --work-dir $fold *>> $log
Get-ChildItem (Join-Path $fold 'data\for_train') -Filter 'trust_*.npy' | ForEach-Object { Copy-Item $_.FullName (Join-Path $fold 'data\processed') -Force }

foreach ($s in 42, 1, 2) {
  "[start] seed=$s $(Get-Date -Format s)" | Out-File -FilePath $log -Encoding utf8 -Append
  & $gpy -X utf8 -u (Join-Path $root 'train_test2.3.py') --work-dir $fold --fold-json (Join-Path $fold 'views.json') --pt-dir (Join-Path $fold 'data\processed') --config (Join-Path $root '_devcfg\dual.yaml') --fold-mode fold --epochs 100 --steps-per-epoch 1 --val-every 5 --view-policy all --amp --seed $s --extra-feats cone5 --func-const --label-mask trust --dump-scores (Join-Path $root "_devcfg\gnn_v31_s$s.npz") --tag ("v31s" + $s) *>> $log
  "[done] seed=$s rc=$LASTEXITCODE $(Get-Date -Format s)" | Out-File -FilePath $log -Encoding utf8 -Append
}
"DONE $(Get-Date -Format s)" | Out-File -FilePath $log -Encoding utf8 -Append
