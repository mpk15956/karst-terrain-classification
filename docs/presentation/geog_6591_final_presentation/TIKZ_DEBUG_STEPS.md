# TikZ Rendering Debug Steps

## Current Status

✅ Inkscape is installed and in PATH  
✅ Filter code has been updated for Windows compatibility  
❌ TikZ diagrams are still rendering as code blocks (filter not processing)

## Diagnosis

The filter appears to not be processing the TikZ code blocks. The HTML output shows code blocks with the class `{tikz}` but they're not being converted to images.

## Debugging Steps

### 1. Verify Filter is Being Loaded

Check if Quarto is loading the extension filter. Try rendering with verbose output:

```powershell
quarto render presentation.qmd --log-level debug 2>&1 | Select-String -Pattern "tikz|filter" -CaseSensitive:$false
```

### 2. Test a Simple Standalone TikZ Block

Create a minimal test to see if the filter runs at all. The filter should:
- Find code blocks with class `tikz`
- Compile them using pdflatex
- Convert to SVG using inkscape
- Replace code block with image

### 3. Check Filter Matching

The filter checks for `block.classes:includes('tikz')`. In the HTML, we see `class="{tikz}"`. This suggests:
- Either the filter isn't running (class preserved as-is)
- Or the filter is running but failing silently

### 4. Test Directly with Pandoc

Try processing with pandoc directly to see filter errors:

```powershell
quarto pandoc presentation.qmd --to html --filter=_extensions/danmackinlay/tikz/tikz.lua
```

### 5. Check for Error Messages

Look for errors in the Quarto output. The filter uses `quarto.log.error()` which should show errors. If no errors appear, the filter might not be running at all.

## Potential Issues

1. **Extension not auto-loading**: Quarto extensions in `_extensions/` should auto-load, but maybe there's a configuration issue
2. **Filter execution order**: The filter might be running but being overridden by another filter
3. **Silent failures**: Errors might be caught and ignored somewhere

## Quick Test

Try rendering just one TikZ diagram in a minimal file:

```qmd
---
title: Test
format: html
---

```{tikz}
\begin{tikzpicture}
  \node at (0,0) {Test};
\end{tikzpicture}
```
```

If this works, the issue is specific to the presentation format or configuration.

## Next Steps

1. Check Quarto version: `quarto --version` (needs >= 1.3.0)
2. Try explicit filter loading in YAML
3. Check if there are conflicting filters
4. Verify the extension structure matches Quarto's expectations

