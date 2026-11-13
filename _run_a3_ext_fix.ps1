# A3-ext fix pass: re-run the 4 tags that were killed while the old (quadratic) text_surv was running.
# Uses the patched keep_ablation.py (token-bag text survival, ~0.1s/view instead of ~10min).
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$logDir = Join-Path $env:TEMP 'a3ext'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$jobs = @(
  @{ tag = 'a4_s35932';  root = 'hosts_a4';  host = 's35932t200'; view = 's35932t200__a4trojan_s0_d1_s42' },
  @{ tag = 'a4_s38417';  root = 'hosts_a4';  host = 's38417t100'; view = 's38417t100__a4trojan_s0_d1_s42' },
  @{ tag = 'a4_s38584';  root = 'hosts_a4';  host = 's38584t100'; view = 's38584t100__a4trojan_s0_d1_s42' },
  @{ tag = 'bt2_s15850'; root = 'hosts_bt2'; host = 's15850t100'; view = 's15850t100__injalpha_d1_s42' }
)

$running = @()
$startedAt = Get-Date
"fix-start $($startedAt.ToString('s')) tasks=$($jobs.Count)" | Out-File -FilePath (Join-Path $logDir '_run_fix.out') -Encoding utf8

foreach ($j in $jobs) {
  $argv = @(
    '-X', 'utf8', '-u', 'phase2\ys\keep_ablation.py',
    '--hosts-root', "generate_trans\$($j.root)",
    '--host', $j.host,
    '--views', $j.view,
    '--recipes', 'abc,nand,aig',
    '--schemes', 'none,cur,bnd,full',
    '--out', "generate_trans\keepab_ext\$($j.tag)",
    '--tables', "_a3ext\tables\$($j.tag)",
    '--timeout', '1800'
  )
  $p = Start-Process -FilePath $py -ArgumentList $argv `
        -RedirectStandardOutput (Join-Path $logDir "$($j.tag).log") `
        -RedirectStandardError (Join-Path $logDir "$($j.tag).err") `
        -PassThru -WindowStyle Hidden
  $p | Add-Member -NotePropertyName Tag -NotePropertyValue $j.tag -Force
  $running += $p
  "launch $($j.tag) pid=$($p.Id) $(Get-Date -Format s)" | Out-File -FilePath (Join-Path $logDir '_run_fix.out') -Encoding utf8 -Append
}

while ((@($running | Where-Object { -not $_.HasExited })).Count -gt 0) {
  Start-Sleep -Seconds 10
}

foreach ($p in $running) { "$($p.Tag) exit=$($p.ExitCode)" | Out-File -FilePath (Join-Path $logDir '_run_fix.out') -Encoding utf8 -Append }
"DONE fix elapsed=$([int]((Get-Date) - $startedAt).TotalSeconds)s" | Out-File -FilePath (Join-Path $logDir '_run_fix.out') -Encoding utf8 -Append
