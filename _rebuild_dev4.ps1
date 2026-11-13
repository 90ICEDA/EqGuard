# Rebuild dev4 graph data after the concat-assign fix (parser2 + process_pt2).
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\_dev4'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ("dev4_rebuild_" + (Get-Date -Format 'HHmmss') + ".log")

Push-Location $fold
& $py -X utf8 -u (Join-Path $root 'data\verilog_data\parser2.py') --out-root ./data/for_train --skip-debug --cycle-mode contract --prov-root (Join-Path $root 'generate_trans\hosts_bt2'),(Join-Path $root 'generate_trans\hosts_a4') *>> $log
"[parser2] rc=$LASTEXITCODE" | Out-File -FilePath $log -Encoding utf8 -Append
Pop-Location

& $py -X utf8 -u (Join-Path $root 'process_pt2.py') --work-dir $fold --fold-json (Join-Path $fold 'views.json') --matrix-root $fold --trans-label transported *>> $log
"[process_pt2] rc=$LASTEXITCODE" | Out-File -FilePath $log -Encoding utf8 -Append
"worker=20" | Out-Null
