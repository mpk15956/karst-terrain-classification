# Diagnostic script to check TikZ rendering dependencies for Quarto
# This script checks for pdflatex and inkscape installations

Write-Host "Checking TikZ Rendering Dependencies..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allFound = $true

# Check for pdflatex
Write-Host "Checking for pdflatex (LaTeX compiler)..." -NoNewline
try {
    $pdflatexVersion = & pdflatex --version 2>&1 | Select-Object -First 1
    if ($LASTEXITCODE -eq 0 -or $pdflatexVersion -match "pdfTeX|pdfLaTeX") {
        Write-Host " FOUND" -ForegroundColor Green
        Write-Host "  Version: $($pdflatexVersion)" -ForegroundColor Gray
    } else {
        Write-Host " NOT FOUND" -ForegroundColor Red
        $allFound = $false
    }
} catch {
    Write-Host " NOT FOUND" -ForegroundColor Red
    $allFound = $false
}

# Check for inkscape
Write-Host "Checking for inkscape (SVG converter)..." -NoNewline
try {
    $inkscapeVersion = & inkscape --version 2>&1 | Select-Object -First 1
    if ($LASTEXITCODE -eq 0 -or $inkscapeVersion -match "Inkscape") {
        Write-Host " FOUND" -ForegroundColor Green
        Write-Host "  Version: $($inkscapeVersion)" -ForegroundColor Gray
    } else {
        Write-Host " NOT FOUND" -ForegroundColor Red
        $allFound = $false
    }
} catch {
    Write-Host " NOT FOUND" -ForegroundColor Red
    $allFound = $false
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($allFound) {
    Write-Host "All dependencies are installed! TikZ rendering should work." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Missing dependencies detected. Installation instructions:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. pdflatex (LaTeX Compiler):" -ForegroundColor White
    Write-Host "   - Option A: Install TeX Live (Full LaTeX distribution)" -ForegroundColor Gray
    Write-Host "     Download: https://www.tug.org/texlive/windows.html" -ForegroundColor Gray
    Write-Host "   - Option B: Install MiKTeX (Windows-friendly)" -ForegroundColor Gray
    Write-Host "     Download: https://miktex.org/download" -ForegroundColor Gray
    Write-Host "   - Option C: Install TinyTeX (Minimal, lightweight)" -ForegroundColor Gray
    Write-Host "     In R: install.packages('tinytex'); tinytex::install_tinytex()" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Inkscape (SVG Converter):" -ForegroundColor White
    Write-Host "   - Download: https://inkscape.org/release/" -ForegroundColor Gray
    Write-Host "   - After installation, ensure it's added to PATH or restart your terminal" -ForegroundColor Gray
    Write-Host ""
    Write-Host "After installation, restart your terminal and run this script again to verify." -ForegroundColor Yellow
    exit 1
}
