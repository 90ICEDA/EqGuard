# Rebuild fold v3 graph data (parser2 with the yosys-netlist fixes) + pt, then the baseline can be re-run.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt3'
$log = Join-Path $env:TEMP ("rebuild_v3_" + (Get-Date -Format 'HHmmss') + ".log")
"start $(Get-Date -Format s)" | Out-File -FilePath $log -Encoding utf8

Push-Location $fold
& $py -X utf8 -u (Join-Path $root 'data\verilog_data\parser2.py') --out-root ./data/for_train --skip-debug --cycle-mode contract --prov-root (Join-Path $root 'generate_trans\hosts_bt2'),(Join-Path $root 'generate_trans\hosts_a4') *>> $log
$rc1 = $LASTEXITCODE
Pop-Location
"[parser2] rc=$rc1" | Out-File -FilePath $log -Encoding utf8 -Append

& $py -X utf8 -u (Join-Path $root 'process_pt2.py') --work-dir $fold --fold-json (Join-Path $fold 'views.json') --matrix-root $fold --trans-label transported *>> $log
$rc2 = $LASTEXITCODE
"[process_pt2] rc=$rc2" | Out-File -FilePath $log -Encoding utf8 -Append
"DONE rc1=$rc1 rc2=$rc2 $(Get-Date -Format s)" | Out-File -FilePath $log -Encoding utf8 -Append
