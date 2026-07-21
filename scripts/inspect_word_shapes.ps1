param(
    [string]$InputDocx = 'D:\ai-math\星火杯参赛材料\作品说明文档_智学助手_APA引用版.docx'
)

$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($InputDocx, $false, $true)
    Write-Output ("Shapes=" + $doc.Shapes.Count)
    Write-Output ("InlineShapes=" + $doc.InlineShapes.Count)
    $doc.Close($false)
}
finally {
    $word.Quit()
}
