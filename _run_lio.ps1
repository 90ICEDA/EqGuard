# P1：LIO（**木马家族留一** ✓）1 seed 试点（与 N4 同口径：60 epoch ✓，test 限 s38584t100 ✓）
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$log = Join-Path $env:TEMP ('lio_' + (Get-Date -Format 'HHmmss') + '.log')

$kaFile = Join-Path $env:TEMP 'keepawake.ps1'
@'
Add-Type -Name K -Namespace W -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while ($true) { [W.K]::SetThreadExecutionState(0x80000003) | Out-Null; Start-Sleep -Seconds 45 }
'@ | Set-Content $kaFile -Encoding utf8
$ka = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $kaFile -PassThru -WindowStyle Hidden

$argList = @('-X', 'utf8', '-u', (Join-Path $root 'train_test2.3.py'),
  '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
  '--pt-dir', (Join-Path $fold 'data\processed'),
  '--config', (Join-Path $root '_devcfg\dual.yaml'), '--fold-mode', 'lio',
  '--circuits', 's38584t100', '--epochs', '60', '--steps-per-epoch', '1', '--val-every', '5',
  '--view-policy', 'all', '--amp', '--seed', '42', '--extra-feats', 'cone5',
  '--label-mask', 'trust', '--tag', 'n4lio')
"[run] lio $(Get-Date -Format s)" | Out-File $log -Encoding Unicode
$outF = Join-Path $env:TEMP 'n4lio.out'
$errF = Join-Path $env:TEMP 'n4lio.err'
$p = Start-Process -FilePath $gpy -ArgumentList $argList -PassThru -NoNewWindow `
       -RedirectStandardOutput $outF -RedirectStandardError $errF
while (-not $p.HasExited) {
  Start-Sleep -Seconds 60
  "[hb] $((Get-Content $outF -Tail 1 -ErrorAction SilentlyContinue))" | Out-File $log -Append -Encoding Unicode
}
"[exit] lio rc=$($p.ExitCode) $(Get-Date -Format s)" | Out-File $log -Append -Encoding Unicode

& $py -X utf8 -u (Join-Path $root 'phase2\ys\make_n4_summary.py') *>> $log
"[sum] rc=$LASTEXITCODE" | Out-File $log -Append -Encoding Unicode

git add -A 2>&1 | Out-File $log -Append -Encoding Unicode
git commit -q -m 'feat(N4): family-LIO pilot (60 epoch, 1 seed) + refresh three-way protocol summary' 2>&1 |
  Out-File $log -Append -Encoding Unicode
"[git] rc=$LASTEXITCODE head=$(git rev-parse --short HEAD)" | Out-File $log -Append -Encoding Unicode
if ($ka -and -not $ka.HasExited) { Stop-Process -Id $ka.Id -Force -ErrorAction SilentlyContinue }
"LIO_DONE $(Get-Date -Format s)" | Out-File (Join-Path $env:TEMP 'lio.done') -Encoding utf8
