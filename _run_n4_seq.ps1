# N4 补方差 —— **顺序版** ✓（2026-10-22 12:55 ✓，按用户要求：一次只跑一个 run ✓）
#   顺序：lro s1 → lro s2 → lio s1 → lio s2（每个 run 内部仍带 --resume 断点 ✓）
#   每 run 结束由 `_run_n4_seeds12_v2.ps1 -Lane a|b` 自检（rc + done_splits=5 + loco_summary ✓）+ 重试一次 ✓
#   全部结束后：刷新三向汇总 ✓ → seed 聚合 ✓ → 提交 ✓ → 写 n4seeds.done ✓
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$laneScript = Join-Path $root '_run_n4_seeds12_v2.ps1'
$log = Join-Path $env:TEMP ('n4seq_' + (Get-Date -Format 'HHmmss') + '.log')
"[start] $(Get-Date -Format s) 顺序模式 ✓" | Out-File $log -Encoding Unicode

# 关睡眠 ✓（务必插电 ✓；断电最多只丢 1 个 split ✓，因为有 checkpoint ✓）
powercfg /change standby-timeout-ac 0 2>&1 | Out-Null
powercfg /change monitor-timeout-ac 0 2>&1 | Out-Null
powercfg /change hibernate-timeout-ac 0 2>&1 | Out-Null
"[power] never sleep (AC) ✓" | Out-File $log -Append -Encoding Unicode

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$kaFile -PassThru -WindowStyle Hidden

foreach ($lane in 'a', 'b') {
  "[lane-$lane] start $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $laneScript -Lane $lane *>> $log
  "[lane-$lane] rc=$LASTEXITCODE end $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
}

# ---------------- 汇总 + 聚合 + 提交 ----------------
& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_summary.py') --match n4b `
  --out-dir (Join-Path $root '10.15\06_统一评测协议\N4_三向泛化_100ep') *>> $log
"[sum] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_seedagg.py') `
  --dir (Join-Path $root '10.15\06_统一评测协议\N4_三向泛化_100ep') *>> $log
"[agg] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N4): LRO/LIO seeds 1,2 @100ep (sequential, resume-safe) + seed aggregation for T14' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
"N4SEEDS_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'n4seeds.done') -Encoding utf8
"[done] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
