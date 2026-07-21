param(
    [string]$InputDocx = 'D:\ai-math\星火杯参赛材料\作品说明文档_智学助手_APA引用版.docx',
    [string]$OutputDocx = 'D:\ai-math\星火杯参赛材料\作品说明文档_智学助手_APA引用版_结构图重做版.docx'
)

$ErrorActionPreference = 'Stop'

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputDocx, $false, $false)

    $end = $doc.Content
    $end.Collapse(0)
    $end.InsertBreak(7)
    $end.Collapse(0)
    $end.InsertAfter("附图  智学助手教育智能体结构示意图")
    $end.Font.NameFarEast = "仿宋"
    $end.Font.Size = 14
    $end.Font.Bold = $true
    $end.ParagraphFormat.Alignment = 1
    $end.InsertParagraphAfter()
    $end.Collapse(0)
    $end.InsertAfter("以教材约束为边界，以学习者状态为依据，以持续反馈促进理解深化")
    $end.Font.NameFarEast = "仿宋"
    $end.Font.Size = 10.5
    $end.Font.Bold = $false
    $end.ParagraphFormat.Alignment = 1
    $end.InsertParagraphAfter()

    $pageWidth = $doc.PageSetup.PageWidth
    $leftMargin = $doc.PageSetup.LeftMargin
    $rightMargin = $doc.PageSetup.RightMargin
    $usable = $pageWidth - $leftMargin - $rightMargin
    $centerX = $leftMargin + ($usable / 2)

    function AddBox {
        param(
            [single]$Left,
            [single]$Top,
            [single]$Width,
            [single]$Height,
            [string]$Title,
            [string]$Body,
            [int]$FillRgb,
            [int]$LineRgb,
            [int]$TitleRgb
        )
        $shape = $doc.Shapes.AddShape(1, $Left, $Top, $Width, $Height)
        $shape.Fill.ForeColor.RGB = $FillRgb
        $shape.Line.ForeColor.RGB = $LineRgb
        $shape.Line.Weight = 1.2
        $shape.TextFrame.MarginLeft = 6
        $shape.TextFrame.MarginRight = 6
        $shape.TextFrame.MarginTop = 4
        $shape.TextFrame.MarginBottom = 4
        $shape.TextFrame.VerticalAnchor = 3
        $shape.TextFrame.TextRange.Text = $Title + [char]13 + $Body
        $shape.TextFrame.TextRange.ParagraphFormat.Alignment = 1
        $shape.TextFrame.TextRange.Font.NameFarEast = "仿宋"
        $shape.TextFrame.TextRange.Font.Size = 9.5
        $shape.TextFrame.TextRange.Characters(1, $Title.Length).Font.Bold = $true
        $shape.TextFrame.TextRange.Characters(1, $Title.Length).Font.Size = 10.5
        $shape.TextFrame.TextRange.Characters(1, $Title.Length).Font.Color = $TitleRgb
    }

    function AddArrow {
        param(
            [single]$Left,
            [single]$Top,
            [string]$Text
        )
        $shape = $doc.Shapes.AddTextbox(1, $Left, $Top, 22, 20)
        $shape.Line.Visible = $false
        $shape.Fill.Visible = $false
        $shape.TextFrame.TextRange.Text = $Text
        $shape.TextFrame.TextRange.Font.NameFarEast = "仿宋"
        $shape.TextFrame.TextRange.Font.Size = 18
        $shape.TextFrame.TextRange.Font.Bold = $true
        $shape.TextFrame.TextRange.Font.Color = 3940090
        $shape.TextFrame.TextRange.ParagraphFormat.Alignment = 1
    }

    function AddBand {
        param(
            [single]$Left,
            [single]$Top,
            [single]$Width,
            [single]$Height,
            [string]$Text,
            [int]$FillRgb,
            [int]$LineRgb,
            [int]$TextRgb
        )
        $shape = $doc.Shapes.AddShape(1, $Left, $Top, $Width, $Height)
        $shape.Fill.ForeColor.RGB = $FillRgb
        $shape.Line.ForeColor.RGB = $LineRgb
        $shape.Line.Weight = 1.2
        $shape.TextFrame.MarginLeft = 6
        $shape.TextFrame.MarginRight = 6
        $shape.TextFrame.MarginTop = 3
        $shape.TextFrame.MarginBottom = 3
        $shape.TextFrame.VerticalAnchor = 3
        $shape.TextFrame.TextRange.Text = $Text
        $shape.TextFrame.TextRange.Font.NameFarEast = "仿宋"
        $shape.TextFrame.TextRange.Font.Size = 10.5
        $shape.TextFrame.TextRange.Font.Bold = $true
        $shape.TextFrame.TextRange.Font.Color = $TextRgb
        $shape.TextFrame.TextRange.ParagraphFormat.Alignment = 1
    }

    $titleTop = 110
    AddBand ($centerX - 200) $titleTop 400 30 "教育目标：精准诊断   适切支架   持续反馈" 1983737 1983737 16777215
    AddArrow ($centerX - 10) ($titleTop + 35) "↓"

    $row1Top = $titleTop + 62
    $boxW = 145
    $boxH = 56
    $left1 = $centerX - 230
    $left2 = $centerX - 72
    $left3 = $centerX + 86

    AddBox $left1 $row1Top $boxW $boxH "一　学习入口" "教材阅读`r文字提问`r截图求助" 15656936 9160037 1983737
    AddArrow ($left1 + 152) ($row1Top + 20) "→"
    AddBox $left2 $row1Top $boxW $boxH "二　知识基础" "页码锚定`r知识图谱`r前置关系" 15925611 10252349 4424722
    AddArrow ($left2 + 152) ($row1Top + 20) "→"
    AddBox $left3 $row1Top $boxW $boxH "三　学习者诊断" "掌握阶段`r薄弱概念`r学习记录" 16771782 14278301 9200925

    AddArrow ($left3 + 60) ($row1Top + 56) "↓"

    $row2Top = $row1Top + 88
    AddBox $left3 $row2Top $boxW $boxH "四　导学支持" "分步讲解`r提示追问`r支架调节" 15656936 9160037 1983737
    AddArrow ($left3 - 18) ($row2Top + 20) "←"
    AddBox $left2 $row2Top $boxW $boxH "五　练习评价" "按页出题`r过程批改`r错因分析" 15925611 10252349 4424722
    AddArrow ($left2 - 18) ($row2Top + 20) "←"
    AddBox $left1 $row2Top $boxW $boxH "六　反馈更新" "画像回写`r补弱建议`r策略调整" 16771782 14278301 9200925

    AddArrow ($left1 + 60) ($row2Top + 58) "↓"
    AddBand ($centerX - 190) ($row2Top + 85) 380 28 "评价证据：提问质量   概念变化   错因分布   后续建议" 15658741 12041634 3947593

    $note = $doc.Content
    $note.Collapse(0)
    $note.InsertAfter("注：图中直线箭头表示学习支持的主要推进方向，反馈更新用于形成下一轮学习建议。")
    $note.Font.NameFarEast = "仿宋"
    $note.Font.Size = 9.2
    $note.Font.Color = 6381921
    $note.ParagraphFormat.Alignment = 1

    $doc.SaveAs([ref]$OutputDocx)
    $doc.Close()
}
finally {
    $word.Quit()
}

