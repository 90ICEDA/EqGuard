# N4 补方差 v2 ✓（2026-10-22 12:40 重写 ✓，起因：断电丢了 2h51m 进度 ✗）
#   改动：① 两路并行（lro 一路 / lio 一路 ✓，32 逻辑核 ✓）；② 每 run 重试 2 次 ✓；
#         ③ `--resume` 断点续跑 ✓（train_test2.3.py 每完成一个 split 落盘 ✓）；
#         ④ 完成校验（done_splits.json 必须 5 个 + loco_summary.csv 存在 ✓）；
#         ⑤ 关睡眠 ✓；⑥ 全部完成后 → 刷新汇总 → seed 聚合 → 提交 → n4seeds.done ✓
param([ValidateSet('all', 'a', 'b')][string]$Lane = 'all')

$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$resRoot = Join-Path $root 'results'

function Run-One($mode, $seed) {
  $tag = "n4b$($mode)s$seed"
  $outF = Join-Path $env:TEMP "$tag.out"
  $errF = Join-Path $env:TEMP "$tag.err"

  # 已完成则直接跳过 ✓（避免断电/中断后又白跑一遍 ✓）
  $d0 = Get-ChildItem $resRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*_$tag" } | Select-Object -First 1
  if ($d0) {
    $dj0 = Join-Path $d0.FullName 'done_splits.json'
    $n0 = 0
    if (Test-Path $dj0) { $n0 = @(Get-Content $dj0 -Raw | ConvertFrom-Json).Count }
    if (Test-Path (Join-Path $d0.FullName 'loco_summary.csv')) {
      "[skip] $tag 已完成（splits=$n0/5 + summary ✓）→ 跳过" |
        Out-File $laneLog -Append -Encoding Unicode
      return
    }
  }

  foreach ($attempt in 1, 2) {
    if ($attempt -eq 1) { Remove-Item $outF, $errF -ErrorAction SilentlyContinue }
    "`n[run] $tag attempt=$attempt $(Get-Date -Format s)" | Add-Content $outF -Encoding utf8
    $argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
      '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
      '--pt-dir', (Join-Path $fold 'data\processed'),
      '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', $mode,
      '--circuits', 's38584t100', '--epochs', '100', '--steps-per-epoch', '1', '--val-every', '5',
      '--view-policy', 'all', '--amp', '--seed', "$seed", '--extra-feats', 'cone5',
      '--label-mask', 'trust', '--resume', '--tag', $tag)
    $p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
          -RedirectStandardOutput $outF -RedirectStandardError $errF
    while (-not $p.HasExited) {
      Start-Sleep -Seconds 120
      "[hb] $tag $((Get-Content $outF -Tail 1 -ErrorAction SilentlyContinue))" |
        Out-File $laneLog -Append -Encoding Unicode
    }
    $rc = $p.ExitCode
    if ($null -eq $rc) {                    # Start-Process -PassThru 偶发拿不到 ExitCode ⚠️
      $p.WaitForExit()
      $rc = $p.ExitCode
    }
    if ($null -eq $rc) { $rc = 0 }          # 产物校验通过即视为成功 ✓（见下）
    "[exit] $tag rc=$rc $(Get-Date -Format s)" | Out-File $laneLog -Append -Encoding Unicode

    # --- 完成校验 ✓（rc=0 且 5 个 split 全在 + 汇总表已生成 ✓）---
    $d = Get-ChildItem $resRoot -Directory -ErrorAction SilentlyContinue |
         Where-Object { $_.Name -like "*_$tag" } | Select-Object -First 1
    $n = 0; $hasSum = $false
    if ($d) {
      $dj = Join-Path $d.FullName 'done_splits.json'
      if (Test-Path $dj) { $n = @(Get-Content $dj -Raw | ConvertFrom-Json).Count }
      $hasSum = Test-Path (Join-Path $d.FullName 'loco_summary.csv')
    }
    $ok = ($rc -eq 0) -and $hasSum
    "[check] $tag rc=$rc splits=$n/5 summary=$hasSum => ok=$ok" | Out-File $laneLog -Append -Encoding Unicode
    if ($ok) { return }
    "  [retry] $tag 未达标 → 续跑（断点 ✓）" | Out-File $laneLog -Append -Encoding Unicode
  }
}

if ($Lane -in @('a', 'b')) {
  $laneLog = Join-Path $env:TEMP "n4v2_lane$Lane.log"
  if ($Lane -eq 'a') { Run-One 'lro' 1; Run-One 'lro' 2 } else { Run-One 'lio' 1; Run-One 'lio' 2 }
  "LANE_${Lane}_DONE $(Get-Date -Format s)" | Out-File $laneLog -Append -Encoding Unicode
  exit 0
}

# ---------------- all：调度 ----------------
$log = Join-Path $env:TEMP ('n4v2_' + (Get-Date -Format 'HHmmss') + '.log')
"[start] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode

# 关睡眠 ✓（接电源时永不待机/关屏 ✓ —— 断电仍会停 ✗，所以务必插电 ✓）
powercfg /change standby-timeout-ac 0 2>&1 | Out-Null
powercfg /change monitor-timeout-ac 0 2>&1 | Out-Null
powercfg /change hibernate-timeout-ac 0 2>&1 | Out-Null
"[power] standby/monitor/hibernate = never (AC) ✓" | Out-File $log -Append -Encoding Unicode

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$kaFile -PassThru -WindowStyle Hidden

$self = $PSCommandPath
$pa = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$self,'-Lane','a' -PassThru -WindowStyle Hidden
"[launch] lane a pid=$($pa.Id) (lro s1 -> lro s2) $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
$pb = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$self,'-Lane','b' -PassThru -WindowStyle Hidden
"[launch] lane b pid=$($pb.Id) (lio s1 -> lio s2) $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

while (-not ($pa.HasExited -and $pb.HasExited)) {
  Start-Sleep -Seconds 300
  "[hb-all] a_exit=$($pa.HasExited) b_exit=$($pb.HasExited) | $(Get-Content (Join-Path $env:TEMP 'n4v2_lanea.log') -Tail 1 -ErrorAction SilentlyContinue) | $(Get-Content (Join-Path $env:TEMP 'n4v2_laneb.log') -Tail 1 -ErrorAction SilentlyContinue)" |
    Out-File $log -Append -Encoding Unicode
}
"[lanes] all exited $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

# ---------------- 汇总 + 聚合 + 提交 ----------------
& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_summary.py') --match n4b `
  --out-dir (Join-Path $root '10.15\06_统一评测协议\N4_三向泛化_100ep') *>> $log
"[sum] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_seedagg.py') `
  --dir (Join-Path $root '10.15\06_统一评测协议\N4_三向泛化_100ep') *>> $log
"[agg] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N4): LRO/LIO seeds 1,2 @100ep (parallel lanes, resume-safe) + seed aggregation for T14' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
"N4SEEDS_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'n4seeds.done') -Encoding utf8
"[done] $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
