param(
    [string]$InputDocx = 'D:\ai-math\星火杯参赛材料\作品说明文档_智学助手_APA引用版.docx',
    [string]$OutputDocx = 'D:\ai-math\星火杯参赛材料\作品说明文档_智学助手_APA引用版_结构图终版.docx'
)

$ErrorActionPreference = 'Stop'

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

function Set-TextStyle {
    param(
        $Range,
        [double]$Size,
        [bool]$Bold
    )
    $Range.Font.NameFarEast = '仿宋'
    $Range.Font.Name = 'Times New Roman'
    $Range.Font.Size = $Size
    $Range.Font.Bold = $Bold
    $Range.ParagraphFormat.Alignment = 1
    $Range.ParagraphFormat.SpaceBefore = 0
    $Range.ParagraphFormat.SpaceAfter = 0
}

function Add-Band {
    param(
        [object]$Doc,
        [single]$Left,
        [single]$Top,
        [single]$Width,
        [single]$Height,
        [string]$Text,
        [int]$FillRgb,
        [int]$LineRgb
    )
    $shape = $Doc.Shapes.AddShape(1, $Left, $Top, $Width, $Height)
    $shape.Fill.ForeColor.RGB = $FillRgb
    $shape.Line.ForeColor.RGB = $LineRgb
    $shape.Line.Weight = 1.2
    $shape.TextFrame.MarginLeft = 6
    $shape.TextFrame.MarginRight = 6
    $shape.TextFrame.MarginTop = 3
    $shape.TextFrame.MarginBottom = 3
    $shape.TextFrame.VerticalAnchor = 3
    $shape.TextFrame.TextRange.Text = $Text
    Set-TextStyle -Range $shape.TextFrame.TextRange -Size 11 -Bold $true
    return $shape
}

function Add-Arrow {
    param(
        [object]$Doc,
        [single]$Left,
        [single]$Top,
        [string]$Text
    )
    $shape = $Doc.Shapes.AddTextbox(1, $Left, $Top, 26, 20)
    $shape.Line.Visible = $false
    $shape.Fill.Visible = $false
    $shape.TextFrame.TextRange.Text = $Text
    Set-TextStyle -Range $shape.TextFrame.TextRange -Size 18 -Bold $true
    return $shape
}

function Add-Box {
    param(
        [object]$Doc,
        [single]$Left,
        [single]$Top,
        [single]$Width,
        [single]$Height,
        [string]$Title,
        [string]$Body,
        [int]$FillRgb,
        [int]$LineRgb
    )
    $shape = $Doc.Shapes.AddShape(1, $Left, $Top, $Width, $Height)
    $shape.Fill.ForeColor.RGB = $FillRgb
    $shape.Line.ForeColor.RGB = $LineRgb
    $shape.Line.Weight = 1.1
    $shape.TextFrame.MarginLeft = 7
    $shape.TextFrame.MarginRight = 7
    $shape.TextFrame.MarginTop = 4
    $shape.TextFrame.MarginBottom = 4
    $shape.TextFrame.VerticalAnchor = 3
    $shape.TextFrame.TextRange.Text = $Title + [char]13 + $Body
    $tr = $shape.TextFrame.TextRange
    Set-TextStyle -Range $tr -Size 9.2 -Bold $false
    $count = $tr.Paragraphs.Count
    if ($count -ge 1) {
        $p1 = $tr.Paragraphs(1).Range
        Set-TextStyle -Range $p1 -Size 10.5 -Bold $true
    }
    for ($i = 2; $i -le $count; $i++) {
        $pi = $tr.Paragraphs($i).Range
        Set-TextStyle -Range $pi -Size 9.0 -Bold $false
    }
    return $shape
}

try {
    $doc = $word.Documents.Open($InputDocx, $false, $false)

    $end = $doc.Content
    $end.Collapse(0)
    $end.InsertBreak(7)
    $end.Collapse(0)
    $end.InsertAfter("附图  智学助手教育智能体结构示意图")
    Set-TextStyle -Range $end -Size 14 -Bold $true
    $end.InsertParagraphAfter()
    $end.Collapse(0)
    $end.InsertAfter("以教材约束为边界，以学习者状态为依据，以持续反馈促进理解深化")
    Set-TextStyle -Range $end -Size 10.5 -Bold $false
    $end.InsertParagraphAfter()
    $end.Collapse(0)

    $pageWidth = $doc.PageSetup.PageWidth
    $centerX = $pageWidth / 2
    $boxW = 400
    $boxLeft = $centerX - ($boxW / 2)

    Add-Band -Doc $doc -Left ($centerX - 215) -Top 110 -Width 430 -Height 28 -Text '教育目标：精准诊断   适切支架   持续反馈' -FillRgb 15790333 -LineRgb 12105912
    Add-Arrow -Doc $doc -Left ($centerX - 12) -Top 144 -Text '↓'

    $y = 170
    Add-Box -Doc $doc -Left $boxLeft -Top $y -Width $boxW -Height 50 -Title '一　学习入口' -Body '教材阅读`r文字提问`r截图求助' -FillRgb 16056037 -LineRgb 9325654
    Add-Arrow -Doc $doc -Left ($centerX - 12) -Top 225 -Text '↓'

    $y = 250
    Add-Box -Doc $doc -Left $boxLeft -Top $y -Width $boxW -Height 50 -Title '二　知识基础' -Body '页码锚定`r知识图谱`r前置关系' -FillRgb 16324499 -LineRgb 10440037
    Add-Arrow -Doc $doc -Left ($centerX - 12) -Top 305 -Text '↓'

    $y = 330
    Add-Box -Doc $doc -Left $boxLeft -Top $y -Width $boxW -Height 50 -Title '三　学习者诊断' -Body '掌握阶段`r薄弱概念`r学习记录' -FillRgb 16774292 -LineRgb 14341757
    Add-Arrow -Doc $doc -Left ($centerX - 12) -Top 385 -Text '↓'

    $y = 410
    Add-Box -Doc $doc -Left $boxLeft -Top $y -Width $boxW -Height 50 -Title '四　导学支持' -Body '分步讲解`r提示追问`r支架调节' -FillRgb 16056037 -LineRgb 9325654
    Add-Arrow -Doc $doc -Left ($centerX - 12) -Top 465 -Text '↓'

    $y = 490
    Add-Box -Doc $doc -Left $boxLeft -Top $y -Width $boxW -Height 50 -Title '五　练习评价' -Body '按页出题`r过程批改`r错因分析' -FillRgb 16324499 -LineRgb 10440037
    Add-Arrow -Doc $doc -Left ($centerX - 12) -Top 545 -Text '↓'

    $y = 570
    Add-Box -Doc $doc -Left $boxLeft -Top $y -Width $boxW -Height 50 -Title '六　反馈更新' -Body '画像回写`r补弱建议`r策略调整' -FillRgb 16774292 -LineRgb 14341757

    Add-Band -Doc $doc -Left ($centerX - 215) -Top 640 -Width 430 -Height 28 -Text '评价证据：提问质量   概念变化   错因分布   后续建议' -FillRgb 15856420 -LineRgb 12500642

    $note = $doc.Content
    $note.Collapse(0)
    $note.InsertAfter("注：图中直线箭头表示学习支持的主要推进方向，反馈更新用于形成下一轮学习建议。")
    Set-TextStyle -Range $note -Size 9.2 -Bold $false
    $note.InsertParagraphAfter()
    $note.Collapse(0)

    $doc.SaveAs2($OutputDocx)
    $doc.Close()
}
finally {
    $word.Quit()
}
