param([string]$Queue = (Join-Path (Join-Path $PSScriptRoot '../..') '_p0pilot/round29_20261029/queue_runs/handoff_20261030_214331'))
$ErrorActionPreference = 'Stop'
$s = (Join-Path $PSScriptRoot '../..')
$tables = Join-Path $s '10.15\06_统一评测协议\N4_三向泛化\tables'
$now = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

"== SAT status $now =="
if (Test-Path (Join-Path $Queue 'state.json')) {
  $st = Get-Content (Join-Path $Queue 'state.json') -Raw | ConvertFrom-Json
  "queue: phase=$($st.phase) time=$($st.time)"
}
foreach ($p in @('sat_k4_validation_round29', 'sat_k4_test_round29')) {
  $d = Join-Path $tables $p
  $views = Get-ChildItem (Join-Path $d 'views') -Directory -ErrorAction SilentlyContinue
  $cov = @($views | Where-Object { Test-Path (Join-Path $_.FullName 'coverage.json') })
  "$p : views=$($views.Count) verified_files=$($cov.Count)"
  $runs = Get-ChildItem (Join-Path $d 'runs') -Directory -ErrorAction SilentlyContinue | Sort-Object Name
  if ($runs) {
    $r = $runs[-1]
    $logs = Get-ChildItem $r.FullName -Filter *.log -ErrorAction SilentlyContinue
    "  run=$($r.Name) logs=$($logs.Count)"
    foreach ($lg in ($logs | Sort-Object LastWriteTime -Descending | Select-Object -First 1)) {
      $fi = Get-Item $lg.FullName
      $last = (Get-Content $lg.FullName -Tail 200 -ErrorAction SilentlyContinue | Select-String '\[BATCH\]' | Select-Object -Last 1)
      $c = Get-Content $lg.FullName -ErrorAction SilentlyContinue
      "  active=$($fi.Name) size=$([math]::Round($fi.Length/1KB))KB reused=$(($c | Select-String '\[EVIDENCE\] reused').Count) solved=$(($c | Select-String '\[EVIDENCE\] solved').Count) last=$last"
    }
  }
}
$procs = Get-Process | Where-Object { $_.ProcessName -match 'python|wsl|yosys' } | Group-Object ProcessName | ForEach-Object { "$($_.Name)=$($_.Count)" }
"procs: $($procs -join ' ')"
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
if ($os) { "free_mem_GiB={0:N2}" -f ($os.FreePhysicalMemory/1MB) }
"C_free_GiB={0:N2} D_free_GiB={1:N2}" -f ([System.IO.DriveInfo]::new('C').AvailableFreeSpace/1GB), ([System.IO.DriveInfo]::new('D').AvailableFreeSpace/1GB)
