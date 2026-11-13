# _run_p0_agnostic_full.ps1 -- run label-agnostic combinational P0 in 2 lanes, then merge CSVs
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$flag = Join-Path $env:TEMP 'p0_agnostic.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
$lane = Join-Path $root '_p0_lane.ps1'
$log = Join-Path $root '_p0pilot\p0_full.log'
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

Log '=== label-agnostic combinational P0 full ==='
$a = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$lane,'s38584t100' -PassThru -WindowStyle Hidden
$b = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$lane,'s38417t100' -PassThru -WindowStyle Hidden
$c = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$lane,'s35932t200' -PassThru -WindowStyle Hidden
$d = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$lane,'rs232t1000,s15850t100' -PassThru -WindowStyle Hidden
Log ("laneA pid={0} (s38584) | laneB pid={1} (s38417) | laneC pid={2} (s35932) | laneD pid={3} (rs232+s15850)" -f $a.Id, $b.Id, $c.Id, $d.Id)
while (-not ($a.HasExited -and $b.HasExited -and $c.HasExited -and $d.HasExited)) { Start-Sleep -Seconds 60 }
Log 'both lanes exited -> merge'

& $py -X utf8 -c "import pandas as pd, glob, os; fs=glob.glob(r'_p0pilot/full_*.csv'); ds=[pd.read_csv(f,encoding='utf-8-sig') for f in fs]; d=pd.concat(ds,ignore_index=True); d=d.drop_duplicates(subset=['design','target'],keep='last'); d.to_csv(r'_p0pilot/functional_relations_agnostic.csv',index=False,encoding='utf-8-sig'); print('merged',len(d),'rows from',len(fs),'files')" 2>&1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8; Write-Host $_ }

'P0_AGNOSTIC_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== P0 agnostic full done ==='
