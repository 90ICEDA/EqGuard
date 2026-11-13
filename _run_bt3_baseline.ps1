# EquiGuard fold v3 GPU baseline: 3 seeds x 100 epochs (sequential)
# NOTE: --pt-dir is passed explicitly (default is <work-dir>/data/processed, but be explicit).
# NOTE: the pt build must have orig_view_map attached (process_pt2.py) or orig masks are empty
#       -> cross_entropy(empty) = NaN -> the run silently learns nothing (fixed 2026-10-17).
cd C:\Users\91344\Desktop\GraphSAINT\GIN_train
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
foreach ($s in 42, 1, 2) {
  Write-Output ("[start] seed=$s " + (Get-Date -Format s))
  & ginvenv_gpu\Scripts\python.exe -X utf8 -u train_test2.3.py --work-dir generate_trans/folds/hosts_bt3 --fold-json generate_trans/folds/hosts_bt3/views.json --pt-dir generate_trans/folds/hosts_bt3/data/processed --config config_bt3_gpu.yaml --fold-mode fold --epochs 100 --val-every 5 --view-policy random --view-budget 4 --amp --seed $s --tag ("bt3s" + $s) *> "$env:TEMP\bt3_s$s.log"
  Write-Output ("[done] seed=$s rc=$LASTEXITCODE " + (Get-Date -Format s))
}
Write-Output ALL_DONE
