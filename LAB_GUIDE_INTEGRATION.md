# Lab Guide Integration - Book Editor

## Overview
The Book Editor now supports viewing Lab Guides alongside the course content. Users can seamlessly toggle between the book view and the lab guide view using a button in the header.

## Features Implemented

### 1. Lab Guide Loading
- Automatically searches for `_LabGuide_complete` file in the same S3 folder as the book
- Processes S3 image URLs and converts them to data URLs for offline viewing
- Converts markdown content to HTML for rich rendering
- Silent failure if lab guide is not found (no error displayed to user)

### 2. View Toggle
- **Book View**: Shows the module-grouped lesson navigator and editor (default)
- **Lab Guide View**: Shows the lab guide content in a clean, readable format
- Toggle button in header: 
  - 🧪 Lab Guide (when viewing book)
  - 📚 Libro (when viewing lab guide)

### 3. Lab Guide Display
- Clean, distraction-free reading interface
- Properly formatted markdown rendering:
  - Headers with bottom borders
  - Code blocks with syntax highlighting
  - Images with rounded corners and shadows
  - Blockquotes with left border
  - Proper spacing and typography
- Responsive layout (max-width: 1000px)
- Scrollable content area

## Technical Implementation

### State Management
```javascript
const [labGuideData, setLabGuideData] = useState(null);
const [showLabGuide, setShowLabGuide] = useState(false);
const [viewMode, setViewMode] = useState('book');
```

### Key Functions
- `loadLabGuide()`: Fetches and processes lab guide from S3
- View mode toggle updates both `showLabGuide` and `viewMode` states
- Conditional rendering based on `showLabGuide` state

### File Naming Convention
The lab guide file must be named with the pattern `_LabGuide_complete` in the S3 book folder:
```
s3://crewai-course-artifacts/your-project/your-course-folder/_LabGuide_complete
```

## Usage

### For Users
1. Open the Book Editor for any course
2. If a lab guide exists, click the "🧪 Lab Guide" button in the header
3. View the lab guide content
4. Click "📚 Libro" to return to the book editor

### For Developers
The lab guide integration automatically handles:
- ✅ S3 authentication and file fetching
- ✅ Image URL conversion to data URLs
- ✅ Markdown to HTML conversion
- ✅ Error handling (missing files)
- ✅ Responsive styling

## CSS Classes Added
- `.lab-guide-viewer`: Main container
- `.lab-guide-header`: Header section (with gradient background)
- `.lab-guide-content`: Scrollable content area
- `.content-viewer`: Content wrapper with max-width
- `.btn-active`: Active state for toggle button
- Content-specific styles: `h1`, `h2`, `img`, `code`, `pre`, `blockquote`, etc.

## Files Modified
1. `/src/components/BookEditor.jsx` - Added lab guide functionality
2. `/src/components/BookEditor.css` - Added lab guide styling (~130 lines)

## Future Enhancements
- [ ] Edit mode for lab guides
- [ ] Search functionality within lab guides
- [ ] Download lab guide as PDF
- [ ] Table of contents for long lab guides
- [ ] Print-friendly formatting

## Testing Checklist
- ✅ Lab guide loads successfully
- ✅ Toggle button switches views
- ✅ Images display correctly
- ✅ Markdown formatting renders properly
- ✅ Scrolling works in lab guide view
- ✅ No errors if lab guide is missing
- ✅ Button styles update correctly
- ✅ Responsive layout works

## Notes
- Lab guides are read-only (no editing functionality)
- All images are converted to data URLs for offline access
- The feature gracefully handles missing lab guides
- Console logs can be used for debugging: "=== Loading Lab Guide ==="
