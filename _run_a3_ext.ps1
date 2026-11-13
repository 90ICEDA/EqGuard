# A3-ext: keep policy ablation, 10 views x 3 recipes x 4 schemes = 120 combos
# 4-way parallel; each task gets its own --out and --tables (the script overwrites its CSV)
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$logDir = Join-Path $env:TEMP 'a3ext'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$jobs = @(
  @{ tag = 'a4_rs232';  root = 'hosts_a4';  host = 'rs232t1000'; view = 'rs232t1000__a4trojan_s0_d1_s42' },
  @{ tag = 'a4_s15850'; root = 'hosts_a4';  host = 's15850t100'; view = 's15850t100__a4trojan_s0_d1_s42' },
  @{ tag = 'a4_s35932'; root = 'hosts_a4';  host = 's35932t200'; view = 's35932t200__a4trojan_s0_d1_s42' },
  @{ tag = 'a4_s38417'; root = 'hosts_a4';  host = 's38417t100'; view = 's38417t100__a4trojan_s0_d1_s42' },
  @{ tag = 'a4_s38584'; root = 'hosts_a4';  host = 's38584t100'; view = 's38584t100__a4trojan_s0_d1_s42' },
  @{ tag = 'bt2_rs232'; root = 'hosts_bt2'; host = 'rs232t1000'; view = 'rs232t1000__injalpha_d1_s42' },
  @{ tag = 'bt2_s15850'; root = 'hosts_bt2'; host = 's15850t100'; view = 's15850t100__injalpha_d1_s42' },
  @{ tag = 'bt2_s35932'; root = 'hosts_bt2'; host = 's35932t200'; view = 's35932t200__injalpha_d1_s42' },
  @{ tag = 'bt2_s38417'; root = 'hosts_bt2'; host = 's38417t100'; view = 's38417t100__injalpha_d1_s42' },
  @{ tag = 'bt2_s38584'; root = 'hosts_bt2'; host = 's38584t100'; view = 's38584t100__injalpha_d1_s42' }
)

$maxParallel = 4
$running = @()
$done = @()
$startedAt = Get-Date
"start $($startedAt.ToString('s')) tasks=$($jobs.Count) parallel=$maxParallel" | Out-File -FilePath (Join-Path $logDir '_run.out') -Encoding utf8

foreach ($j in $jobs) {
  while ((@($running | Where-Object { -not $_.HasExited })).Count -ge $maxParallel) {
    Start-Sleep -Seconds 5
  }
  $outDir = "generate_trans\keepab_ext\$($j.tag)"
  # NOTE: do NOT pass Chinese paths through Start-Process (ANSI round-trip mangles them
  # into a mojibake directory). --tables therefore uses an ASCII dir; merge_a3_ext.py
  # (Python, Unicode-safe) copies the CSVs into the Chinese docs folder afterwards.
  $tabDir = "_a3ext\tables\$($j.tag)"
  $argv = @(
    '-X', 'utf8', '-u', 'phase2\ys\keep_ablation.py',
    '--hosts-root', "generate_trans\$($j.root)",
    '--host', $j.host,
    '--views', $j.view,
    '--recipes', 'abc,nand,aig',
    '--schemes', 'none,cur,bnd,full',
    '--out', $outDir,
    '--tables', $tabDir,
    '--timeout', '1800'
  )
  $p = Start-Process -FilePath $py -ArgumentList $argv `
        -RedirectStandardOutput (Join-Path $logDir "$($j.tag).log") `
        -RedirectStandardError (Join-Path $logDir "$($j.tag).err") `
        -PassThru -WindowStyle Hidden
  $p | Add-Member -NotePropertyName Tag -NotePropertyValue $j.tag -Force
  $running += $p
  "launch $($j.tag) pid=$($p.Id) $(Get-Date -Format s)" | Out-File -FilePath (Join-Path $logDir '_run.out') -Encoding utf8 -Append
}

while ((@($running | Where-Object { -not $_.HasExited })).Count -gt 0) {
  Start-Sleep -Seconds 10
}

foreach ($p in $running) {
  $done += "$($p.Tag) exit=$($p.ExitCode)"
}
$elapsed = [int]((Get-Date) - $startedAt).TotalSeconds
$done | Out-File -FilePath (Join-Path $logDir '_run.out') -Encoding utf8 -Append
"DONE elapsed=${elapsed}s $(Get-Date -Format s)" | Out-File -FilePath (Join-Path $logDir '_run.out') -Encoding utf8 -Append
