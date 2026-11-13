@echo off
wsl -e bash -lc "yosys -V; id -un; date -Is" > "C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\sat_coverage_handoff_20261030\probe_wsl.txt" 2>&1
echo rc=%errorlevel% >> "C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\sat_coverage_handoff_20261030\probe_wsl.txt"
