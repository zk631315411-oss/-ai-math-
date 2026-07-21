$ErrorActionPreference = 'Stop'
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$doc = $w.Documents.Add()
$shape = $doc.Shapes.AddTextbox(1, 10, 10, 200, 80)
$shape.TextFrame.TextRange.Text = "Title`rBody"
$range = $shape.TextFrame.TextRange
Write-Output ("TEXT=" + $range.Text)
try {
    $p1 = $range.Paragraphs(1)
    Write-Output ("P1=" + $p1.GetType().FullName)
    try {
        $pr = $p1.Range
        Write-Output ("PR=" + $pr.GetType().FullName)
        try {
            $pr.Font.Color = 1983737
            Write-Output "COLOR_OK"
        } catch {
            Write-Output ("COLOR_FAIL=" + $_.Exception.Message)
        }
    } catch {
        Write-Output ("PR_FAIL=" + $_.Exception.Message)
    }
} catch {
    Write-Output ("P1_FAIL=" + $_.Exception.Message)
}
try {
    $c1 = $range.Characters(1)
    Write-Output ("C1=" + $c1.GetType().FullName)
} catch {
    Write-Output ("C1_FAIL=" + $_.Exception.Message)
}
$doc.Close($false)
$w.Quit()
