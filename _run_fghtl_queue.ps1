# _run_fghtl_queue.ps1  (ASCII only, unattended, CPU-only)
# Queue: P1 patch steps (regions/roles) -> sweep extra hosts -> refresh figures/summaries -> commit
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP 'fghtl_queue.log'
$flag = Join-Path $env:TEMP 'fghtl_queue.done'
if (Test-Path $flag) { Remove-Item $flag -Force }

function Log($msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
  Add-Content -Path $log -Value $line -Encoding UTF8
  Write-Host $line
}

function Run($name, $argsList) {
  Log "== START $name"
  $p = & $py -X utf8 @argsList 2>&1
  $p | Out-File -FilePath $log -Append -Encoding UTF8
  Log ("== END   {0} rc={1}" -f $name, $LASTEXITCODE)
}

$hosts = @('rs232t1000','s38584t100','s15850t100','s35932t200','s38417t100')
$insts = @('injalpha','injepsilon')
$pairs = 'ys_id:ys_abc,ys_id:ys_opt,ys_abc:ys_opt'

Log '=== FGHTL queue start ==='

# 1) sweep for ALL hosts (adds cross-name pairs; additive, dedup by host/inst/pair/net_a,net_b)
foreach ($h in $hosts) {
  foreach ($i in $insts) {
    Run "sweep $h/$i" @('phase2\ys\sat_sweep_pairs.py','--host',$h,'--inst',$i,
                        '--pairs',$pairs,'--k','32','--cycles','8','--per-sig','2',
                        '--max-pairs','120')
  }
}

# 2) region correspondence (split/merge) + region-level roles (union of name+sweep edges)
Run 'p1 region/roles' @('phase2\ys\fghtl_p1_region_roles.py',
                        '--hosts', ($hosts -join ','), '--insts', ($insts -join ','),
                        '--pairs', $pairs)

# 3) refresh summaries + figures
Run 'node_pairs_summary' @('phase2\ys\make_node_pairs_summary.py')
Run 'sat_summary'        @('phase2\ys\make_sat_summary.py')
Run 'f7_region_fig'      @('phase2\ys\make_f7_region_fig2.py')

# 4) commit
git add -A | Out-Null
git commit -q -m 'queue(FGHTL): sweep all hosts + region split/merge typing + region-level roles + F7 refresh'
Log ("[git] rc={0} head={1}" -f $LASTEXITCODE, (git rev-parse --short HEAD))

'FGHTL_QUEUE_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== FGHTL queue done ==='
