# Book Editor Fixes - October 10, 2025

## Summary of Issues Fixed

This document details the fixes applied to the Book Editor component to resolve critical bugs reported on October 10, 2025.

---

## 1. ✅ Pasted Image Display Issue

**Problem:** 
When pasting images into the editor, they showed "pasted-image" alt text but didn't load/display properly after upload.

**Root Cause:**
After uploading images to S3, the editor was using the direct S3 URL which doesn't work for private buckets without proper authentication for display.

**Solution:**
- Modified the paste handler in `BookEditor.jsx` to fetch uploaded S3 images as blob URLs using `getBlobUrlForS3Object()` 
- Added `data-s3-url` attribute to store the original S3 URL while displaying the blob URL
- Updated `convertHtmlToMarkdown()` to extract and use the S3 URL (not blob URL) when saving

**Files Changed:**
- `src/components/BookEditor.jsx` - Updated handlePaste and convertHtmlToMarkdown functions

**Code Changes:**
```javascript
// Now fetches blob URL for display after S3 upload
const displayUrl = await getBlobUrlForS3Object(s3Url);
img.src = displayUrl;
img.setAttribute('data-s3-url', s3Url); // Store for saving
```

---

## 2. ✅ Version Saving with Data URLs Instead of S3 URLs

**Problem:**
Saved versions included base64-encoded images (data URLs) instead of clean S3 URLs, making files unnecessarily large and inconsistent with original format.

**Root Cause:**
The `saveVersion()` function was saving whatever was in memory, including any blob/data URLs used for display.

**Solution:**
- Updated `saveVersion()` to process current edits and convert any data URLs to S3 URLs before saving
- Ensured all lesson content is uploaded to S3 as images before creating the version
- Simplified upload logic to use direct `PutObjectCommand` instead of multipart upload

**Files Changed:**
- `src/components/BookEditor.jsx` - Updated saveVersion function

**Code Changes:**
```javascript
// Upload any inline images before saving version
const { replaceDataUrlsWithS3Urls } = await import('../utils/s3ImageLoader');
html = await replaceDataUrlsWithS3Urls(html, projectFolder);

// Use simple PutObjectCommand for faster upload
await s3.send(new PutObjectCommand({
    Bucket: bucketName,
    Key: versionKey,
    Body: JSON.stringify(versionData, null, 2),
    ContentType: 'application/json',
}));
```

---

## 3. ✅ Version Viewing Not Showing Saved Content

**Problem:**
When clicking "Ver" to view a specific version, it didn't show the actual saved version content - it was loading fragments or incorrect data.

**Root Cause:**
- `viewVersion()` was trying to load markdown snapshot first, which might not exist or be out of sync
- `editVersion()` wasn't processing images properly when loading version data
- The version wasn't showing all lessons, only showing the JSON or partial content

**Solution:**
- Updated `viewVersion()` to load the JSON version and generate full markdown from all lessons
- Updated `editVersion()` to properly process all lesson images using `replaceS3UrlsWithDataUrls()` for display
- Both functions now show the complete book with all lessons

**Files Changed:**
- `src/components/BookEditor.jsx` - Updated viewVersion and editVersion functions

**Code Changes:**
```javascript
// viewVersion - Generate markdown from full book
const parsedVersion = JSON.parse(jsonText);
const markdown = generateMarkdownFromBook(parsedVersion);
setViewingContent(markdown);

// editVersion - Process images in all lessons
for (let lesson of parsed.lessons || []) {
    if (lesson.content) {
        lesson.content = await replaceS3UrlsWithDataUrls(lesson.content);
    }
}
```

---

## 4. ✅ Slow Save Performance and Upload Errors

**Problem:**
- Saving took 6+ seconds from clicking "Guardar Versión" to seeing success message
- Console showed error: "The upload was created using a crc32 checksum. The complete request must include the checksum for each part."

**Root Cause:**
- Used `@aws-sdk/lib-storage` Upload class with multipart uploads
- Multipart uploads require CRC32 checksums for each part
- This added complexity, slower performance, and error-prone behavior for small/medium files

**Solution:**
- Removed `@aws-sdk/lib-storage` dependency from upload logic
- Changed to direct `PutObjectCommand` which is faster and simpler for files under 5GB
- Applied to both `saveBook()` and `saveVersion()` functions
- Removed unnecessary fallback logic and retry complexity

**Files Changed:**
- `src/components/BookEditor.jsx` - Updated saveBook and saveVersion functions
- Removed import of `Upload` from `@aws-sdk/lib-storage`

**Performance Impact:**
- Expected save time reduced from 6+ seconds to ~1-2 seconds
- No more CRC32 checksum errors
- Simpler, more maintainable code

**Code Changes:**
```javascript
// Before: Complex multipart upload
const uploader = new Upload({
    client: s3,
    params: { ... },
    queueSize: 4,
    partSize: Math.min(MAX_SINGLE_PUT, ...),
});
await uploader.done();

// After: Simple direct upload
await s3.send(new PutObjectCommand({
    Bucket: bucketName,
    Key: s3Key,
    Body: bookJson,
    ContentType: 'application/json',
}));
```

---

## 5. ✅ Async Message Channel Error

**Problem:**
Console error: "Uncaught (in promise) Error: A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received"

**Root Cause:**
This is a common browser extension error (often from Chrome extensions) that doesn't affect the application but clutters the console and can be alarming to users.

**Solution:**
- Added global error handlers in `main.jsx` to suppress these specific extension-related errors
- Errors are logged as warnings instead of uncaught errors
- Application functionality is unaffected

**Files Changed:**
- `src/main.jsx` - Added error and unhandledrejection event listeners

**Code Changes:**
```javascript
// Suppress browser extension errors
window.addEventListener('error', (event) => {
    if (event.message && event.message.includes('message channel closed')) {
        console.warn('Suppressed browser extension error:', event.message);
        event.preventDefault();
        return false;
    }
});

window.addEventListener('unhandledrejection', (event) => {
    if (event.reason && String(event.reason).includes('message channel closed')) {
        console.warn('Suppressed async browser extension error:', event.reason);
        event.preventDefault();
        return false;
    }
});
```

---

## Testing Recommendations

After deploying these fixes, please test:

1. **Image Pasting:**
   - Paste images from clipboard
   - Verify they display immediately
   - Verify they're uploaded to S3 in background
   - Check that final saved content has S3 URLs not data URLs

2. **Version Saving:**
   - Create a new version with "Guardar Versión"
   - Verify it completes in ~1-2 seconds (not 6+ seconds)
   - Check S3 to confirm version file uses S3 URLs for images
   - Verify no CRC32 errors in console

3. **Version Viewing:**
   - Click "Ver" on a saved version
   - Verify it shows the complete markdown with all lessons
   - Verify all images load correctly
   - Click "Editar" on a version
   - Verify all lessons are editable and images display

4. **Console Errors:**
   - Check that "message channel closed" errors no longer appear as uncaught
   - Verify they appear as warnings if present (not breaking)

---

## Additional Notes

### Image Display Strategy
The editor now uses a two-tier approach for images:
- **Display:** Uses blob URLs created from authenticated S3 GetObject calls
- **Storage:** Uses canonical S3 URLs (https://bucket.s3.amazonaws.com/path)

This ensures:
- Images work in private S3 buckets
- Saved content is portable and uses standard URLs
- Memory is managed (blob URLs should be revoked when no longer needed)

### Performance Improvements
By removing multipart uploads for book/version saves:
- Simpler code (less error-prone)
- Faster uploads (no part management overhead)
- No checksum complexity
- Better for files < 100MB (which covers all typical use cases)

### Future Considerations
1. Consider implementing blob URL cleanup when images are removed from editor
2. Add progress indicator during version save for better UX
3. Consider adding version comparison feature (diff between versions)
4. May want to implement automatic version naming based on timestamp

---

## Files Modified Summary

1. `src/components/BookEditor.jsx` - Major refactor of upload, save, and version management
2. `src/main.jsx` - Added global error handlers for browser extension errors

## Dependencies Changed

- Removed usage of `@aws-sdk/lib-storage` Upload class
- All uploads now use `@aws-sdk/client-s3` PutObjectCommand directly

---

**Date:** October 10, 2025  
**Developer:** GitHub Copilot  
**Status:** ✅ All fixes applied and ready for testing
