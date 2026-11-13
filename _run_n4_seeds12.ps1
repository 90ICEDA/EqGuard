# N4 补方差 ✓：LRO × seed 1,2 + LIO × seed 1,2（各 100 ep ✓，与 42 号同配置 ✓）
#   → 刷新三向汇总 → 生成 seed 聚合（mean±std ✓）→ 提交 → 写 n4seeds.done ✓
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('n4seeds_' + (Get-Date -Format 'HHmmss') + '.log')

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$kaFile -PassThru -WindowStyle Hidden

"[start] $(Get-Date -Format s)" | Out-File $log -Encoding Unicode

function Run-Protocol($mode, $seed) {
  $tag = "n4b$($mode)s$seed"
  $argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
    '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
    '--pt-dir', (Join-Path $fold 'data\processed'),
    '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', $mode,
    '--circuits', 's38584t100', '--epochs', '100', '--steps-per-epoch', '1', '--val-every', '5',
    '--view-policy', 'all', '--amp', '--seed', "$seed", '--extra-feats', 'cone5',
    '--label-mask', 'trust', '--tag', $tag)
  "[run] $tag $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
  $outF = Join-Path $env:TEMP "$tag.out"
  $errF = Join-Path $env:TEMP "$tag.err"
  $p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
        -RedirectStandardOutput $outF -RedirectStandardError $errF
  while (-not $p.HasExited) {
    Start-Sleep -Seconds 120
    "[hb] $tag $((Get-Content $outF -Tail 1 -ErrorAction SilentlyContinue))" |
      Out-File $log -Append -Encoding Unicode
  }
  "[exit] $tag rc=$($p.ExitCode) $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode
}

foreach ($m in 'lro', 'lio') { foreach ($s in 1, 2) { Run-Protocol $m $s } }

& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_summary.py') --match n4b `
  --out-dir (Join-Path $root '10.15\06_统一评测协议\N4_三向泛化_100ep') *>> $log
"[sum] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_seedagg.py') `
  --dir (Join-Path $root '10.15\06_统一评测协议\N4_三向泛化_100ep') *>> $log
"[agg] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N4): LRO/LIO seeds 1,2 @100ep + seed aggregation (mean+-std for T14)' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
"N4SEEDS_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'n4seeds.done') -Encoding utf8
