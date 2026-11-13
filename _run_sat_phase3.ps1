# _run_sat_phase3.ps1 -- C+ (per_sig=0/K64) -> a4 deep -> ctl 2 pairs -> rebuild
#   waits for sat_deep2.done (avoids two writers on the same CSV)
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI)
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\sat_phase3.log'
$flag = Join-Path $env:TEMP 'sat_phase3.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

$tdir = Join-Path $root 'generate_trans\folds\hosts_bt31\trans'

# ---------- wait for deep2 AND for any other node-pair writer to exit ----------
Log '=== phase3 start: waiting for sat_deep2.done (and no other writer) ==='
$dl = (Get-Date).AddHours(3)
while ($true) {
  $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -match 'sat_node_pairs_batch' } | Measure-Object).Count -gt 0
  $done = Test-Path (Join-Path $env:TEMP 'sat_deep2.done')
  if ($done -and -not $busy) { Log 'deep2 done + no writer -> start phase3'; break }
  if ((Get-Date) -gt $dl) { Log 'wait timeout 3h -> start anyway (RISK: concurrent writer!)'; break }
  Start-Sleep -Seconds 60
}

function Run-One([string]$tag, [string[]]$argv) {
  & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' @argv 2>&1 |
    Out-File -FilePath (Join-Path $n4.FullName ("logs\p3_{0}.log" -f $tag)) -Encoding UTF8
  return $LASTEXITCODE
}

# ---------- C+ : ABC 家族对 + per_sig=0 + K=64/cycles=16 + simple ----------
Log '=== C+ : abc:aig/abc:nand/opt:aig/opt:nand | per_sig=0 K=64 cyc=16 simple ==='
$specs = @()
foreach ($f in (Get-ChildItem $tdir -Filter '*_d1_s42__*.v')) {
  if ($f.BaseName -notmatch '^(?<h>[^_]+)__(?<i>.+?)_d1_s42__') { continue }
  $h = $Matches['h']; $i = $Matches['i']
  if ($i -like 'inj*') { $specs += ,@($h, $i) }
}
$specs = $specs | Sort-Object { $_[0] }, { $_[1] } -Unique
Log ("C+ specs = {0}" -f $specs.Count)
$i = 0
foreach ($s in $specs) {
  $i++
  $tag = "Cp_{0}_{1}" -f $s[0], $s[1]
  $rc = Run-One $tag @('--host',$s[0],'--inst',$s[1],
      '--pairs','ys_abc:ys_aig,ys_abc:ys_nand,ys_opt:ys_aig,ys_opt:ys_nand',
      '--anchor','all','--budget','0','--per-sig','0','--k','64','--cycles','16',
      '--prove-mode','simple','--batch','200','--timeout','300','--workers','6',
      '--skip-covered','--force')
  Log ("  [C+ {0}/{1}] {2}|{3} rc={4}" -f $i, $specs.Count, $s[0], $s[1], $rc)
}

# ---------- D+ : id 视图用**同名候选**（实测池 +40~50%，B05 口径命中 ~47%） ----------
Log '=== D+ : id:abc/id:opt | cand=name(no sig check) budget 3000 ==='
$i = 0
foreach ($s in $specs) {
  $i++
  $tag = "Dp_{0}_{1}" -f $s[0], $s[1]
  $rc = Run-One $tag @('--host',$s[0],'--inst',$s[1],
      '--pairs','ys_id:ys_abc,ys_id:ys_opt','--anchor','all','--budget','3000',
      '--cand','name','--name-sig','off','--prove-mode','simple','--batch','200',
      '--timeout','300','--workers','6','--skip-covered','--force')
  Log ("  [D+ {0}/{1}] {2}|{3} rc={4}" -f $i, $specs.Count, $s[0], $s[1], $rc)
}

# ---------- a4 deep : same-instance cross-recipe + cross-instance ----------
Log '=== a4 deep : same-instance (abc:id/abc:opt) + cross-instance (trojan vs ctl) ==='
$a4 = @()
foreach ($f in (Get-ChildItem $tdir -Filter '*__a4*_d1_s42__*.v')) {
  if ($f.BaseName -notmatch '^(?<h>[^_]+)__(?<i>a4[^_]+_s\d)_d1_s42__') { continue }
  $a4 += ,@($Matches['h'], $Matches['i'])
}
$a4 = $a4 | Sort-Object { $_[0] }, { $_[1] } -Unique
Log ("a4 instances = {0}" -f $a4.Count)
foreach ($s in $a4) {
  $tag = "a4same_{0}_{1}" -f $s[0], $s[1]
  $rc = Run-One $tag @('--host',$s[0],'--inst',$s[1],
      '--pairs','ys_abc:ys_id,ys_abc:ys_opt','--anchor','all','--budget','2000',
      '--per-sig','20','--prove-mode','simple','--batch','200','--timeout','300',
      '--workers','6','--skip-covered','--force')
  Log ("  [a4-same] {0}|{1} rc={2}" -f $s[0], $s[1], $rc)
}
foreach ($h in @('rs232t1000','s15850t100')) {
  foreach ($sd in @('s0','s1')) {
    foreach ($pr in @(@{a="a4trojan_$sd"; b="a4ctlequiv_$sd"}, @{a="a4trojan_$sd"; b="a4ctldead_$sd"}, @{a="a4ctlequiv_$sd"; b="a4ctldead_$sd"})) {
      $tag = "a4x_{0}_{1}_{2}" -f $h, $pr.a, $pr.b
      $rc = Run-One $tag @('--host',$h,'--inst',$pr.a,'--inst-b',$pr.b,'--recipe','ys_abc',
          '--anchor','all','--budget','2000','--per-sig','20','--batch','200',
          '--timeout','300','--workers','6','--skip-covered','--force')
      Log ("  [a4-cross] {0} {1} vs {2} rc={3}" -f $h, $pr.a, $pr.b, $rc)
    }
  }
}

# ---------- ctl : 2 pairs (abc:opt, abc:aig) ----------
Log '=== ctl : abc:opt + abc:aig (budget 2500) ==='
$ctl = @()
foreach ($f in (Get-ChildItem $tdir -Filter '*__ctl*_d1_s42__*.v')) {
  if ($f.BaseName -notmatch '^(?<h>[^_]+)__(?<i>ctl[^_]+)_d1_s42__') { continue }
  $ctl += ,@($Matches['h'], $Matches['i'])
}
$ctl = $ctl | Sort-Object { $_[0] }, { $_[1] } -Unique
Log ("ctl specs = {0}" -f $ctl.Count)
$i = 0
foreach ($s in $ctl) {
  $i++
  $tag = "ctl_{0}_{1}" -f $s[0], $s[1]
  $rc = Run-One $tag @('--host',$s[0],'--inst',$s[1],
      '--pairs','ys_abc:ys_opt,ys_abc:ys_aig','--anchor','all','--budget','2500',
      '--per-sig','20','--prove-mode','simple','--batch','200','--timeout','300',
      '--workers','6','--skip-covered','--force')
  Log ("  [ctl {0}/{1}] {2}|{3} rc={4}" -f $i, $ctl.Count, $s[0], $s[1], $rc)
}

# ---------- rebuild ----------
Log '--- rebuild: INCIDENT (train) + DRIVER (strict) + PERM (control) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --incident 2>&1 | Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --tag-suffix '_driver' 2>&1 | Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --permute-within-view --tag-suffix '_perm' 2>&1 | Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' 2>&1 | Select-String -Pattern 'n_pairs' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
'SAT_PHASE3_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== phase3 done ==='
