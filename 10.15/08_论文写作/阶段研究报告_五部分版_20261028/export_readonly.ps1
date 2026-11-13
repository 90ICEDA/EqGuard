$ErrorActionPreference = 'Stop'
$taskFolder = $PSScriptRoot
$taskDocument = Join-Path $taskFolder '面向等价网表的GNN木马检测研究阶段报告.docx'
$taskPdf = Join-Path $taskFolder '构建与核验/版式核验.pdf'
$wordApp = $null
$openedDocument = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $openedDocument = $wordApp.Documents.Open($taskDocument, $false, $true, $false)
    $openedDocument.Repaginate()
    $openedDocument.ExportAsFixedFormat($taskPdf, 17)
    Write-Output $taskPdf
} finally {
    if ($null -ne $openedDocument) { $openedDocument.Close(0) }
    if ($null -ne $wordApp) { $wordApp.Quit() }
}
