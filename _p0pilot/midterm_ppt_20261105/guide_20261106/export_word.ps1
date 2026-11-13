$ErrorActionPreference = 'Stop'
$taskRoot = (Join-Path $PSScriptRoot '../../..')
$docPath = Join-Path $taskRoot '10.15\08_论文写作\中期答辩_20261105\中期答辩逐页详细讲解_对应34页成果重点修订版_20261106.docx'
$pdfPath = Join-Path $taskRoot '_p0pilot\midterm_ppt_20261105\guide_20261106\word_preview.pdf'
$taskWord = $null
$taskDoc = $null
try {
  $taskWord = New-Object -ComObject Word.Application
  $taskWord.Visible = $false
  $taskWord.DisplayAlerts = 0
  $taskWord.AutomationSecurity = 3
  $taskDoc = $taskWord.Documents.Open($docPath, $false, $true)
  $taskDoc.Repaginate()
  $taskDoc.ExportAsFixedFormat($pdfPath, 17)
  Write-Output ('Rendered pages: ' + $taskDoc.ComputeStatistics(2))
} finally {
  if ($null -ne $taskDoc) { $taskDoc.Close(0); [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskDoc) }
  if ($null -ne $taskWord) { $taskWord.Quit(); [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskWord) }
}
