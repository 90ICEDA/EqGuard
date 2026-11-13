# _p0_lane.ps1 -- run label-agnostic combinational P0 for a list of hosts (one yosys at a time)
param([string]$hosts = 's38584t100')
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$tdir = Join-Path $root 'generate_trans\folds\hosts_bt31\trans'
foreach ($h in ($hosts -split ',')) {
  $h = $h.Trim()
  if (-not $h) { continue }
  $insts = @()
  foreach ($f in (Get-ChildItem $tdir -Filter "*_d1_s42__*.v")) {
    if ($f.BaseName -notmatch '^(?<h>[^_]+)__(?<i>.+?)_d1_s42__') { continue }
    if ($Matches['h'] -ne $h) { continue }
    $insts += $Matches['i']
  }
  $insts = $insts | Sort-Object -Unique
  if (-not $insts) { continue }
  $instArg = $insts -join ','
  $out = Join-Path $root ("_p0pilot\full_{0}.csv" -f $h)
  $ld = Join-Path $root ("_p0pilot\full_logs\{0}" -f $h)
  & $py -X utf8 -u 'phase2\ys\sat_functional_relations_agnostic.py' `
      --host $h --inst $instArg --recipes 'ys_id,ys_abc,ys_aig,ys_nand,ys_opt' `
      --max-cases 115 --gate-cases 80 --mux-cases 20 --comb-cases 10 --dff-cases 5 `
      --dff-order obs --timeout 8 --bmc-depths= --out $out --logdir $ld 2>&1 |
    Out-File -FilePath (Join-Path $root ("_p0pilot\lane_{0}.log" -f $h)) -Encoding UTF8
  "[{0}] {1} insts={2} rc={3}" -f (Get-Date -Format 'HH:mm'), $h, $insts.Count, $LASTEXITCODE |
    Tee-Object -FilePath (Join-Path $root '_p0pilot\lane_status.log') -Append
}
