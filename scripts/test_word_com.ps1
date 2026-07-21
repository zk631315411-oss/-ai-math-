$ErrorActionPreference = 'Stop'
$w = New-Object -ComObject Word.Application
$w.Visible = $false
Write-Output ("WORD_OK " + $w.Version)
$w.Quit()
