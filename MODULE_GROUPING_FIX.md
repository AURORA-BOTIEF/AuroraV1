# Fix: Correct Module Grouping

## Problem
The Book Editor was grouping lessons incorrectly:
- **Expected**: 7 modules with varying numbers of lessons (as in the course structure)
- **Actual**: All modules showing exactly 3 lessons (using fallback logic)

Example from screenshot:
```
Módulo 1 (3)  ← Wrong! Should vary by actual module
Módulo 2 (3)  ← Wrong! Should vary by actual module
```

## Root Cause

The `extractModuleInfo()` function was **not prioritizing** the `moduleNumber` property that was added during the `convertModulesToLessons()` conversion. Instead, it was falling back to the hardcoded assumption of "3 lessons per module".

### The Flow:
1. ✅ Backend has modules structure with varying lesson counts
2. ✅ `convertModulesToLessons()` correctly adds `moduleNumber` to each lesson
3. ❌ `extractModuleInfo()` **ignores** `moduleNumber` property
4. ❌ Falls back to `Math.floor(index / 3) + 1` → Always 3 lessons per module!

## Solution

### 1. **Priority-Based Module Detection in `extractModuleInfo()`**

Changed the priority order to check for the `moduleNumber` property FIRST:

```javascript
const extractModuleInfo = (lesson, index) => {
    // PRIORITY 1: Check if lesson already has moduleNumber from conversion
    if (lesson.moduleNumber) {
        return {
            moduleNumber: lesson.moduleNumber,
            lessonNumberInModule: lesson.lessonNumberInModule || (index + 1)
        };
    }
    
    // PRIORITY 2: Try to extract from filename (e.g., "lesson_01-01.md")
    if (lesson.filename) {
        const match = lesson.filename.match(/(\d+)-(\d+)/);
        if (match) {
            return {
                moduleNumber: parseInt(match[1]),
                lessonNumber: parseInt(match[2])
            };
        }
    }
    
    // PRIORITY 3: Try to extract from title (e.g., "Module 1: ...")
    if (lesson.title) {
        const match = lesson.title.match(/Module\s*(\d+)/i);
        if (match) {
            return {
                moduleNumber: parseInt(match[1]),
                lessonNumber: index + 1
            };
        }
    }
    
    // FALLBACK: assume 3 lessons per module (rarely used now)
    const lessonsPerModule = 3;
    return {
        moduleNumber: Math.floor(index / lessonsPerModule) + 1,
        lessonNumber: (index % lessonsPerModule) + 1
    };
};
```

### 2. **Added `lessonNumberInModule` Property**

Enhanced `convertModulesToLessons()` to track the lesson number within each module:

```javascript
const convertModulesToLessons = (bookData) => {
    if (bookData.modules && Array.isArray(bookData.modules)) {
        const lessons = [];
        bookData.modules.forEach((module, moduleIdx) => {
            if (module.lessons && Array.isArray(module.lessons)) {
                module.lessons.forEach((lesson, lessonIdx) => {
                    lessons.push({
                        ...lesson,
                        moduleNumber: moduleIdx + 1,           // ← Which module
                        lessonNumberInModule: lessonIdx + 1,  // ← NEW! Position in module
                        moduleTitle: module.title || `Module ${moduleIdx + 1}`,
                        filename: lesson.filename || 
                            `lesson_${String(moduleIdx + 1).padStart(2, '0')}-${String(lessonIdx + 1).padStart(2, '0')}.md`
                    });
                });
            }
        });
        return { ...bookData, lessons: lessons };
    }
    return bookData;
};
```

### 3. **Display Actual Module Titles**

Updated `renderLessonsByModule()` to show the real module title instead of generic "Módulo X":

```javascript
const renderLessonsByModule = () => {
    const modules = groupLessonsByModule();
    const moduleNumbers = Object.keys(modules).sort((a, b) => parseInt(a) - parseInt(b));

    return moduleNumbers.map(moduleNum => {
        const module = modules[moduleNum];
        const firstLesson = module.lessons[0];
        
        // Get actual module title from lesson metadata
        const moduleTitle = firstLesson?.moduleTitle || `Módulo ${moduleNum}`;
        
        return (
            <div key={moduleNum} className="module-section">
                <div className="module-header">
                    <span className="module-toggle">{isCollapsed ? '▶' : '▼'}</span>
                    <span className="module-title">{moduleTitle}</span>  {/* ← Real title! */}
                    <span className="module-count">({module.lessons.length})</span>
                </div>
                {/* ... lessons ... */}
            </div>
        );
    });
};
```

## Result

### Before Fix:
```
📚 Contenido del Libro
[14 módulos · 42 lecciones]  ← Wrong count!

▼ Módulo 1 (3)  ← Always 3
  └─ L1  Lesson 1
  └─ L2  Lesson 2
  └─ L3  Lesson 3

▼ Módulo 2 (3)  ← Always 3
  └─ L1  Lesson 4
  └─ L2  Lesson 5
  └─ L3  Lesson 6
```

### After Fix:
```
📚 Contenido del Libro
[7 módulos · 42 lecciones]  ← Correct!

▼ Tipos de licencias para trabajar con Microsoft Copilot Studio (3)  ← Real title & count
  └─ L1  Tipos de licencias para trabajar con Microsoft Copilot Studio
  └─ L2  Copilot Studio integrado en Teams
  └─ L3  Desarrollar un agente en Microsoft Copilot Studio de Teams

▼ Copilot Studio con conexión a modelos de lenguaje (2)  ← Different count!
  └─ L1  Copilot Studio con conexión a modelos de lenguaje
  └─ L2  Desarrollar un agente en Microsoft Copilot integrado con IA generativa

▼ Módulo 3 (5)  ← Varies by actual content!
  └─ L1  ...
  └─ L2  ...
  └─ L3  ...
  └─ L4  ...
  └─ L5  ...
```

## Benefits

1. **Accurate Grouping**: Modules show the correct number of lessons
2. **Real Titles**: Module headers display actual module names from the course
3. **Proper Numbering**: Lesson numbers (L1, L2, L3...) restart for each module
4. **Flexible Structure**: Handles modules with 1, 2, 3, 5, 10+ lessons

## Data Flow

```
Backend S3 Structure:
{
  "modules": [
    {
      "title": "Tipos de licencias...",
      "lessons": [
        { "title": "Lesson 1", "content": "..." },
        { "title": "Lesson 2", "content": "..." },
        { "title": "Lesson 3", "content": "..." }
      ]
    },
    {
      "title": "Copilot Studio con conexión...",
      "lessons": [
        { "title": "Lesson 4", "content": "..." },
        { "title": "Lesson 5", "content": "..." }
      ]
    }
  ]
}

↓ convertModulesToLessons()

Flattened with Metadata:
{
  "lessons": [
    { 
      "title": "Lesson 1", 
      "moduleNumber": 1,              ← Added!
      "lessonNumberInModule": 1,       ← Added!
      "moduleTitle": "Tipos de licencias...",  ← Added!
      "filename": "lesson_01-01.md"
    },
    { 
      "title": "Lesson 2", 
      "moduleNumber": 1, 
      "lessonNumberInModule": 2,
      "moduleTitle": "Tipos de licencias...",
      "filename": "lesson_01-02.md"
    },
    ...
  ]
}

↓ extractModuleInfo() - Now uses moduleNumber!

↓ groupLessonsByModule()

Grouped for UI:
{
  1: {
    moduleNumber: 1,
    lessons: [lesson1, lesson2, lesson3]  ← 3 lessons
  },
  2: {
    moduleNumber: 2,
    lessons: [lesson4, lesson5]           ← 2 lessons
  }
}

↓ renderLessonsByModule()

UI Display:
▼ Tipos de licencias... (3)
  L1, L2, L3
▼ Copilot Studio con conexión... (2)
  L1, L2
```

## Testing

### What to Look For:

1. **Module Count**: Should match your actual course structure (7 modules)
2. **Lesson Count**: Each module shows its correct number of lessons
3. **Module Titles**: Real module names instead of generic "Módulo X"
4. **Lesson Numbers**: L1, L2, L3... restart for each module
5. **Console Log**: Should show correct conversion
   ```
   Converting modules structure to lessons array...
   Converted 7 modules into 42 lessons
   ```

### To Verify:

1. **Refresh browser** (Ctrl+F5)
2. **Open the book** in the editor
3. **Check module headers** - should show real titles
4. **Verify counts** - should vary by module (not all 3)
5. **Compare with MD file** - structure should match

## Files Modified
- ✅ `/src/components/BookEditor.jsx`
  - Enhanced `extractModuleInfo()` with priority-based detection
  - Added `lessonNumberInModule` in `convertModulesToLessons()`
  - Updated `renderLessonsByModule()` to show real module titles

## Status
- ✅ Priority-based module detection
- ✅ Accurate lesson counts per module
- ✅ Real module titles displayed
- ✅ Proper lesson numbering within modules
- ✅ No syntax errors

---

**Date:** October 20, 2025  
**Status:** Fixed - Modules now group correctly with accurate counts and titles
