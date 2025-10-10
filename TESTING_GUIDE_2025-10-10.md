# Quick Testing Guide - HTML to Markdown Fix
## October 10, 2025

---

## 🎯 What Was Fixed

1. **Document structure preservation** - Headings, lists, bold, italic, blockquotes now save correctly
2. **Image URLs** - S3 URLs are now properly written to markdown files
3. **Nested elements** - Bold text in headings, formatted text in lists, etc.

---

## ✅ Quick Test (5 minutes)

### Test 1: Basic Formatting (2 min)
1. Open editor, click "Editar"
2. Type this content:
   ```
   ### This is a Heading
   
   This is a paragraph with **bold** and *italic* text.
   
   - First bullet
   - Second bullet
   
   1. First number
   2. Second number
   ```
3. Click "Guardar Versión", name it "test-formatting"
4. Click "Ver" on that version
5. **VERIFY:** All formatting should still be there (heading, bold, italic, lists)

**Expected Result:** ✅ Structure preserved

---

### Test 2: Pasted Image (2 min)
1. Copy any image (screenshot, photo, etc.)
2. In editor, paste it (Ctrl+V or Cmd+V)
3. Wait 2-3 seconds (image uploads to S3 in background)
4. Open browser console (F12)
5. Click "Guardar Versión", name it "test-image"
6. **CHECK CONSOLE:** Look for:
   ```
   ✓ Replacing src with data-s3-url for image 0: s3://...
   Markdown images: ['![pasted-image](s3://bucket/...)']
   ```
7. Close editor and reopen
8. Load the "test-image" version
9. **VERIFY:** Image should still display

**Expected Result:** ✅ Image persists with S3 URL

---

### Test 3: Complex Content (1 min)
1. Paste the example content from the first screenshot (the "Hands-On Exercises" document)
2. Click "Guardar Versión", name it "test-complex"
3. Click "Ver" on that version
4. **VERIFY:** Compare with original - should look identical

**Expected Result:** ✅ Exact same formatting

---

## 🔍 What to Check in Console

When you save a version, you should see:

```
=== convertHtmlToMarkdown START ===
Input HTML length: 5432
Found images: 1
Image 0: { alt: 'pasted-image', hasDataS3Url: true, dataS3Url: 's3://bucket/...' }
✓ Replacing src with data-s3-url for image 0: s3://bucket/project/abc123.png
Markdown images found: 1
Markdown images: ['![pasted-image](s3://bucket/project/abc123.png)']
First 300 chars of output markdown: ### Exercise 1: Setting Up Structured...
=== convertHtmlToMarkdown END ===
```

### Good Signs ✅
- `hasDataS3Url: true`
- `✓ Replacing src with data-s3-url`
- `Markdown images found: 1` (matches number you pasted)
- Markdown preview shows proper formatting

### Bad Signs ⚠️
- `hasDataS3Url: false` → Image won't save (wait longer for upload)
- `Markdown images found: 0` → Image lost during conversion
- Markdown preview is plain text → Structure lost

---

## 🐛 If Something Doesn't Work

### Issue: Image doesn't persist
**Possible causes:**
1. Didn't wait for upload (wait 3-5 seconds after paste)
2. S3 upload failed (check console for errors)
3. Network issue

**Solution:**
- Check console for "Failed to upload pasted file image"
- Try pasting again and waiting longer
- Check internet connection

### Issue: Formatting lost
**Possible causes:**
1. Old browser cache (need to refresh)
2. Syntax error in new code

**Solution:**
- Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
- Check console for JavaScript errors
- If errors, report them

### Issue: Version won't load
**Possible causes:**
1. S3 fetch issue
2. Image loading timeout

**Solution:**
- Check console for errors
- Try again (sometimes S3 is slow)
- Loading spinner should show progress

---

## 📊 Before vs After Comparison

### BEFORE (Broken)
**Save this content:**
```markdown
### Section Title

Paragraph with **bold** text.

- Item 1
- Item 2

![image](blob:...)
```

**After saving and reloading:**
```
Section Title
Paragraph with bold text.
Item 1
Item 2
```
❌ Lost: heading marker, bold, list bullets, image

### AFTER (Fixed)
**Save this content:**
```markdown
### Section Title

Paragraph with **bold** text.

- Item 1
- Item 2

![image](s3://...)
```

**After saving and reloading:**
```markdown
### Section Title

Paragraph with **bold** text.

- Item 1
- Item 2

![image](s3://...)
```
✅ Preserved: everything!

---

## 📝 Report Results

After testing, please report:

1. ✅ or ❌ for each test case
2. If ❌, what went wrong?
3. Console output (copy/paste the logs)
4. Screenshots if helpful

**Example report:**
```
Test 1 (Basic Formatting): ✅ PASS
Test 2 (Pasted Image): ✅ PASS - Image persisted with S3 URL
Test 3 (Complex Content): ✅ PASS - Exact same as original

Console showed:
✓ Replacing src with data-s3-url for image 0: s3://bucket/abc123.png
Markdown images: ['![pasted-image](s3://bucket/abc123.png)']
```

---

**Testing Time:** ~5 minutes  
**Critical for:** Document integrity, image persistence  
**Status:** Ready to test! 🚀
