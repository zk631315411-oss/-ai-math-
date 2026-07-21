$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Add()
$doc.Range(0,0).Text = "test"
$pdf = Join-Path $env:TEMP 'word_export_test.pdf'
try {
    $doc.ExportAsFixedFormat($pdf, 17)
    Write-Output ("PDF_OK " + $pdf)
} catch {
    Write-Output ("PDF_FAIL " + $_.Exception.Message)
}
$doc.Close($false)
$word.Quit()
