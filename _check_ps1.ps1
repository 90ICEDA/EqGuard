$p = (Join-Path $PSScriptRoot '_run_after_reboot.ps1')
$tokens = $null
$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($p, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) { $errors | ForEach-Object { $_.Message } } else { 'ps1 syntax OK' }
