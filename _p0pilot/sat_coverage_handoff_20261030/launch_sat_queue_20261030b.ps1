$ErrorActionPreference = 'Stop'
$satRoot = (Join-Path $PSScriptRoot '../..')
Set-Location -LiteralPath $satRoot

# Preconditions: no project SAT python/coordinator still running
for ($i = 0; $i -lt 12; $i++) {
  $busy = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -like '*GIN_train*' }
  if (-not $busy) { break }
  Start-Sleep -Seconds 5
}
if ($busy) { throw ('Existing project python processes: ' + (($busy | ForEach-Object { $_.ProcessId }) -join ',')) }

# Precondition: WSL Yosys must be reachable from the venv interpreter used by the extractor
$satPython = Join-Path $satRoot 'ginvenv\Scripts\python.exe'
$probe = Join-Path $satRoot '_p0pilot\sat_coverage_handoff_20261030\probe_wmi.txt'
Remove-Item -LiteralPath $probe -ErrorAction SilentlyContinue
$probeCmd = '"{0}" -B -u -X utf8 "{1}"' -f $satPython, (Join-Path $satRoot '_p0pilot\sat_coverage_handoff_20261030\probe_wmi.py')
$probeRun = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $probeCmd; CurrentDirectory = $satRoot }
if ($probeRun.ReturnValue -ne 0) { throw ('WSL probe launch failed: ' + $probeRun.ReturnValue) }
for ($i = 0; $i -lt 20 -and -not (Test-Path -LiteralPath $probe); $i++) { Start-Sleep -Seconds 2 }
if (-not (Test-Path -LiteralPath $probe)) { throw 'WSL probe produced no output' }
$probeText = Get-Content -LiteralPath $probe -Encoding UTF8 -Raw
if ($probeText -notmatch 'rc=0') { throw ('WSL precheck failed: ' + $probeText) }

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$satQueue = Join-Path $satRoot ("_p0pilot\round29_20261029\queue_runs\handoff_" + $stamp)
New-Item -ItemType Directory -Path $satQueue -ErrorAction Stop | Out-Null

$satTables = Join-Path $satRoot '10.15\06_统一评测协议\N4_三向泛化\tables'
$satRequest = [ordered]@{
  time              = (Get-Date).ToString('o')
  wait_for          = @()
  panels            = @{
    validation = (Join-Path $satTables 'sat_k4_validation_round29')
    test       = (Join-Path $satTables 'sat_k4_test_round29')
  }
  new_training_runs = 0
  launch            = 'SAT-only handoff; reuse all successful evidence and verified train export'
}
$satUtf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $satQueue 'request.json'), ($satRequest | ConvertTo-Json -Depth 6), $satUtf8)

$satRunner = Join-Path $satRoot '_p0pilot\round29_20261029\immune_runner.py'
$satScript = Join-Path $satRoot '_p0pilot\round29_20261029\holdout_k4.py'
$satCommand = '"{0}" -B -u -X utf8 "{1}" "{2}" --queue "{3}"' -f $satPython, $satRunner, $satScript, $satQueue

$satLaunch = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $satCommand; CurrentDirectory = $satRoot }
if ($satLaunch.ReturnValue -ne 0) { throw ('WMI launch failed: ' + $satLaunch.ReturnValue) }

[ordered]@{ time = (Get-Date).ToString('o'); pid = $satLaunch.ProcessId; command = $satCommand; queue = $satQueue; wsl_precheck = $probeText.Trim() } |
  ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $satQueue 'launch.json') -Encoding utf8

Write-Output ('QUEUE=' + $satQueue)
Write-Output ('PID=' + $satLaunch.ProcessId)
