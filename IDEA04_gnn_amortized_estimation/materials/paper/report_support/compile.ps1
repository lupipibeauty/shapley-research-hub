$ErrorActionPreference = "Stop"

$xelatex = Get-Command xelatex -ErrorAction SilentlyContinue
if ($null -eq $xelatex) {
    $candidate = "D:\ProgramFiles\texlive\2026\bin\windows\xelatex.exe"
    if (Test-Path $candidate) {
        $xelatex = Get-Item $candidate
    } else {
        throw "xelatex was not found."
    }
}

$bibtex = Join-Path (Split-Path $xelatex.Source) "bibtex.exe"

& $xelatex.Source -interaction=nonstopmode -halt-on-error experiment_report.tex
if ($LASTEXITCODE -ne 0) { throw "First XeLaTeX pass failed." }

& $bibtex experiment_report
if ($LASTEXITCODE -ne 0) { throw "BibTeX pass failed." }

& $xelatex.Source -interaction=nonstopmode -halt-on-error experiment_report.tex
if ($LASTEXITCODE -ne 0) { throw "Second XeLaTeX pass failed." }

& $xelatex.Source -interaction=nonstopmode -halt-on-error experiment_report.tex
if ($LASTEXITCODE -ne 0) { throw "Third XeLaTeX pass failed." }

Write-Host "Compiled experiment_report.pdf successfully."
