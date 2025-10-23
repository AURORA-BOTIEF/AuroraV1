# Image and List Rendering Fixes

## Date: October 20, 2025

## Issues Fixed

### 1. Images Showing as Base64 Code in Gray Sections

**Problem:**
- Lines containing image markdown with long base64 data URLs (e.g., `![VISUAL: 01-05-0019](data:image/png;base64,iVBORw0KG...`)
- Were appearing as text in gray `<pre>` boxes instead of rendering as images
- The regex pattern `/!\[{1,2}([^\]]*)\]{1,2}\(([^)]+)\)/` was failing to match very long data URLs

**Root Cause:**
- The regex pattern `[^)]+` is designed to match everything except `)`, but with extremely long base64 strings (thousands of characters), the regex engine was struggling
- Lines were falling through to the "regular text" handler and being wrapped in `<p>` tags
- The styled paragraphs appeared in gray boxes due to CSS styling

**Solution:**
- Replaced regex-based image detection with string parsing approach
- New method uses `indexOf()` to find `![`, `](`, and `)` positions
- Manually extracts alt text and src URL regardless of length
- Handles both single and double bracket formats: `![alt](url)` and `![[VISUAL: desc]](url)`

**Implementation:**
```javascript
// Old approach (failed on long URLs):
const imgMatch = line.match(/!\[{1,2}([^\]]*)\]{1,2}\(([^)]+)\)/);

// New approach (handles any length):
if (line.includes('![') && line.includes('](')) {
    const imgStartIdx = line.indexOf('![');
    const imgEndBracketIdx = line.indexOf('](', imgStartIdx);
    
    // Extract alt text
    let altStartIdx = imgStartIdx + 2;
    let altEndIdx = imgEndBracketIdx;
    if (line[altStartIdx] === '[') { /* handle double brackets */ }
    const alt = line.substring(altStartIdx, altEndIdx).trim();
    
    // Extract URL (handles URLs of any length)
    const srcStartIdx = imgEndBracketIdx + 2;
    let srcEndIdx = line.indexOf(')', srcStartIdx);
    if (srcEndIdx === -1) srcEndIdx = line.length;
    const src = line.substring(srcStartIdx, srcEndIdx).trim();
    
    // Render image
    out += `<p style="text-align: center;"><img alt="${alt}" src="${src}" ... /></p>`;
}
```

**Benefits:**
- Handles data URLs of unlimited length
- More reliable than regex for edge cases
- Better performance on very long strings
- Supports both `![alt]` and `![[VISUAL: alt]]` formats

### 2. Empty Numbered Items in Lab Guide

**Problem:**
- Steps 6 and 13 in the Lab Guide were showing just numbers with no content
- Lines like `6. '''` or `13. """` were being processed
- The triple quotes were removed by `applyInlineFormatting()`, leaving empty list items
- Rendered as: `<li></li>` which displayed as just a number

**Root Cause:**
- Ordered list regex matched lines like `6. '''`
- The content `'''` was extracted and passed to `applyInlineFormatting()`
- Inline formatting removed the `'''` (as designed), leaving empty string
- Empty `<li>` elements were still rendered with numbering

**Solution:**
- Added validation in ordered and unordered list item handlers
- Check if item content is empty or contains only fence markers
- Skip rendering empty list items entirely

**Implementation:**
```javascript
// Ordered list item handler
const ol = line.match(/^(\s*)\d+\.\s+(.*)$/);
if (ol) {
    const itemContent = ol[2].trim();
    
    // Skip empty list items
    if (!itemContent || 
        itemContent === "'''" || 
        itemContent === '"""' || 
        itemContent === '```') {
        continue; // Don't render this item
    }
    
    // ... normal list item rendering
    out += `<li>${applyInlineFormatting(itemContent)}</li>`;
}

// Same logic applied to unordered lists
```

**Benefits:**
- Cleaner output - no empty numbered items
- Prevents confusion from seeing "6." with no content
- Maintains proper numbering sequence (skips to next valid item)
- Consistent behavior for both ordered and unordered lists

## Technical Details

### Image Detection Flow

**Before:**
1. Regex attempts to match entire pattern in one pass
2. Fails on very long URLs (thousands of characters)
3. Line falls through to paragraph handler
4. Gets wrapped as `<p>![VISUAL: ...](...very long base64...)</p>`
5. CSS styling makes it appear in gray box

**After:**
1. Quick check: Does line contain `![` and `](`?
2. Use string indexing to find positions
3. Extract alt and src substrings
4. Validate src exists
5. Render as `<img>` tag immediately
6. Skip paragraph handler entirely

### List Item Filtering

**Processing Order:**
1. Regex matches list item: `6. '''`
2. Extract content: `'''`
3. **NEW:** Check if content is empty/invalid
4. If invalid, `continue` to next line (skip rendering)
5. If valid, apply inline formatting and render

**Skipped Patterns:**
- Empty content: `6. ` (just whitespace)
- Only triple quotes: `6. '''`, `6. """`, `6. ` ` ` ``
- These are likely formatting artifacts or placeholder lines

## Testing Instructions

### Test Image Rendering

1. **Refresh browser** at http://localhost:5173/
2. Navigate to "Lesson 3: Desarrollar un agente en Microsoft Copilot Studio de Teams"
3. Look for the section with "Fase 4: Orquestación Avanzada y Lógica de Negocio"
4. **Expected behavior:**
   - Images should render as actual images (centered, proper size)
   - NO base64 code should be visible
   - NO gray boxes containing `![VISUAL: ...]` text
5. **Look for:** Visual images displaying between the text sections

### Test List Items

1. Switch to **Lab Guide** view
2. Navigate to the section with numbered steps
3. **Expected behavior:**
   - No empty numbered items (e.g., just "6." with nothing)
   - Steps should jump from 5 → 7 if 6 was empty
   - All visible numbered items should have content
4. **Specifically check:** Steps 6 and 13 from the previous issue

### Verification Checklist

- [ ] Images render as pictures, not as code
- [ ] No `![VISUAL: ...]` text visible
- [ ] No long base64 strings in gray boxes
- [ ] No empty numbered list items
- [ ] List numbering is sequential (only for non-empty items)
- [ ] Table formatting still works (from previous fix)
- [ ] Code blocks still render in gray boxes (actual code, not images)

## Files Modified

- `/src/components/BookEditor.jsx`
  - `formatContentForEditing()` function
    - Image detection: Replaced regex with substring parsing
    - Ordered list handler: Added empty item filtering
    - Unordered list handler: Added empty item filtering

## Related Documentation

- See `MARKDOWN_FIXES_COMPLETE.md` for previous fixes (triple quotes, tables, bold text)
- See `LAB_GUIDE_IMPROVEMENTS.md` for Lab Guide version control

## Performance Impact

**Positive:**
- String operations (`indexOf`, `substring`) are faster than complex regex on long strings
- Reduced regex backtracking on failed matches
- Faster rendering of pages with many images

**Neutral:**
- Minimal impact on pages without images
- List filtering adds negligible overhead (simple string comparison)
