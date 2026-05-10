# TikZ Rendering Diagnosis and Fix

## Problem Identified

TikZ diagrams are not rendering because:

1. **Inkscape not in PATH**: Inkscape is installed at `C:\Program Files\Inkscape\bin\inkscape.exe` but not accessible via PATH
2. **Filter uses Unix command check**: The original filter used `command -v` which doesn't work on Windows
3. **Silent failures**: When dependencies aren't found, the filter fails silently and leaves code blocks as-is

## Fixes Applied

### 1. Updated Dependency Detection (`tikz.lua`)

I've modified the filter to:
- Use cross-platform command detection (Windows `where.exe` + Unix `command -v`)
- Check common Windows installation paths for Inkscape
- Use full paths to commands instead of relying on PATH

**Changes made to**: `docs/presentation/_extensions/danmackinlay/tikz/tikz.lua`

### 2. Added TikZ Configuration

Added caching configuration to `presentation.qmd` YAML header:
```yaml
tikz:
  cache: true
```

## Next Steps

### Option 1: Add Inkscape to PATH (Recommended)

Add Inkscape to your system PATH so it's accessible everywhere:

1. Open System Properties → Advanced → Environment Variables
2. Edit "Path" under "System variables"
3. Add: `C:\Program Files\Inkscape\bin`
4. Restart your terminal/IDE
5. Verify: Run `inkscape --version` in a new terminal

### Option 2: Verify the Filter Fix Works

The filter should now automatically find Inkscape even if not in PATH. Test by:

```powershell
cd docs/presentation
quarto render presentation.qmd
```

Check for any error messages. If you see TikZ diagrams rendered as images, the fix worked!

### Option 3: Check for Error Messages

If diagrams still don't render, check the Quarto output for error messages. The filter now logs errors instead of failing silently. Look for messages like:
- "Error compiling TikZ figure..."
- "pdflatex not found..."
- "Inkscape not found..."

## Testing

Try rendering the test document:

```powershell
cd docs/presentation
quarto render test_tikz.qmd
```

Then check `test_tikz.html` - if you see images instead of code blocks, TikZ rendering is working!

## Current Status

- ✅ Filter updated to find Inkscape automatically
- ✅ Cross-platform dependency detection implemented  
- ✅ TikZ configuration added to presentation
- ⏳ Waiting to test if rendering works now

The filter should now work even if Inkscape isn't in PATH. However, adding it to PATH is still recommended for better compatibility.
