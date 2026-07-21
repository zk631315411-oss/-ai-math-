param(
    [string]$InputDocx = 'D:\ai-math\星火杯参赛材料\作品说明文档_智学助手_教育学强化版.docx',
    [string]$OutputDocx = 'D:\ai-math\星火杯参赛材料\作品说明文档_智学助手_教育学强化版_末尾结构图版.docx'
)

$ErrorActionPreference = 'Stop'

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

function Set-RangeStyle {
    param($Range, [double]$Size, [bool]$Bold, [int]$Color)
    $Range.Font.NameFarEast = '仿宋'
    $Range.Font.Name = 'Times New Roman'
    $Range.Font.Size = $Size
    $Range.Font.Bold = $Bold
    $Range.Font.Color = $Color
    $Range.ParagraphFormat.Alignment = 1
    $Range.ParagraphFormat.SpaceBefore = 0
    $Range.ParagraphFormat.SpaceAfter = 0
}

function Add-Box {
    param($Doc, [single]$Left, [single]$Top, [single]$Width, [single]$Height, [string]$Title, [string]$Body, [int]$Fill, [int]$Line, [int]$TitleColor)
    $shape = $Doc.Shapes.AddShape(1, $Left, $Top, $Width, $Height)
    $shape.Fill.ForeColor.RGB = $Fill
    $shape.Line.ForeColor.RGB = $Line
    $shape.Line.Weight = 1.1
    $shape.TextFrame.MarginLeft = 7
    $shape.TextFrame.MarginRight = 7
    $shape.TextFrame.MarginTop = 4
    $shape.TextFrame.MarginBottom = 4
    $shape.TextFrame.VerticalAnchor = 3
    $shape.TextFrame.TextRange.Text = $Title + [char]13 + $Body
    $tr = $shape.TextFrame.TextRange
    if ($tr.Paragraphs.Count -ge 1) { Set-RangeStyle -Range $tr.Paragraphs(1).Range -Size 10.5 -Bold $true -Color $TitleColor }
    if ($tr.Paragraphs.Count -ge 2) {
        for ($i = 2; $i -le $tr.Paragraphs.Count; $i++) { Set-RangeStyle -Range $tr.Paragraphs($i).Range -Size 9.1 -Bold $false -Color 4605510 }
    }
    return $shape
}

function Add-Band {
    param($Doc, [single]$Left, [single]$Top, [single]$Width, [single]$Height, [string]$Text, [int]$Fill, [int]$Line, [int]$TextColor)
    $shape = $Doc.Shapes.AddShape(1, $Left, $Top, $Width, $Height)
    $shape.Fill.ForeColor.RGB = $Fill
    $shape.Line.ForeColor.RGB = $Line
    $shape.Line.Weight = 1.1
    $shape.TextFrame.MarginLeft = 8
    $shape.TextFrame.MarginRight = 8
    $shape.TextFrame.MarginTop = 3
    $shape.TextFrame.MarginBottom = 3
    $shape.TextFrame.VerticalAnchor = 3
    $shape.TextFrame.TextRange.Text = $Text
    Set-RangeStyle -Range $shape.TextFrame.TextRange -Size 10.6 -Bold $true -Color $TextColor
    return $shape
}

function Add-Arrow {
    param($Doc, [single]$Left, [single]$Top, [string]$Text = '↓')
    $shape = $Doc.Shapes.AddTextbox(1, $Left, $Top, 24, 20)
    $shape.Line.Visible = $false
    $shape.Fill.Visible = $false
    $shape.TextFrame.TextRange.Text = $Text
    Set-RangeStyle -Range $shape.TextFrame.TextRange -Size 18 -Bold $true -Color 3940090
    return $shape
}

try {
    $doc = $word.Documents.Open($InputDocx, $false, $false)

    # Remove any prior tail figure if present.
    $deleteStart = $null
    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $text = ($doc.Paragraphs.Item($i).Range.Text).Trim()
        if ($text.StartsWith('图1 智学助手教育智能体结构示意图') -or $text.StartsWith('附图')) {
            $deleteStart = $doc.Paragraphs.Item($i).Range.Start
            break
        }
    }
    if ($null -ne $deleteStart) {
        $tailRange = $doc.Range($deleteStart, $doc.Content.End)
        $tailRange.Delete()
    }

    $end = $doc.Content
    $end.Collapse(0)
    $end.InsertBreak(7)
    $end.Collapse(0)
    $end.InsertAfter('图1 智学助手教育智能体结构示意图')
    Set-RangeStyle -Range $end -Size 14 -Bold $true -Color 1983737
    $end.InsertParagraphAfter()
    $end.Collapse(0)
    $end.InsertAfter('以教材约束为边界，以学习者状态为依据，以持续反馈促进理解深化')
    Set-RangeStyle -Range $end -Size 10.2 -Bold $false -Color 5921370
    $end.InsertParagraphAfter()

    $pageWidth = $doc.PageSetup.PageWidth
    $leftMargin = $doc.PageSetup.LeftMargin
    $rightMargin = $doc.PageSetup.RightMargin
    $usable = $pageWidth - $leftMargin - $rightMargin
    $center = $leftMargin + ($usable / 2)
    $boxWidth = 420
    $boxLeft = $center - ($boxWidth / 2)
    $boxHeight = 54
    $startY = 155
    $step = 74

    $blueFill = 15656936
    $greenFill = 15925611
    $orangeFill = 16771782
    $headerFill = 1983737
    $greyFill = 15658741
    $blueLine = 9160037
    $greenLine = 10252349
    $orangeLine = 14278301
    $greyLine = 12041634
    $blueText = 1983737
    $greenText = 4424722
    $orangeText = 9200925
    $greyText = 3947593

    Add-Band -Doc $doc -Left ($center - 215) -Top 100 -Width 430 -Height 28 -Text '教育目标：精准诊断   适切支架   持续反馈' -Fill $headerFill -Line $headerFill -TextColor 16777215
    Add-Arrow -Doc $doc -Left ($center - 12) -Top 133

    Add-Box -Doc $doc -Left $boxLeft -Top $startY -Width $boxWidth -Height $boxHeight -Title '一　学习入口' -Body "教材阅读`r文字提问`r截图求助" -Fill $blueFill -Line $blueLine -TitleColor $blueText
    Add-Arrow -Doc $doc -Left ($center - 12) -Top ($startY + 56)

    Add-Box -Doc $doc -Left $boxLeft -Top ($startY + $step) -Width $boxWidth -Height $boxHeight -Title '二　知识基础' -Body "页码锚定`r知识图谱`r前置关系" -Fill $greenFill -Line $greenLine -TitleColor $greenText
    Add-Arrow -Doc $doc -Left ($center - 12) -Top ($startY + $step + 56)

    Add-Box -Doc $doc -Left $boxLeft -Top ($startY + $step * 2) -Width $boxWidth -Height $boxHeight -Title '三　学习者诊断' -Body "掌握阶段`r薄弱概念`r学习记录" -Fill $orangeFill -Line $orangeLine -TitleColor $orangeText
    Add-Arrow -Doc $doc -Left ($center - 12) -Top ($startY + $step * 2 + 56)

    Add-Box -Doc $doc -Left $boxLeft -Top ($startY + $step * 3) -Width $boxWidth -Height $boxHeight -Title '四　导学支持' -Body "分步讲解`r提示追问`r支架调节" -Fill $blueFill -Line $blueLine -TitleColor $blueText
    Add-Arrow -Doc $doc -Left ($center - 12) -Top ($startY + $step * 3 + 56)

    Add-Box -Doc $doc -Left $boxLeft -Top ($startY + $step * 4) -Width $boxWidth -Height $boxHeight -Title '五　练习评价' -Body "按页出题`r过程批改`r错因分析" -Fill $greenFill -Line $greenLine -TitleColor $greenText
    Add-Arrow -Doc $doc -Left ($center - 12) -Top ($startY + $step * 4 + 56)

    Add-Box -Doc $doc -Left $boxLeft -Top ($startY + $step * 5) -Width $boxWidth -Height $boxHeight -Title '六　反馈更新' -Body "画像回写`r补弱建议`r策略调整" -Fill $orangeFill -Line $orangeLine -TitleColor $orangeText

    Add-Band -Doc $doc -Left ($center - 215) -Top ($startY + $step * 5 + 76) -Width 430 -Height 28 -Text '评价证据：提问质量   概念变化   错因分布   后续建议' -Fill $greyFill -Line $greyLine -TextColor $greyText

    $note = $doc.Content
    $note.Collapse(0)
    $note.InsertAfter('注：直线箭头表示学习支持的推进方向，反馈更新用于形成下一轮学习建议。')
    Set-RangeStyle -Range $note -Size 9.1 -Bold $false -Color 6381921
    $note.InsertParagraphAfter()

    $doc.SaveAs2($OutputDocx)
    $doc.Close()
}
finally {
    $word.Quit()
}

