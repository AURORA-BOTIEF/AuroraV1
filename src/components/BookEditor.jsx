// src/components/BookEditor.jsx
import React, { useState, useEffect, useRef } from 'react';
import { replaceS3UrlsWithDataUrls, uploadImageToS3 } from '../utils/s3ImageLoader';
import { S3Client, PutObjectCommand, ListObjectsV2Command, GetObjectCommand } from '@aws-sdk/client-s3';
import { fetchAuthSession } from 'aws-amplify/auth';
import './BookEditor.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;
const IDENTITY_POOL_ID = import.meta.env.VITE_IDENTITY_POOL_ID || import.meta.env.VITE_AWS_IDENTITY_POOL_ID || '';
const AWS_REGION = import.meta.env.VITE_AWS_REGION || 'us-east-1';

function BookEditor({ projectFolder, bookType = 'theory', onClose }) {
    const [bookData, setBookData] = useState(null);
    const [originalBookData, setOriginalBookData] = useState(null); // Store original for "Original" version
    const [loading, setLoading] = useState(true);
    const [loadingImages, setLoadingImages] = useState(false);
    const [saving, setSaving] = useState(false);
    const [currentLessonIndex, setCurrentLessonIndex] = useState(0);
    const [isEditing, setIsEditing] = useState(false);
    const [versions, setVersions] = useState([]);
    const [labGuideVersions, setLabGuideVersions] = useState([]);
    const [sessionVersionKey, setSessionVersionKey] = useState(null);
    const [showVersionHistory, setShowVersionHistory] = useState(false);
    const [newVersionName, setNewVersionName] = useState('');
    const [newLabGuideVersionName, setNewLabGuideVersionName] = useState('');
    const [viewingVersion, setViewingVersion] = useState(null);
    const [viewingContent, setViewingContent] = useState('');
    const [loadingVersion, setLoadingVersion] = useState(false);
    const editorRef = useRef(null);
    const lastAppliedLessonRef = useRef({ index: null, content: null, isEditing: null });
    const lastAppliedLabGuideRef = useRef({ isEditing: null, content: null });
    const [editingHtml, setEditingHtml] = useState(null);
    const [labGuideEditingHtml, setLabGuideEditingHtml] = useState(null);
    const selectionRef = useRef(null);
    const [collapsedModules, setCollapsedModules] = useState({});
    const [labGuideData, setLabGuideData] = useState(null);
    const [showLabGuide, setShowLabGuide] = useState(false);
    const [viewMode, setViewMode] = useState('book'); // 'book' or 'lab'
    // PPT Generation states
    const [showPPTModal, setShowPPTModal] = useState(false);
    const [pptGenerating, setPptGenerating] = useState(false);
    const [selectedPPTVersion, setSelectedPPTVersion] = useState('current');
    const [pptStyle, setPptStyle] = useState('professional');
    const [slidesPerLesson, setSlidesPerLesson] = useState(6);
    const [pptModelProvider, setPptModelProvider] = useState('bedrock');
    // (Quill removed) we prefer Lexical editor; contentEditable is fallback

    // Function to extract module number from lesson filename or title
    const extractModuleInfo = (lesson, index) => {
        // PRIORITY 1: Check if lesson already has moduleNumber from conversion
        if (lesson.moduleNumber) {
            return {
                moduleNumber: lesson.moduleNumber,
                lessonNumber: lesson.lessonNumberInModule || (index + 1)
            };
        }

        // PRIORITY 2: Try to extract from filename (e.g., "lesson_01-01.md" or "01-01-lesson.md")
        if (lesson.filename) {
            const match = lesson.filename.match(/(\d+)-(\d+)/);
            if (match) {
                return {
                    moduleNumber: parseInt(match[1]),
                    lessonNumber: parseInt(match[2])
                };
            }
        }

        // PRIORITY 3: Try to extract from title (e.g., "Module 1: Lesson 2 - Title")
        if (lesson.title) {
            const match = lesson.title.match(/Module\s*(\d+)/i);
            if (match) {
                return {
                    moduleNumber: parseInt(match[1]),
                    lessonNumber: index + 1
                };
            }
        }

        // FALLBACK: assume 3 lessons per module if no clear structure
        const lessonsPerModule = 3;
        return {
            moduleNumber: Math.floor(index / lessonsPerModule) + 1,
            lessonNumber: (index % lessonsPerModule) + 1
        };
    };

    // Group lessons by module
    const groupLessonsByModule = () => {
        if (!bookData || !bookData.lessons || !Array.isArray(bookData.lessons)) return {};

        const modules = {};
        bookData.lessons.forEach((lesson, index) => {
            const { moduleNumber } = extractModuleInfo(lesson, index);
            if (!modules[moduleNumber]) {
                modules[moduleNumber] = {
                    moduleNumber,
                    lessons: []
                };
            }
            modules[moduleNumber].lessons.push({
                ...lesson,
                originalIndex: index
            });
        });

        return modules;
    };    // Toggle module collapse state
    const toggleModule = (moduleNumber) => {
        setCollapsedModules(prev => ({
            ...prev,
            [moduleNumber]: !prev[moduleNumber]
        }));
    };

    // Toggle all modules at once
    const toggleAllModules = () => {
        const modules = groupLessonsByModule();
        const moduleNumbers = Object.keys(modules);
        const anyCollapsed = moduleNumbers.some(num => collapsedModules[num]);

        const newState = {};
        moduleNumbers.forEach(num => {
            newState[num] = !anyCollapsed; // If any collapsed, expand all; otherwise collapse all
        });
        setCollapsedModules(newState);
    };

    // Render lessons grouped by module
    const renderLessonsByModule = () => {
        const modules = groupLessonsByModule();
        const moduleNumbers = Object.keys(modules).sort((a, b) => parseInt(a) - parseInt(b));

        return moduleNumbers.map(moduleNum => {
            const module = modules[moduleNum];
            const isCollapsed = collapsedModules[moduleNum];

            // Get module title from first lesson's moduleTitle property, or use default
            const firstLesson = module.lessons[0];
            const moduleTitle = firstLesson?.moduleTitle || `Módulo ${moduleNum}`;

            return (
                <div key={moduleNum} className="module-section">
                    <div
                        className="module-header"
                        onClick={() => toggleModule(moduleNum)}
                    >
                        <span className="module-toggle">{isCollapsed ? '▶' : '▼'}</span>
                        <span className="module-title">{moduleTitle}</span>
                        <span className="module-count">({module.lessons.length})</span>
                    </div>
                    {!isCollapsed && (
                        <div className="module-lessons">
                            {module.lessons.map((lesson) => (
                                <div
                                    key={lesson.originalIndex}
                                    className={`lesson-item ${lesson.originalIndex === currentLessonIndex ? 'active' : ''}`}
                                    onClick={() => setCurrentLessonIndex(lesson.originalIndex)}
                                >
                                    <span className="lesson-number">L{lesson.lessonNumberInModule || extractModuleInfo(lesson, lesson.originalIndex).lessonNumber}</span>
                                    <span className="lesson-title-text">{lesson.title || `Lección ${lesson.originalIndex + 1}`}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            );
        });
    };

    useEffect(() => {
        if (projectFolder) {
            loadBook();
            loadVersions();
            loadLabGuide();
            loadLabGuideVersions();
        }
    }, [projectFolder]);

    // ReactQuill removed; lexical is preferred

    // Dynamically import Lexical editor wrapper (preferred editor)
    const [LexicalEditorWrapper, setLexicalEditorWrapper] = React.useState(null);
    const [useLexical, setUseLexical] = React.useState(false);
    useEffect(() => {
        let mounted = true;
        (async () => {
            try {
                const mod = await import('./LexicalEditorWrapper');
                if (mounted) {
                    setLexicalEditorWrapper(() => mod.default);
                    setUseLexical(true);
                }
            } catch (e) {
                console.warn('Lexical dynamic import failed, falling back to other editors:', e);
                setUseLexical(false);
            }
        })();
        return () => { mounted = false; };
    }, []);

    const loadBook = async () => {
        try {
            setLoading(true);
            setLoadingImages(true);

            const response = await fetch(`${API_BASE}/load-book/${projectFolder}?bookType=${bookType}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Load book error:', errorText);
                throw new Error(`No se pudo cargar los datos del libro: ${response.status}`);
            }

            const data = await response.json();

            console.log('=== Book Data Response ===');
            console.log('Keys:', Object.keys(data));
            console.log('Has bookData:', !!data.bookData);
            console.log('Has bookContent:', !!data.bookContent);
            console.log('Has bookJsonUrl:', !!data.bookJsonUrl);
            console.log('Has bookMdUrl:', !!data.bookMdUrl);

            if (data.bookData) {
                console.log('bookData structure:', {
                    keys: Object.keys(data.bookData),
                    hasLessons: !!data.bookData.lessons,
                    lessonsIsArray: Array.isArray(data.bookData.lessons),
                    lessonsCount: data.bookData.lessons ? data.bookData.lessons.length : 'N/A'
                });
            }

            let bookToSet = null;

            // Helper function to convert modules structure to lessons array
            const convertModulesToLessons = (bookData) => {
                if (bookData.modules && Array.isArray(bookData.modules)) {
                    console.log('Converting modules structure to lessons array...');
                    const lessons = [];
                    bookData.modules.forEach((module, moduleIdx) => {
                        // Handle both 'lessons' (theory) and 'labs' (lab guides)
                        const items = module.lessons || module.labs;
                        if (items && Array.isArray(items)) {
                            items.forEach((item, itemIdx) => {
                                lessons.push({
                                    ...item,
                                    moduleNumber: moduleIdx + 1,
                                    lessonNumberInModule: itemIdx + 1,
                                    moduleTitle: module.module_title || module.title || `Module ${moduleIdx + 1}`,
                                    // Ensure filename follows the pattern for module grouping
                                    filename: item.filename || `lesson_${String(moduleIdx + 1).padStart(2, '0')}-${String(itemIdx + 1).padStart(2, '0')}.md`
                                });
                            });
                        }
                    });
                    console.log(`Converted ${bookData.modules.length} modules into ${lessons.length} lessons (or labs)`);
                    return {
                        ...bookData,
                        lessons: lessons,
                        metadata: {
                            ...(bookData.metadata || {}),
                            total_lessons: lessons.length,
                            total_modules: bookData.modules.length
                        }
                    };
                }
                return bookData;
            };

            // Priority: inline bookData > inline bookContent > presigned URLs
            if (data.bookData) {
                console.log('Processing book data...');

                // Check if we have modules structure instead of lessons
                if (!data.bookData.lessons && data.bookData.modules) {
                    data.bookData = convertModulesToLessons(data.bookData);
                }

                // Ensure lessons is an array
                if (data.bookData.lessons && Array.isArray(data.bookData.lessons)) {
                    // Set book data immediately WITHOUT waiting for images
                    bookToSet = data.bookData;
                    setBookData(bookToSet);
                    setOriginalBookData(JSON.parse(JSON.stringify(bookToSet)));
                    setLoading(false); // Show UI immediately

                    // Load images progressively in the background
                    console.log('Loading images progressively in background...');
                    setLoadingImages(true);

                    // Process images for current lesson first (priority)
                    const currentLesson = bookToSet.lessons[0];
                    if (currentLesson && currentLesson.content) {
                        console.log('Loading images for current lesson (priority)...');
                        currentLesson.content = await replaceS3UrlsWithDataUrls(currentLesson.content);
                        setBookData({ ...bookToSet }); // Trigger re-render
                    }

                    // Then load remaining lessons in background
                    setTimeout(async () => {
                        for (let i = 1; i < bookToSet.lessons.length; i++) {
                            const lesson = bookToSet.lessons[i];
                            if (lesson.content) {
                                lesson.content = await replaceS3UrlsWithDataUrls(lesson.content);
                                // Update state every few lessons to show progress
                                if (i % 5 === 0 || i === bookToSet.lessons.length - 1) {
                                    setBookData({ ...bookToSet });
                                }
                            }
                        }
                        console.log('All images loaded');
                        setLoadingImages(false);
                    }, 100);

                    return; // Exit early since we've set the state
                } else {
                    console.error('bookData.lessons is not an array or is missing:', data.bookData);
                    throw new Error('El formato del libro no es válido: lessons no es un array');
                }
            } else if (data.bookContent) {
                // Replace S3 URLs with data URLs before parsing
                console.log('Loading images from S3 (inlined bookContent)...');
                const contentWithImages = await replaceS3UrlsWithDataUrls(data.bookContent);
                const parsedBook = parseMarkdownToBook(contentWithImages);
                bookToSet = parsedBook;
            } else if (data.bookJsonUrl) {
                // Fetch JSON via presigned URL
                console.log('Fetching book JSON from presigned URL...');
                const jsonResp = await fetch(data.bookJsonUrl);
                if (!jsonResp.ok) throw new Error('Failed to fetch book JSON from S3');
                let fetchedJson = await jsonResp.json();

                // Check if we have modules structure instead of lessons
                if (!fetchedJson.lessons && fetchedJson.modules) {
                    fetchedJson = convertModulesToLessons(fetchedJson);
                }

                // Ensure lessons exists and is an array
                if (!fetchedJson.lessons || !Array.isArray(fetchedJson.lessons)) {
                    console.error('Fetched JSON lessons is not valid:', fetchedJson);
                    throw new Error('El formato del libro no es válido: lessons no es un array');
                }
                // Process images
                for (let lesson of fetchedJson.lessons) {
                    if (lesson.content) lesson.content = await replaceS3UrlsWithDataUrls(lesson.content);
                }
                bookToSet = fetchedJson;
            } else if (data.bookMdUrl) {
                // Fetch markdown via presigned URL and parse
                console.log('Fetching book markdown from presigned URL...');
                const mdResp = await fetch(data.bookMdUrl);
                if (!mdResp.ok) throw new Error('Failed to fetch book markdown from S3');
                const markdown = await mdResp.text();
                const contentWithImages = await replaceS3UrlsWithDataUrls(markdown);
                const parsedBook = parseMarkdownToBook(contentWithImages);
                bookToSet = parsedBook;
            } else {
                throw new Error('No hay datos del libro disponibles');
            }

            setBookData(bookToSet);
            setOriginalBookData(JSON.parse(JSON.stringify(bookToSet))); // Deep copy for original
            setLoadingImages(false);
        } catch (error) {
            console.error('Error al cargar libro:', error);
            alert('Error al cargar libro: ' + error.message);
            setLoadingImages(false);
        } finally {
            setLoading(false);
        }
    };

    const loadLabGuide = async () => {
        try {
            console.log('=== Loading Lab Guide ===');

            // Get authenticated credentials from Amplify
            const session = await fetchAuthSession();
            if (!session || !session.credentials) {
                console.log('No credentials available for lab guide loading');
                return;
            }

            const s3 = new S3Client({
                region: AWS_REGION,
                credentials: session.credentials,
            });

            const bucketName = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';
            const labGuidePrefix = `${projectFolder}/book/`;

            // List files in the book folder to find lab guide
            const response = await s3.send(new ListObjectsV2Command({
                Bucket: bucketName,
                Prefix: labGuidePrefix,
                MaxKeys: 50
            }));

            if (!response.Contents) {
                console.log('No contents found in book folder');
                return;
            }

            console.log('Files in book folder:');
            response.Contents.forEach(obj => {
                console.log('  -', obj.Key);
            });

            // Look for lab guide file (_LabGuide_complete)
            const labGuideFile = response.Contents.find(obj =>
                obj.Key && obj.Key.includes('_LabGuide_complete')
            );

            if (!labGuideFile) {
                console.log('No lab guide file found. Searched for files containing "_LabGuide_complete"');
                console.log('Available files:', response.Contents.map(obj => obj.Key).join(', '));
                return;
            }

            console.log('Found lab guide:', labGuideFile.Key);

            // Download the lab guide content
            const labGuideResponse = await s3.send(new GetObjectCommand({
                Bucket: bucketName,
                Key: labGuideFile.Key
            }));

            const labGuideContent = await labGuideResponse.Body.transformToString();

            // Process images in lab guide content
            console.log('Processing images in lab guide...');
            const contentWithImages = await replaceS3UrlsWithDataUrls(labGuideContent);

            setLabGuideData({
                content: contentWithImages,
                filename: labGuideFile.Key.split('/').pop(),
                lastModified: labGuideFile.LastModified
            });

            console.log('Lab guide loaded successfully');
        } catch (error) {
            console.error('Error loading lab guide:', error);
            // Don't show alert - lab guide is optional
        }
    };

    const saveLabGuide = async () => {
        if (!labGuideData) {
            alert('No hay guía de laboratorios cargada');
            return;
        }

        if (!newLabGuideVersionName.trim()) {
            alert('Por favor ingresa un nombre para la versión del Lab Guide');
            return;
        }

        try {
            console.log('=== Saving Lab Guide Version ===');

            const safeVersionName = newLabGuideVersionName.replace(/\s+/g, '_');
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const versionFilename = `${labGuideData.filename.replace('.md', '')}_${safeVersionName}_${timestamp}.md`;

            // Get authenticated credentials
            const session = await fetchAuthSession();
            if (!session || !session.credentials) {
                throw new Error('No se encontraron credenciales autenticadas');
            }

            const s3 = new S3Client({
                region: AWS_REGION,
                credentials: session.credentials,
            });

            const bucketName = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';

            // Get the current content - use editing HTML if available
            const currentContent = labGuideEditingHtml || labGuideData.content;

            // Convert HTML back to markdown for storage
            const markdown = convertHtmlToMarkdown(currentContent);

            // Save as a version in lab-versions folder
            const versionKey = `${projectFolder}/lab-versions/${versionFilename}`;

            // Check if version with this name already exists
            const existingVersion = labGuideVersions.find(v => v.name.includes(safeVersionName));
            if (existingVersion) {
                const override = confirm(`Ya existe una versión con el nombre "${newLabGuideVersionName}".\n\n¿Deseas sobrescribirla?`);
                if (!override) {
                    return;
                }
            }

            console.log('Saving lab guide version to:', versionKey);

            // Upload to S3
            await s3.send(new PutObjectCommand({
                Bucket: bucketName,
                Key: versionKey,
                Body: markdown,
                ContentType: 'text/markdown'
            }));

            // Also update the main lab guide file
            const labGuideKey = `${projectFolder}/book/${labGuideData.filename}`;
            await s3.send(new PutObjectCommand({
                Bucket: bucketName,
                Key: labGuideKey,
                Body: markdown,
                ContentType: 'text/markdown'
            }));

            // Add to versions list
            if (existingVersion) {
                setLabGuideVersions(prev => prev.map(v =>
                    v.name.includes(safeVersionName)
                        ? { ...v, timestamp: new Date(), key: versionKey }
                        : v
                ));
            } else {
                setLabGuideVersions(prev => [{
                    name: versionFilename.replace('.md', ''),
                    timestamp: new Date(),
                    key: versionKey
                }, ...prev]);
            }

            // Update lab guide data with the current content
            setLabGuideData({
                ...labGuideData,
                content: currentContent
            });

            setNewLabGuideVersionName('');
            alert('¡Versión de Lab Guide guardada exitosamente!');
            console.log('Lab guide version saved successfully');
        } catch (error) {
            console.error('Error saving lab guide:', error);
            alert('Error al guardar la guía de laboratorios: ' + error.message);
        }
    };

    const parseMarkdownToBook = (markdown) => {
        const lines = markdown.split('\n');
        const lessons = [];
        let currentLesson = null;
        let inFrontMatter = true;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            if (line.startsWith('# ') && !line.includes('Table of Contents') && !line.includes('Book Statistics')) {
                if (currentLesson) {
                    lessons.push(currentLesson);
                }
                currentLesson = {
                    title: line.substring(2).trim(),
                    content: '',
                    filename: `lesson_${lessons.length + 1}.md`
                };
                inFrontMatter = false;
            } else if (currentLesson && !inFrontMatter) {
                currentLesson.content += line + '\n';
            }
        }

        if (currentLesson) {
            lessons.push(currentLesson);
        }

        return {
            metadata: {
                title: '📚 Libro del Curso',
                author: 'Aurora AI',
                generated_at: new Date().toISOString(),
                total_lessons: lessons.length,
                total_words: lessons.reduce((sum, lesson) => sum + lesson.content.split(/\s+/).length, 0)
            },
            lessons: lessons,
            table_of_contents: lessons.map(lesson => `- ${lesson.title}`)
        };
    };

    // Convert markdown lesson content to minimal HTML suitable for the editor
    const formatContentForEditing = (markdown) => {
        if (!markdown) return '';

        console.log('=== formatContentForEditing START ===');
        console.log('Input markdown length:', markdown.length);
        console.log('First 200 chars:', markdown.substring(0, 200));

        // Split into lines so we can group lists and preserve block structure
        const lines = markdown.split('\n');
        let out = '';
        let inUl = false;
        let inOl = false;
        let inCodeBlock = false;
        let codeBlockContent = '';
        let codeBlockLanguage = '';

        const closeLists = () => {
            if (inUl) { out += '</ul>'; inUl = false; }
            if (inOl) { out += '</ol>'; inOl = false; }
        };

        // Helper function to apply inline formatting (bold, italic, inline code)
        const applyInlineFormatting = (text) => {
            // Remove standalone triple quotes that are not part of code blocks
            // This handles cases where ''' or """ or ``` appear in regular text
            let result = text
                .replace(/^'''$/g, '') // Remove lines with only '''
                .replace(/^"""$/g, '') // Remove lines with only """
                .replace(/^```$/g, '') // Remove lines with only ```
                .replace(/\s'''(\s|$)/g, '$1') // Remove ''' with surrounding spaces
                .replace(/\s"""(\s|$)/g, '$1') // Remove """ with surrounding spaces
                .replace(/\s```(\s|$)/g, '$1'); // Remove ``` with surrounding spaces

            // Apply inline code, bold, italic formatting
            return result
                .replace(/`([^`]+)`/g, '<code style="background: #f4f4f4; padding: 0.2rem 0.4rem; border-radius: 3px; font-family: \'Courier New\', monospace;">$1</code>')
                .replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>')
                .replace(/\*([^\*]+)\*/g, '<em>$1</em>');
        };

        for (let rawLine of lines) {
            const line = rawLine.trimEnd();

            // Check for code block fences (```, """, ''') - with or without language
            // Match trimmed line to handle any leading/trailing whitespace
            const trimmedLine = line.trim();

            // Check for fence markers (with or without language identifier)
            const isFence = trimmedLine.startsWith('```') || trimmedLine.startsWith('"""') || trimmedLine.startsWith("'''");

            if (isFence) {
                // Extract language if present (e.g., ```yaml -> 'yaml')
                const langMatch = trimmedLine.match(/^(?:```|"""|''')(\w+)?/);

                if (!inCodeBlock) {
                    // Starting a code block
                    closeLists();
                    inCodeBlock = true;
                    codeBlockLanguage = (langMatch && langMatch[1]) ? langMatch[1] : '';
                    codeBlockContent = '';
                } else {
                    // Ending a code block
                    inCodeBlock = false;
                    if (codeBlockContent.trim()) {
                        const escapedCode = codeBlockContent
                            .replace(/&/g, '&amp;')
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;');
                        out += `<pre style="background: #f4f4f4; padding: 1rem; border-radius: 5px; overflow-x: auto; font-family: 'Courier New', monospace;"><code>${escapedCode}</code></pre>`;
                    }
                    codeBlockLanguage = '';
                    codeBlockContent = '';
                }
                continue; // Skip the fence line itself
            }

            // If inside code block, accumulate content (but don't process images here)
            if (inCodeBlock) {
                codeBlockContent += line + '\n';
                continue;
            }

            if (/^\s*$/.test(line)) {
                // blank line - only close lists if not in a list context
                // Check if next non-empty line is also a list item to keep lists open
                out += '<br/>';
                continue;
            }

            // Headings h1..h6 (support ###### .. #)
            const hMatch = line.match(/^(#{1,6})\s+(.*)$/);
            if (hMatch) {
                closeLists();
                const level = Math.min(6, hMatch[1].length);
                out += `<h${level}>${applyInlineFormatting(hMatch[2].trim())}</h${level}>`;
                console.log(`Converted heading: "${line}" -> <h${level}>`);
                continue;
            }

            // Blockquote
            const bq = line.match(/^>\s?(.*)$/);
            if (bq) {
                closeLists();
                out += `<blockquote>${applyInlineFormatting(bq[1])}</blockquote>`;
                continue;
            }

            // Unordered list item (including indented ones)
            const ul = line.match(/^(\s*)[-\*]\s+(.*)$/);
            if (ul) {
                const indent = ul[1].length;
                const itemContent = ul[2].trim();

                // Skip empty list items (where content is only whitespace or just triple quotes)
                if (!itemContent || itemContent === "'''" || itemContent === '"""' || itemContent === '```') {
                    continue;
                }

                if (!inUl) {
                    if (inOl) out += '</ol>';
                    inOl = false;
                    out += '<ul>';
                    inUl = true;
                }
                out += `<li>${applyInlineFormatting(itemContent)}</li>`;
                continue;
            }

            // Ordered list item (including indented ones)
            const ol = line.match(/^(\s*)\d+\.\s+(.*)$/);
            if (ol) {
                const indent = ol[1].length;
                const itemContent = ol[2].trim();

                // Skip empty list items (where content is only whitespace or just triple quotes)
                if (!itemContent || itemContent === "'''" || itemContent === '"""' || itemContent === '```') {
                    continue;
                }

                if (!inOl) {
                    if (inUl) out += '</ul>';
                    inUl = false;
                    out += '<ol>';
                    inOl = true;
                }
                out += `<li>${applyInlineFormatting(itemContent)}</li>`;
                continue;
            }

            // If line starts with whitespace and we're in a list, it might be continuation
            if ((inOl || inUl) && line.match(/^\s{4,}/)) {
                // Indented content within list item - add as paragraph within last li
                const content = line.trim();
                if (content) {
                    out += `<p style="margin-left: 1.5rem;">${applyInlineFormatting(content)}</p>`;
                }
                continue;
            }

            // Check if this line contains an image markdown (including those with long data URLs)
            // Support both ![alt](url) and ![[VISUAL: description]](url) formats
            // Use a more flexible pattern that handles very long base64 data URLs
            if (line.includes('![')) {
                console.log('🖼️ Found image line, length:', line.length);
                console.log('First 100 chars:', line.substring(0, 100));

                // Find the image markdown pattern - more robust for long URLs
                const imgStartIdx = line.indexOf('![');
                const imgEndBracketIdx = line.indexOf('](', imgStartIdx);

                console.log('Image indices:', { imgStartIdx, imgEndBracketIdx });

                if (imgStartIdx !== -1 && imgEndBracketIdx !== -1) {
                    // Extract alt text (between ![ and ])
                    let altStartIdx = imgStartIdx + 2;
                    let altEndIdx = imgEndBracketIdx;

                    // Handle double brackets ![[VISUAL: ...]]
                    if (line[altStartIdx] === '[') {
                        altStartIdx++;
                        // Find the closing ]]
                        const doubleCloseBracket = line.indexOf(']]', altStartIdx);
                        if (doubleCloseBracket !== -1 && doubleCloseBracket < imgEndBracketIdx) {
                            altEndIdx = doubleCloseBracket;
                        }
                    }

                    const alt = line.substring(altStartIdx, altEndIdx).trim();

                    // Extract URL (after ]( until the end of line or closing ))
                    const srcStartIdx = imgEndBracketIdx + 2;
                    let srcEndIdx = line.indexOf(')', srcStartIdx);

                    // If no closing paren found, the URL extends to end of line
                    if (srcEndIdx === -1) {
                        srcEndIdx = line.length;
                    }

                    const src = line.substring(srcStartIdx, srcEndIdx).trim();

                    console.log('Extracted alt:', alt);
                    console.log('Extracted src length:', src.length);
                    console.log('Src starts with:', src.substring(0, 50));

                    // Only render as image if we found valid src
                    if (src) {
                        closeLists();
                        console.log('✅ Rendering image with alt:', alt);
                        out += `<p style="text-align: center;"><img alt="${alt}" src="${src}" style="max-width: 100%; height: auto; display: inline-block;" /></p>`;
                        continue;
                    } else {
                        console.log('❌ No valid src found');
                    }
                } else {
                    console.log('❌ Image pattern not complete (missing ]( or ))');
                }
            }

            // Table row detection (markdown tables with | separator)
            // Match lines like: | Header 1 | Header 2 | Header 3 |
            // or: |----------|----------|----------|
            const tableMatch = line.match(/^\|(.+)\|$/);
            if (tableMatch) {
                closeLists();
                const cells = tableMatch[1].split('|').map(c => c.trim());

                // Check if this is a separator row (|---|---|)
                const isSeparator = cells.every(c => /^[-:]+$/.test(c));

                if (isSeparator) {
                    // Skip separator rows, they're just for markdown formatting
                    continue;
                }

                // Check if this is likely a header row (first table row or has bold text)
                const isHeaderRow = cells.some(c => /^\*\*/.test(c)) || !out.includes('<table');

                // Start table if not already in one
                if (!out.includes('<table') || out.lastIndexOf('</table>') > out.lastIndexOf('<table')) {
                    out += '<table style="width: 100%; border-collapse: collapse; margin: 1rem 0;">';
                    if (isHeaderRow) {
                        out += '<thead><tr>';
                        cells.forEach(cell => {
                            out += `<th style="border: 1px solid #ddd; padding: 0.75rem; background-color: #f4f4f4; text-align: left;">${applyInlineFormatting(cell)}</th>`;
                        });
                        out += '</tr></thead><tbody>';
                    } else {
                        out += '<tbody><tr>';
                        cells.forEach(cell => {
                            out += `<td style="border: 1px solid #ddd; padding: 0.75rem;">${applyInlineFormatting(cell)}</td>`;
                        });
                        out += '</tr>';
                    }
                } else {
                    // Continue existing table
                    out += '<tr>';
                    cells.forEach(cell => {
                        out += `<td style="border: 1px solid #ddd; padding: 0.75rem;">${applyInlineFormatting(cell)}</td>`;
                    });
                    out += '</tr>';
                }
                continue;
            }

            // Close table if we were in one and hit a non-table line
            if (out.includes('<table') && out.lastIndexOf('<table') > out.lastIndexOf('</table>')) {
                // Check if this line is not a table row
                if (!line.match(/^\|(.+)\|$/)) {
                    out += '</tbody></table>';
                }
            }

            // Apply inline formatting to regular text
            let inline = applyInlineFormatting(line);

            // If the line contains HTML-like block tags already, preserve them
            if (/^<\/?(p|div|h\d|ul|ol|li|img|blockquote|span)/i.test(inline)) {
                closeLists();
                out += inline;
            } else {
                closeLists();
                out += `<p>${inline}</p>`;
            }
        }

        closeLists();

        // Collapse adjacent empty paragraphs
        out = out.replace(/<p>\s*<\/p>/g, '');

        console.log('Output HTML length:', out.length);
        console.log('First 200 chars of HTML:', out.substring(0, 200));
        console.log('=== formatContentForEditing END ===');

        return out;
    };

    const loadVersions = async () => {
        try {
            // Load version files from S3 under projectFolder/versions/
            const session = await fetchAuthSession();
            if (!session || !session.credentials) return;
            const s3 = new S3Client({ region: AWS_REGION, credentials: session.credentials });
            const bucket = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';
            const prefix = `${projectFolder}/versions/`;

            const resp = await s3.send(new ListObjectsV2Command({ Bucket: bucket, Prefix: prefix }));
            const items = resp.Contents || [];
            const vers = items
                .filter(i => i.Key && i.Key.endsWith('.json'))
                .map(i => ({ name: i.Key.replace(prefix, ''), timestamp: i.LastModified, key: i.Key }))
                .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

            setVersions(vers);
        } catch (error) {
            console.error('Error al cargar versiones:', error);
        }
    };

    const loadLabGuideVersions = async () => {
        try {
            // Load lab guide version files from S3 under projectFolder/lab-versions/
            const session = await fetchAuthSession();
            if (!session || !session.credentials) return;
            const s3 = new S3Client({ region: AWS_REGION, credentials: session.credentials });
            const bucket = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';
            const prefix = `${projectFolder}/lab-versions/`;

            const resp = await s3.send(new ListObjectsV2Command({ Bucket: bucket, Prefix: prefix }));
            const items = resp.Contents || [];
            const vers = items
                .filter(i => i.Key && i.Key.endsWith('.md'))
                .map(i => ({ name: i.Key.replace(prefix, '').replace('.md', ''), timestamp: i.LastModified, key: i.Key }))
                .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

            setLabGuideVersions(vers);
        } catch (error) {
            console.error('Error al cargar versiones de lab guide:', error);
        }
    };

    const deleteVersion = async (version) => {
        if (!confirm(`¿Eliminar la versión "${version.name}"? Esta acción no se puede deshacer.`)) return;
        try {
            const session = await fetchAuthSession();
            if (!session || !session.credentials) throw new Error('No credentials');
            const { S3Client, DeleteObjectCommand } = await import('@aws-sdk/client-s3');
            const s3 = new S3Client({ region: AWS_REGION, credentials: session.credentials });
            const bucket = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';

            // Delete JSON
            await s3.send(new DeleteObjectCommand({ Bucket: bucket, Key: version.key }));
            // Also attempt to delete markdown snapshot (replace .json with .md)
            try {
                const mdKey = version.key.replace(/\.json$/i, '.md');
                await s3.send(new DeleteObjectCommand({ Bucket: bucket, Key: mdKey }));
            } catch (e) {
                // ignore missing md snapshot
            }

            setVersions(prev => prev.filter(v => v.key !== version.key));
            alert('Versión eliminada');
        } catch (e) {
            console.error('Failed to delete version:', e);
            alert('Error al eliminar versión: ' + String(e));
        }
    };

    const deleteLabGuideVersion = async (version) => {
        if (!confirm(`¿Eliminar la versión de Lab Guide "${version.name}"? Esta acción no se puede deshacer.`)) return;
        try {
            const session = await fetchAuthSession();
            if (!session || !session.credentials) throw new Error('No credentials');
            const { S3Client, DeleteObjectCommand } = await import('@aws-sdk/client-s3');
            const s3 = new S3Client({ region: AWS_REGION, credentials: session.credentials });
            const bucket = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';

            await s3.send(new DeleteObjectCommand({ Bucket: bucket, Key: version.key }));

            setLabGuideVersions(prev => prev.filter(v => v.key !== version.key));
            alert('Versión de Lab Guide eliminada');
        } catch (e) {
            console.error('Failed to delete lab guide version:', e);
            alert('Error al eliminar versión: ' + String(e));
        }
    };

    const viewVersion = async (version) => {
        try {
            setLoadingVersion(true);
            const session = await fetchAuthSession();
            if (!session || !session.credentials) throw new Error('No credentials');
            const { S3Client, GetObjectCommand } = await import('@aws-sdk/client-s3');
            const s3 = new S3Client({ region: AWS_REGION, credentials: session.credentials });
            const bucket = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';

            // Load the JSON version to get all lessons
            const resp = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: version.key }));
            const jsonText = await resp.Body.transformToString();
            const parsedVersion = JSON.parse(jsonText);

            // Process images in all lessons for display
            console.log('Loading images from version for viewing...');
            for (let lesson of parsedVersion.lessons || []) {
                if (lesson.content) {
                    lesson.content = await replaceS3UrlsWithDataUrls(lesson.content);
                }
            }

            // Load the version into the main viewer (not modal)
            setBookData(parsedVersion);
            setCurrentLessonIndex(0);
            setIsEditing(false); // View mode
            setShowVersionHistory(false); // Close version history panel
            setViewingVersion(null); // Clear any modal state
        } catch (e) {
            console.error('Failed to load version content:', e);
            alert('Error cargando la versión: ' + String(e));
        } finally {
            setLoadingVersion(false);
        }
    };

    // Load a version into the editor for editing. This will NOT overwrite the original files.
    const editVersion = async (version) => {
        try {
            setLoadingVersion(true);
            const session = await fetchAuthSession();
            if (!session || !session.credentials) throw new Error('No credentials');
            const { S3Client, GetObjectCommand } = await import('@aws-sdk/client-s3');
            const s3 = new S3Client({ region: AWS_REGION, credentials: session.credentials });
            const resp = await s3.send(new GetObjectCommand({
                Bucket: import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts',
                Key: version.key
            }));
            const jsonText = await resp.Body.transformToString();
            const parsed = JSON.parse(jsonText);

            // Process images in all lessons to convert S3 URLs to blob URLs for display
            console.log('Loading images from version for editing...');
            for (let lesson of parsed.lessons || []) {
                if (lesson.content) {
                    lesson.content = await replaceS3UrlsWithDataUrls(lesson.content);
                }
            }

            // Set bookData to parsed version and enter edit mode
            setBookData(parsed);
            setCurrentLessonIndex(0);
            setIsEditing(true);
            // Set editor HTML to the first lesson content formatted for editing
            const firstHtml = formatContentForEditing(parsed.lessons?.[0]?.content || '');
            try { editorRef.current && (editorRef.current.innerHTML = firstHtml); } catch (e) { }
            setEditingHtml(firstHtml);
            setShowVersionHistory(false); // Close version history panel
            alert('Versión cargada para edición. Puedes editar todas las lecciones. Para guardar cambios, usa "Guardar Versión".');
        } catch (e) {
            console.error('Failed to load version for edit:', e);
            alert('Error al cargar versión para editar: ' + String(e));
        } finally {
            setLoadingVersion(false);
        }
    };

    // View original version
    const viewOriginal = async () => {
        try {
            setLoadingVersion(true);

            if (!originalBookData) {
                throw new Error('No se encontró la versión original');
            }

            // Create a deep copy and process images for display
            const originalCopy = JSON.parse(JSON.stringify(originalBookData));
            console.log('Loading images from original version...');
            for (let lesson of originalCopy.lessons || []) {
                if (lesson.content) {
                    lesson.content = await replaceS3UrlsWithDataUrls(lesson.content);
                }
            }

            // Load the original into the main viewer
            setBookData(originalCopy);
            setCurrentLessonIndex(0);
            setIsEditing(false); // View mode
            setShowVersionHistory(false); // Close version history panel
        } catch (e) {
            console.error('Failed to load original version:', e);
            alert('Error cargando la versión original: ' + String(e));
        } finally {
            setLoadingVersion(false);
        }
    };

    // Edit original version
    const editOriginal = async () => {
        try {
            setLoadingVersion(true);

            if (!originalBookData) {
                throw new Error('No se encontró la versión original');
            }

            // Create a deep copy and process images for display
            const originalCopy = JSON.parse(JSON.stringify(originalBookData));
            console.log('Loading images from original version for editing...');
            for (let lesson of originalCopy.lessons || []) {
                if (lesson.content) {
                    lesson.content = await replaceS3UrlsWithDataUrls(lesson.content);
                }
            }

            // Set bookData to original and enter edit mode
            setBookData(originalCopy);
            setCurrentLessonIndex(0);
            setIsEditing(true);
            // Set editor HTML to the first lesson content formatted for editing
            const firstHtml = formatContentForEditing(originalCopy.lessons?.[0]?.content || '');
            try { editorRef.current && (editorRef.current.innerHTML = firstHtml); } catch (e) { }
            setEditingHtml(firstHtml);
            setShowVersionHistory(false); // Close version history panel
            alert('Versión original cargada para edición. Puedes editar todas las lecciones. Para guardar cambios, usa "Guardar Versión".');
        } catch (e) {
            console.error('Failed to load original for edit:', e);
            alert('Error al cargar la versión original para editar: ' + String(e));
        } finally {
            setLoadingVersion(false);
        }
    };

    // No Quill-specific paste handler; Lexical wrapper handles its own paste behavior.

    const saveBook = async () => {
        if (!bookData) return;

        try {
            setSaving(true);

            if (!IDENTITY_POOL_ID) {
                throw new Error('Cognito Identity Pool no configurado. Configure VITE_IDENTITY_POOL_ID en su archivo de entorno y recargue la aplicación.');
            }

            // If the user is still editing, convert the current editor HTML to markdown
            // and use that to build the book JSON we upload. This ensures the most
            // recent edits are included even if the component state hasn't flushed yet.
            let bookToUpload = bookData;
            if (isEditing) {
                let html = editingHtml ?? editorRef.current?.innerHTML ?? '';

                // Upload any pasted/inline images (data URLs) to S3 and replace with S3 URLs
                try {
                    const { replaceDataUrlsWithS3Urls } = await import('../utils/s3ImageLoader');
                    html = await replaceDataUrlsWithS3Urls(html, projectFolder);
                } catch (e) {
                    console.warn('Failed to upload inline images before save:', e);
                }

                const markdown = convertHtmlToMarkdown(html);
                const updatedLessons = [...(bookData.lessons || [])];
                updatedLessons[currentLessonIndex] = {
                    ...(updatedLessons[currentLessonIndex] || {}),
                    content: markdown
                };
                bookToUpload = {
                    ...bookData,
                    lessons: updatedLessons,
                    metadata: {
                        ...bookData.metadata,
                        total_words: updatedLessons.reduce((sum, lesson) => sum + (lesson.content || '').split(/\s+/).length, 0)
                    }
                };
            }

            const bookJson = JSON.stringify(bookToUpload);
            // Obtain authenticated credentials from Amplify (requires user to be signed-in and Identity Pool configured)
            const session = await fetchAuthSession();
            if (!session || !session.credentials) {
                throw new Error('No se encontraron credenciales autenticadas. Asegúrate de iniciar sesión y que VITE_IDENTITY_POOL_ID esté configurado.');
            }

            const s3 = new S3Client({
                region: AWS_REGION,
                credentials: session.credentials,
            });

            const s3Key = `${projectFolder}/book/course_book_data.json`;

            const bucketName = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';

            // Use simple PutObjectCommand for faster, more reliable uploads
            // This avoids multipart upload complexity and CRC32 checksum issues
            await s3.send(new PutObjectCommand({
                Bucket: bucketName,
                Key: s3Key,
                Body: bookJson,
                ContentType: 'application/json',
            }));

            // Notify backend with S3 key
            const notifyResp = await fetch(`${API_BASE}/save-book`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ projectFolder: projectFolder, bookS3Key: s3Key })
            });

            if (!notifyResp.ok) {
                const errText = await notifyResp.text();
                throw new Error('Error al notificar guardado: ' + errText);
            }

            await notifyResp.json();

            // Autosave removed: only manual "Guardar Versión" will create versions.

            // Update local state to reflect what we uploaded and exit edit mode
            setBookData(bookToUpload);
            setIsEditing(false);
            alert('¡Libro guardado exitosamente (subido a S3 via Cognito)!');
        } catch (error) {
            console.error('Error al guardar libro:', error);
            if (error instanceof TypeError) {
                console.error('Fetch failed. This is often caused by CORS or network issues. Ensure the API Gateway allows requests from your origin and that the endpoint is reachable.');
            }
            alert('Error al guardar libro: ' + error.message);
        } finally {
            setSaving(false);
        }
    };

    const generateMarkdownFromBook = (book) => {
        let markdown = `# ${book.metadata.title}\n\n`;
        markdown += `**Author:** ${book.metadata.author}\n`;
        markdown += `**Generated:** ${new Date(book.metadata.generated_at).toLocaleDateString()}\n\n`;
        markdown += `---\n\n`;
        markdown += `# Table of Contents\n\n`;
        book.table_of_contents.forEach(item => {
            markdown += `${item}\n`;
        });
        markdown += `\n---\n\n`;

        book.lessons.forEach((lesson, index) => {
            markdown += `# Lesson ${index + 1}: ${lesson.title}\n\n`;
            markdown += lesson.content;
            markdown += `\n---\n\n`;
        });

        markdown += `## Book Statistics\n\n`;
        markdown += `- **Total Lessons**: ${book.metadata.total_lessons}\n`;
        markdown += `- **Total Words**: ${book.metadata.total_words}\n`;
        markdown += `- **Last Updated**: ${new Date().toLocaleString()}\n`;

        return markdown;
    };

    const saveVersion = async () => {
        if (!newVersionName.trim()) {
            alert('Por favor ingresa un nombre para la versión');
            return;
        }

        try {
            const safeVersionName = newVersionName.replace(/\s+/g, '_');
            const originalFilename = (bookData && (bookData.filename || (bookData.metadata && bookData.metadata.filename))) || 'course_book_data';
            const baseName = originalFilename.replace(/\.[^/.]+$/, '');
            // Include original filename in version name: originalname_versionname.json
            const versionJsonName = `${baseName}_${safeVersionName}.json`;
            const versionKey = `${projectFolder}/versions/${versionJsonName}`;

            // Check if version with this name already exists
            const existingVersion = versions.find(v => v.key === versionKey);
            if (existingVersion) {
                const override = confirm(`Ya existe una versión con el nombre "${newVersionName}".\n\n¿Deseas sobrescribirla?`);
                if (!override) {
                    return; // User cancelled
                }
            }

            // Ensure the current lesson edits are saved into bookData before creating version
            let bookToVersion = bookData;
            if (isEditing) {
                let html = editingHtml ?? editorRef.current?.innerHTML ?? '';

                // Upload any inline images (data URLs) to S3 before saving version
                try {
                    const { replaceDataUrlsWithS3Urls } = await import('../utils/s3ImageLoader');
                    html = await replaceDataUrlsWithS3Urls(html, projectFolder);
                } catch (e) {
                    console.warn('Failed to upload inline images before version save:', e);
                }

                const markdown = convertHtmlToMarkdown(html);
                const updatedLessons = [...(bookData.lessons || [])];
                updatedLessons[currentLessonIndex] = {
                    ...(updatedLessons[currentLessonIndex] || {}),
                    content: markdown
                };
                bookToVersion = {
                    ...bookData,
                    lessons: updatedLessons,
                    metadata: {
                        ...bookData.metadata,
                        total_words: updatedLessons.reduce((sum, lesson) => sum + (lesson.content || '').split(/\s+/).length, 0)
                    }
                };
            }

            const versionData = {
                ...bookToVersion,
                version_name: newVersionName,
                saved_at: new Date().toISOString()
            };

            // Upload version JSON to S3 using authenticated Amplify credentials
            const session = await fetchAuthSession();
            if (!session || !session.credentials) {
                throw new Error('No se encontraron credenciales autenticadas. Asegúrate de iniciar sesión y que VITE_IDENTITY_POOL_ID esté configurado.');
            }

            const s3 = new S3Client({
                region: AWS_REGION,
                credentials: session.credentials,
            });

            const bucketName = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';

            // Use simple PutObjectCommand (will overwrite if exists)
            await s3.send(new PutObjectCommand({
                Bucket: bucketName,
                Key: versionKey,
                Body: JSON.stringify(versionData, null, 2),
                ContentType: 'application/json',
            }));

            // Also save a markdown snapshot for easier previewing
            try {
                const markdown = generateMarkdownFromBook(versionData);
                const mdName = `${baseName}_${safeVersionName}.md`;
                const mdKey = `${projectFolder}/versions/${mdName}`;
                await s3.send(new PutObjectCommand({
                    Bucket: bucketName,
                    Key: mdKey,
                    Body: markdown,
                    ContentType: 'text/markdown'
                }));
            } catch (e) {
                console.warn('Failed to save markdown snapshot for version:', e);
            }

            // Update or add version to list
            if (existingVersion) {
                // Update existing version timestamp
                setVersions(prev => prev.map(v =>
                    v.key === versionKey
                        ? { ...v, name: newVersionName, timestamp: versionData.saved_at }
                        : v
                ));
            } else {
                // Add new version
                setVersions(prev => [...prev, {
                    name: newVersionName,
                    timestamp: versionData.saved_at,
                    key: versionKey
                }]);
            }

            setNewVersionName('');
            alert(existingVersion ? '¡Versión sobrescrita exitosamente!' : '¡Versión guardada exitosamente!');
        } catch (error) {
            console.error('Error al guardar versión:', error);
            alert('Error al guardar versión: ' + error.message);
        }
    };

    const updateLessonContent = (index, newContent) => {
        const updatedLessons = [...bookData.lessons];
        updatedLessons[index].content = newContent;
        setBookData({
            ...bookData,
            lessons: updatedLessons,
            metadata: {
                ...bookData.metadata,
                total_words: updatedLessons.reduce((sum, lesson) => sum + lesson.content.split(/\s+/).length, 0)
            }
        });
    };

    // live input handler: keep editingHtml while typing
    const handleContentChange = (e) => {
        if (isEditing) {
            const htmlContent = e.target.innerHTML;
            setEditingHtml(htmlContent);
        }
    };

    // Handle paste events: upload images from clipboard (files or data URLs) and replace
    // them with S3 URLs so saved content contains S3 links instead of inline data.
    const handlePaste = async (e) => {
        if (!isEditing) return;
        try {
            const clipboard = e.clipboardData || window.clipboardData;
            if (!clipboard) return;

            // If files are present (image files), upload them
            const files = Array.from(clipboard.files || []).filter(f => f.type && f.type.startsWith('image/'));
            if (files.length > 0) {
                e.preventDefault();
                // For immediate visual feedback, insert a local blob URL first,
                // then upload the file and replace the src with the S3/presigned URL.
                for (const file of files) {
                    try {
                        const localUrl = URL.createObjectURL(file);
                        // Insert a wrapper so we can find and replace the img later
                        const wrapperHtml = `<div data-local-url="${localUrl}"><img src="${localUrl}" alt="pasted-image" data-local-url="${localUrl}" /></div>`;
                        const insertedNodes = insertHtmlAtCursor(wrapperHtml);
                        // scroll into view the inserted element
                        try {
                            if (insertedNodes && insertedNodes.length > 0) {
                                const node = insertedNodes[0];
                                node.scrollIntoView({ block: 'nearest' });
                            }
                        } catch (e) { }

                        // Upload in background and replace the local URL when done
                        (async () => {
                            try {
                                const s3Url = await uploadImageToS3(file, projectFolder);
                                // For private buckets, fetch the S3 object as a blob URL for display
                                const { getBlobUrlForS3Object } = await import('../utils/s3ImageLoader');
                                const displayUrl = await getBlobUrlForS3Object(s3Url);

                                // Replace any img elements with matching data-local-url
                                const imgs = editorRef.current?.querySelectorAll(`img[data-local-url="${localUrl}"]`) || [];
                                imgs.forEach(img => {
                                    try {
                                        img.src = displayUrl;
                                        img.setAttribute('data-s3-url', s3Url); // Store original S3 URL for saving
                                        img.removeAttribute('data-local-url');
                                    } catch (e) { }
                                });
                                // revoke local object URL
                                try { URL.revokeObjectURL(localUrl); } catch (e) { }
                                // sync editingHtml
                                setEditingHtml(editorRef.current?.innerHTML ?? '');
                            } catch (err) {
                                console.error('Failed to upload pasted file image:', err);
                            }
                        })();
                    } catch (err) {
                        console.error('Failed to handle pasted file image:', err);
                    }
                }
                // update editingHtml after inserts
                setEditingHtml(editorRef.current?.innerHTML ?? '');
                return;
            }

            // If clipboard has HTML with data URLs, detect and upload
            const html = clipboard.getData('text/html');
            if (html && html.includes('data:')) {
                e.preventDefault();
                // Replace data URLs with S3 URLs using helper
                const updated = await replaceDataUrlsWithS3Urls(html, projectFolder);
                // Insert updated HTML at caret
                insertHtmlAtCursor(updated);
                setEditingHtml(editorRef.current?.innerHTML ?? '');
                return;
            }

            // Otherwise let default paste happen and update editingHtml shortly after
            setTimeout(() => setEditingHtml(editorRef.current?.innerHTML ?? ''), 50);
        } catch (e) {
            console.error('Paste handler error:', e);
        }
    };

    // Helper to insert HTML at the current cursor position inside the editor
    function insertHtmlAtCursor(html) {
        const sel = window.getSelection();
        if (!sel || sel.rangeCount === 0) {
            // fallback: append
            if (editorRef.current) {
                const el = document.createElement('div');
                el.innerHTML = html;
                while (el.firstChild) editorRef.current.appendChild(el.firstChild);
                return null;
            }
            return null;
        }
        const range = sel.getRangeAt(0);
        range.deleteContents();
        const el = document.createElement('div');
        el.innerHTML = html;
        const frag = document.createDocumentFragment();
        let node, lastNode;
        const inserted = [];
        while ((node = el.firstChild)) {
            const appended = frag.appendChild(node);
            inserted.push(appended);
            lastNode = appended;
        }
        range.insertNode(frag);
        // Move selection to after inserted content
        if (lastNode) {
            range.setStartAfter(lastNode);
            range.setEndAfter(lastNode);
            sel.removeAllRanges();
            sel.addRange(range);
        }
        return inserted;
    }

    // Only set the editor HTML when switching lessons, toggling edit mode, or when the
    // underlying lesson content actually changes. Guard against undefined content to
    // avoid runtime errors that would unmount the component (blank page).
    // Apply innerHTML only when switching lessons or toggling edit mode.
    useEffect(() => {
        if (viewMode !== 'book') return; // Only run for book view

        const editor = editorRef.current;
        if (!editor) return;

        const lessonContent = bookData?.lessons?.[currentLessonIndex]?.content || '';
        const formatted = formatContentForEditing(lessonContent);

        if (isEditing) {
            // Initialize editing HTML if not already set
            const initial = editingHtml ?? formatted;
            try { editor.innerHTML = initial; } catch (e) { console.error('Failed to set editor HTML:', e); }
            setEditingHtml(initial);
            // focus editor when entering edit mode
            try { editor.focus(); } catch (e) { }
        } else {
            // Render canonical content in read-only
            try { editor.innerHTML = formatted; } catch (e) { console.error('Failed to set editor HTML:', e); }
            setEditingHtml(null);
        }

        lastAppliedLessonRef.current = { index: currentLessonIndex, content: formatted, isEditing };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [viewMode, currentLessonIndex, isEditing, bookData]);

    // Similar useEffect for lab guide editing
    useEffect(() => {
        if (viewMode !== 'lab') return;

        const editor = editorRef.current;
        if (!editor) return;

        const labContent = labGuideData?.content || '';
        const formatted = formatContentForEditing(labContent);

        // Check if we need to update (avoid unnecessary re-renders)
        const lastApplied = lastAppliedLabGuideRef.current;
        if (lastApplied.isEditing === isEditing && lastApplied.content === formatted) {
            return; // No change needed
        }

        if (isEditing) {
            // Only set HTML if we're transitioning to edit mode or content changed
            if (lastApplied.isEditing !== isEditing) {
                // Transitioning to edit mode
                const initial = labGuideEditingHtml ?? formatted;
                try {
                    editor.innerHTML = initial;
                } catch (e) {
                    console.error('Failed to set lab guide editor HTML:', e);
                }
                setLabGuideEditingHtml(initial);
                // Only focus on initial transition to edit mode
                setTimeout(() => {
                    try { editor.focus(); } catch (e) { }
                }, 0);
            }
        } else {
            // Render canonical content in read-only
            try {
                editor.innerHTML = formatted;
            } catch (e) {
                console.error('Failed to set lab guide editor HTML:', e);
            }
            setLabGuideEditingHtml(null);
        }

        lastAppliedLabGuideRef.current = { isEditing, content: formatted };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [viewMode, isEditing, labGuideData]);

    // Helpers to map node -> path and back so caret can be restored after innerHTML changes
    function getNodePath(root, node) {
        const path = [];
        let cur = node;
        while (cur && cur !== root) {
            const parent = cur.parentNode;
            if (!parent) break;
            const idx = Array.prototype.indexOf.call(parent.childNodes, cur);
            path.unshift(idx);
            cur = parent;
        }
        return path;
    }

    function getNodeFromPath(root, path) {
        try {
            let cur = root;
            for (const idx of path) {
                if (!cur || !cur.childNodes || cur.childNodes.length <= idx) return null;
                cur = cur.childNodes[idx];
            }
            return cur;
        } catch (e) {
            return null;
        }
    }

    const convertHtmlToMarkdown = (html) => {
        console.log('=== convertHtmlToMarkdown START ===');
        console.log('Input HTML length:', html.length);
        console.log('First 300 chars of input HTML:', html.substring(0, 300));

        // Parse HTML and fix image S3 URLs
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const images = doc.querySelectorAll('img');

        console.log('Found images:', images.length);
        images.forEach((img, idx) => {
            const s3Url = img.getAttribute('data-s3-url');
            const currentSrc = img.src;
            const alt = img.alt;
            console.log(`Image ${idx}:`, {
                alt: alt,
                currentSrc: currentSrc.substring(0, 100),
                hasDataS3Url: !!s3Url,
                dataS3Url: s3Url || 'none'
            });

            if (s3Url) {
                console.log(`✓ Replacing src with data-s3-url for image ${idx}: ${s3Url}`);
                img.src = s3Url;
                img.removeAttribute('data-s3-url');
            } else {
                console.warn(`⚠ Image ${idx} has NO data-s3-url attribute! Current src: ${currentSrc.substring(0, 100)}`);
            }
        });

        // Convert DOM to Markdown recursively
        const convertNodeToMarkdown = (node) => {
            if (node.nodeType === Node.TEXT_NODE) {
                return node.textContent || '';
            }

            if (node.nodeType !== Node.ELEMENT_NODE) {
                return '';
            }

            const tag = node.tagName.toLowerCase();
            const children = Array.from(node.childNodes).map(convertNodeToMarkdown).join('');

            switch (tag) {
                case 'h1': return `# ${children}\n\n`;
                case 'h2': return `## ${children}\n\n`;
                case 'h3': return `### ${children}\n\n`;
                case 'h4': return `#### ${children}\n\n`;
                case 'h5': return `##### ${children}\n\n`;
                case 'h6': return `###### ${children}\n\n`;
                case 'p': return `${children}\n\n`;
                case 'br': return '\n';
                case 'strong':
                case 'b': return `**${children}**`;
                case 'em':
                case 'i': return `*${children}*`;
                case 'font': {
                    // Handle old-style font tags (color, size, etc.)
                    const attrs = [];
                    if (node.hasAttribute('color')) attrs.push(`color: ${node.getAttribute('color')}`);
                    if (node.hasAttribute('size')) attrs.push(`font-size: ${node.getAttribute('size')}`);
                    if (attrs.length > 0) {
                        return `<span style="${attrs.join('; ')}">${children}</span>`;
                    }
                    return children;
                }
                case 'ul':
                    return Array.from(node.children)
                        .map(li => `- ${convertNodeToMarkdown(li)}`)
                        .join('') + '\n';
                case 'ol':
                    return Array.from(node.children)
                        .map((li, idx) => `${idx + 1}. ${convertNodeToMarkdown(li)}`)
                        .join('') + '\n';
                case 'li': return `${children}\n`;
                case 'blockquote': return `> ${children}\n\n`;
                case 'img': {
                    const src = node.src || '';
                    const alt = node.alt || 'image';
                    // Check if this is a VISUAL image (special format)
                    if (alt.includes('VISUAL') || alt.includes('[VISUAL')) {
                        return `![[${alt}]](${src})\n`;
                    }
                    return `![${alt}](${src})\n`;
                }
                case 'div':
                case 'span': {
                    // Handle inline styles for spans
                    if (node.hasAttribute && node.hasAttribute('style')) {
                        const style = node.getAttribute('style');
                        // Preserve as HTML for styled text (markdown doesn't support colors/sizes)
                        return `<span style="${style}">${children}</span>`;
                    }
                    return children;
                }
                default:
                    return children;
            }
        };

        const markdown = convertNodeToMarkdown(doc.body)
            .replace(/\n{3,}/g, '\n\n')  // Collapse multiple newlines
            .trim();

        const markdownImages = markdown.match(/!\[.*?\]\(.*?\)/g) || [];
        console.log('Output markdown length:', markdown.length);
        console.log('Markdown images found:', markdownImages.length);
        if (markdownImages.length > 0) {
            console.log('Markdown images:', markdownImages);
        }
        console.log('First 300 chars of output markdown:', markdown.substring(0, 300));
        console.log('=== convertHtmlToMarkdown END ===');

        return markdown;
    };

    // Save editingHtml back into bookData (convert to markdown) when finalizing edit
    const finalizeEditing = async () => {
        // Don't process book data if we're in lab guide mode
        if (viewMode === 'lab') {
            setIsEditing(false);
            return;
        }

        if (!bookData) return;

        console.log('=== Finalizing Edit START ===');
        const startTime = performance.now();

        const html = editingHtml ?? editorRef.current?.innerHTML ?? '';
        console.log('HTML to convert length:', html.length);

        const markdown = convertHtmlToMarkdown(html);
        console.log('Markdown result length:', markdown.length);

        // Update the lesson content
        const updatedLessons = [...bookData.lessons];
        updatedLessons[currentLessonIndex] = {
            ...updatedLessons[currentLessonIndex],
            content: markdown
        };

        const updatedBookData = {
            ...bookData,
            lessons: updatedLessons,
            metadata: {
                ...bookData.metadata,
                total_words: updatedLessons.reduce((sum, lesson) => sum + lesson.content.split(/\s+/).length, 0)
            }
        };

        setBookData(updatedBookData);

        // Process images in the updated markdown for display
        const contentWithImages = await replaceS3UrlsWithDataUrls(markdown);
        updatedLessons[currentLessonIndex].content = contentWithImages;
        setBookData({
            ...updatedBookData,
            lessons: updatedLessons
        });

        // Exit edit mode - the useEffect will handle re-rendering the formatted HTML
        setIsEditing(false);
        setEditingHtml(null);

        const endTime = performance.now();
        console.log(`=== Finalizing Edit END (took ${(endTime - startTime).toFixed(2)}ms) ===`);
    };    // Basic execCommand wrapper for toolbar actions. Modern browsers may deprecate execCommand,
    // but it's still widely supported for simple editors. We implement small helpers for
    // increase/decrease font by wrapping selection in span with style.
    function execCommand(command, value = null) {
        try {
            if (command === 'increaseFont' || command === 'decreaseFont') {
                // custom handling
                const editor = editorRef.current;
                const sel = window.getSelection();
                if (!sel || sel.rangeCount === 0) return;
                const range = sel.getRangeAt(0);
                const span = document.createElement('span');
                const currentSize = command === 'increaseFont' ? 1.2 : 0.9;
                span.style.fontSize = (currentSize * 100) + '%';
                span.appendChild(range.extractContents());
                range.insertNode(span);
                // Update editingHtml
                setTimeout(() => setEditingHtml(editor.innerHTML), 0);
                return;
            }

            document.execCommand(command, false, value);
            // Update editingHtml after command
            const editor = editorRef.current;
            if (editor) setEditingHtml(editor.innerHTML);
        } catch (e) {
            console.error('execCommand failed:', e);
        }
    }

    // Copy format: save the inline style of the current selection's container
    const formatClipboard = useRef(null);
    function handleCopyFormat() {
        const sel = window.getSelection();
        if (!sel || sel.rangeCount === 0) {
            alert('Por favor, selecciona algún texto primero');
            return;
        }
        const node = sel.anchorNode && sel.anchorNode.nodeType === 3 ? sel.anchorNode.parentNode : sel.anchorNode;
        if (!node) return;

        // Get computed style from the element
        const computedStyle = window.getComputedStyle(node);
        const styleObj = {
            color: computedStyle.color,
            fontSize: computedStyle.fontSize,
            fontWeight: computedStyle.fontWeight,
            fontStyle: computedStyle.fontStyle,
            textAlign: computedStyle.textAlign,
            backgroundColor: computedStyle.backgroundColor
        };
        formatClipboard.current = styleObj;

        // Visual feedback
        alert('✅ Formato copiado');
    }

    function handleApplyFormat() {
        if (!formatClipboard.current) {
            alert('⚠️ Primero debes copiar un formato');
            return;
        }
        const sel = window.getSelection();
        if (!sel || sel.rangeCount === 0) {
            alert('Por favor, selecciona algún texto primero');
            return;
        }
        const range = sel.getRangeAt(0);
        const span = document.createElement('span');

        // Apply stored format as inline styles
        const styleObj = formatClipboard.current;
        let styleString = '';
        if (styleObj.color) styleString += `color: ${styleObj.color}; `;
        if (styleObj.fontSize) styleString += `font-size: ${styleObj.fontSize}; `;
        if (styleObj.fontWeight && styleObj.fontWeight !== 'normal' && styleObj.fontWeight !== '400') {
            styleString += `font-weight: ${styleObj.fontWeight}; `;
        }
        if (styleObj.fontStyle && styleObj.fontStyle !== 'normal') {
            styleString += `font-style: ${styleObj.fontStyle}; `;
        }
        if (styleObj.textAlign) styleString += `text-align: ${styleObj.textAlign}; `;
        if (styleObj.backgroundColor && styleObj.backgroundColor !== 'rgba(0, 0, 0, 0)') {
            styleString += `background-color: ${styleObj.backgroundColor}; `;
        }

        if (styleString) span.setAttribute('style', styleString);
        span.appendChild(range.extractContents());
        range.insertNode(span);
        const editor = editorRef.current;
        if (editor) setEditingHtml(editor.innerHTML);

        // Visual feedback
        alert('✅ Formato aplicado');
    }

    // Generate PowerPoint Presentation
    const generatePowerPoint = async () => {
        try {
            setPptGenerating(true);

            // Get authenticated session
            const session = await fetchAuthSession();
            if (!session || !session.credentials) {
                throw new Error('No se encontraron credenciales autenticadas. Por favor inicia sesión.');
            }

            // Determine which book version to use
            let bookVersionKey = null; // Let Lambda auto-discover the book file

            if (selectedPPTVersion !== 'current' && selectedPPTVersion !== 'original') {
                // User selected a specific version from the versions list
                const version = versions.find(v => v.key === selectedPPTVersion);
                if (version) {
                    bookVersionKey = version.key;
                } else {
                    throw new Error('Versión seleccionada no encontrada');
                }
            }
            // For 'current' or 'original', we leave bookVersionKey as null
            // and let the Lambda discover the latest _data.json file

            console.log('🎯 Generating PPT from version:', bookVersionKey || 'auto-discover latest');

            const requestBody = {
                course_bucket: import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts',
                project_folder: projectFolder,
                book_version_key: bookVersionKey, // null means auto-discover
                model_provider: pptModelProvider,
                slides_per_lesson: slidesPerLesson,
                presentation_style: pptStyle
            };

            console.log('📤 Request:', requestBody);

            // Close modal immediately and show async message
            setShowPPTModal(false);
            setPptGenerating(false);

            // Show async generation message
            alert('🚀 Generación de Presentación Iniciada\n\n' +
                'La presentación PowerPoint se está generando en segundo plano.\n' +
                'Este proceso puede tardar varios minutos dependiendo del tamaño del libro.\n\n' +
                '📊 Configuración:\n' +
                `- Estilo: ${pptStyle}\n` +
                `- Diapositivas por lección: ${slidesPerLesson}\n` +
                `- Modelo: ${pptModelProvider}\n\n` +
                'Puedes continuar trabajando mientras se genera.\n' +
                'La presentación se guardará automáticamente en S3.');

            // Make async request without blocking the UI
            fetch(`${API_BASE}/generate-ppt`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            }).then(async response => {
                if (!response.ok) {
                    let errorMessage = `HTTP ${response.status}`;
                    try {
                        const errorData = await response.json();
                        errorMessage = errorData.error || errorMessage;
                    } catch {
                        const errorText = await response.text();
                        errorMessage = errorText || errorMessage;
                    }
                    throw new Error(`Error generando PPT: ${errorMessage}`);
                }
                return response.json();
            }).then(data => {
                // Check for backend errors
                if (data.error) {
                    throw new Error(`Backend error: ${data.error}`);
                }

                console.log('✅ PPT generated:', data);

                // Enhanced success notification
                const successMessage = `✅ ¡Presentación Generada Exitosamente!\n\n` +
                    `📊 ${data.total_slides} diapositivas creadas\n` +
                    `📁 Ubicación: S3/${data.pptx_s3_key || data.structure_s3_key}\n` +
                    `⏱️ Generado: ${new Date(data.generated_at).toLocaleString()}\n` +
                    `🎨 Estilo: ${pptStyle}\n` +
                    `📝 Diapositivas por lección: ${slidesPerLesson}`;

                // Create download link for the PPTX file
                if (data.pptx_s3_key) {
                    const downloadUrl = `https://crewai-course-artifacts.s3.amazonaws.com/${data.pptx_s3_key}`;
                    const fullMessage = successMessage + `\n\n🔗 URL: ${downloadUrl}\n\n¿Deseas descargar el archivo ahora?`;

                    // Show notification with download option
                    if (confirm(fullMessage)) {
                        window.open(downloadUrl, '_blank');
                    }
                } else {
                    alert(successMessage);
                }
            }).catch(error => {
                console.error('❌ Error generating PPT:', error);

                let userMessage = '❌ Error al generar presentación PowerPoint';
                if (error.message.includes('credentials')) {
                    userMessage += '\n\nVerifica que estés autenticado correctamente.';
                } else if (error.message.includes('ImportError') || error.message.includes('ModuleNotFoundError')) {
                    userMessage += '\n\nError de dependencias en el servidor. Contacta al administrador.';
                } else if (error.message.includes('timeout') || error.message.includes('Timeout')) {
                    userMessage += '\n\nEl proceso tardó demasiado. Intenta con menos diapositivas por lección.';
                } else if (error.message.includes('No book files')) {
                    userMessage += '\n\nNo se encontró el archivo del libro. Verifica que el proyecto tenga un libro válido.';
                }

                alert(userMessage + '\n\nDetalles técnicos: ' + error.message);
            });

        } catch (error) {
            console.error('❌ Error initiating PPT generation:', error);

            let userMessage = '❌ Error al iniciar generación de presentación PowerPoint';
            if (error.message.includes('credentials')) {
                userMessage += '\n\nVerifica que estés autenticado correctamente.';
            }

            alert(userMessage + '\n\nDetalles técnicos: ' + error.message);
            setPptGenerating(false);
        }
    };

    // Defensive rendering: show loading or error if data not ready
    if (loading) {
        return (
            <div className="book-editor-loading">
                <p>Cargando libro...</p>
                {loadingImages && <p style={{ fontSize: '0.9em', opacity: 0.7 }}>Cargando imágenes desde S3...</p>}
            </div>
        );
    }

    if (!bookData) {
        return <div className="book-editor-error">No se encontraron datos del libro para este proyecto.</div>;
    }

    if (!bookData.lessons || !Array.isArray(bookData.lessons)) {
        return <div className="book-editor-error">El libro no tiene un formato válido (lessons no es un array).</div>;
    }

    if (bookData.lessons.length === 0) {
        return <div className="book-editor-error">Este libro no contiene lecciones.</div>;
    }

    const currentLesson = bookData.lessons?.[currentLessonIndex] || { title: '', content: '' };

    return (
        <div className="book-editor">
            {loadingImages && (
                <div className="image-loading-indicator">
                    🖼️ Cargando imágenes en segundo plano...
                </div>
            )}
            {loadingVersion && (
                <div className="version-loading-overlay">
                    <div className="version-loading-content">
                        <div className="spinner"></div>
                        <p>Cargando versión...</p>
                    </div>
                </div>
            )}
            <div className="book-editor-header">
                <h2>📚</h2>
                <div className="editor-toolbar-compact">
                    <button onClick={() => execCommand('bold')} title="Negrita"><strong>B</strong></button>
                    <button onClick={() => execCommand('italic')} title="Cursiva"><em>I</em></button>
                    <button onClick={() => execCommand('justifyLeft')} title="Alinear izquierda">
                        <span style={{ display: 'inline-block', fontSize: '14px' }}>
                            &#x2190;&#x2261;
                        </span>
                    </button>
                    <button onClick={() => execCommand('justifyCenter')} title="Centrar">
                        <span style={{ display: 'inline-block', fontSize: '14px' }}>
                            &#x2261;
                        </span>
                    </button>
                    <button onClick={() => execCommand('justifyRight')} title="Alinear derecha">
                        <span style={{ display: 'inline-block', fontSize: '14px' }}>
                            &#x2261;&#x2192;
                        </span>
                    </button>
                    {/* Color options dropdown */}
                    <select onChange={(e) => execCommand('foreColor', e.target.value)} title="Color de texto" style={{ padding: '0.4rem', border: '1px solid #ddd', borderRadius: '4px', cursor: 'pointer' }}>
                        <option value="">🎨 Color</option>
                        <option value="#000000">⚫ Negro</option>
                        <option value="#d9534f">🔴 Rojo</option>
                        <option value="#5cb85c">🟢 Verde</option>
                        <option value="#5bc0de">🔵 Azul</option>
                        <option value="#f0ad4e">🟠 Naranja</option>
                        <option value="#9b59b6">🟣 Morado</option>
                        <option value="#e91e63">💗 Rosa</option>
                        <option value="#3498db">🔷 Azul claro</option>
                    </select>
                    <button onClick={() => execCommand('increaseFont')} title="Aumentar tamaño">A+</button>
                    <button onClick={() => execCommand('decreaseFont')} title="Disminuir tamaño">A-</button>
                    <button onClick={() => handleCopyFormat()} title="Copiar Formato">📋</button>
                    <button onClick={() => handleApplyFormat()} title="Aplicar Formato">🖌️</button>
                </div>
                <div className="book-editor-actions">
                    {labGuideData && (
                        <button
                            className={viewMode === 'lab' ? 'btn-active' : ''}
                            onClick={() => setViewMode(viewMode === 'book' ? 'lab' : 'book')}
                            title={viewMode === 'book' ? 'Ver Guía de Laboratorios' : 'Ver Libro'}
                        >
                            {viewMode === 'book' ? '🧪 Lab Guide' : '📚 Libro'}
                        </button>
                    )}
                    <button
                        className="btn-generate-ppt"
                        onClick={() => setShowPPTModal(true)}
                        title="Generar presentación PowerPoint"
                    >
                        📊 Generar PPT
                    </button>
                    <button
                        className={isEditing ? 'btn-editing' : 'btn-edit'}
                        onClick={async () => {
                            console.log('=== Edit button clicked ===', isEditing ? 'Finalizing' : 'Entering edit mode');
                            const startTime = performance.now();

                            if (isEditing) {
                                // Just finalize editing - versions are saved separately
                                finalizeEditing();
                            } else {
                                setIsEditing(true);
                            }

                            const endTime = performance.now();
                            console.log(`Button handler took ${(endTime - startTime).toFixed(2)}ms`);
                        }}
                    >
                        {isEditing ? '✓ Finalizar Edición' : '✏️ Editar'}
                    </button>
                    {/* Save button intentionally removed: use "Guardar Versión" to create versions */}
                    <button onClick={() => setShowVersionHistory(!showVersionHistory)}>
                        📋 Versiones ({viewMode === 'lab' ? labGuideVersions.length : versions.length + 1})
                    </button>
                    <button onClick={onClose} className="btn-close">✕ Cerrar</button>
                </div>
            </div>
            {showVersionHistory && (
                <div className="version-history">
                    <h3>Historial de Versiones {viewMode === 'lab' ? '- Lab Guide' : '- Libro'}</h3>
                    {viewMode === 'book' ? (
                        <>
                            <div className="version-list">
                                {/* Original version entry */}
                                <div className="version-item version-original">
                                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                            <button className="version-name" onClick={viewOriginal}>Ver</button>
                                            <button onClick={editOriginal}>Editar</button>
                                            <div style={{ marginLeft: '0.5rem', fontWeight: 'bold' }}>📄 Original</div>
                                        </div>
                                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                            <div className="version-meta" style={{ fontStyle: 'italic', color: '#666' }}>Versión inicial del libro</div>
                                        </div>
                                    </div>
                                </div>
                                {/* Saved versions */}
                                {versions.map((version, index) => (
                                    <div key={index} className={`version-item ${version.isCurrent ? 'current' : ''}`}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                                <button className="version-name" onClick={() => viewVersion(version)}>Ver</button>
                                                <button onClick={() => editVersion(version)}>Editar</button>
                                                <div style={{ marginLeft: '0.5rem' }}>{version.name}</div>
                                            </div>
                                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                                <div className="version-meta">{version.timestamp ? new Date(version.timestamp).toLocaleString('es-ES') : ''}</div>
                                                <button onClick={() => deleteVersion(version)} title="Eliminar versión" style={{ color: '#c0392b' }}>Eliminar</button>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <div className="save-version">
                                <input value={newVersionName} onChange={e => setNewVersionName(e.target.value)} placeholder="Nombre de la versión" />
                                <button onClick={saveVersion} disabled={!newVersionName.trim()}>Guardar Versión</button>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="version-list">
                                {/* Lab Guide Versions */}
                                {labGuideVersions.length === 0 ? (
                                    <div style={{ padding: '1rem', textAlign: 'center', color: '#666' }}>
                                        No hay versiones guardadas del Lab Guide
                                    </div>
                                ) : (
                                    labGuideVersions.map((version, index) => (
                                        <div key={index} className="version-item">
                                            <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                                                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                                    <div style={{ marginLeft: '0.5rem' }}>{version.name}</div>
                                                </div>
                                                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                                    <div className="version-meta">{version.timestamp ? new Date(version.timestamp).toLocaleString('es-ES') : ''}</div>
                                                    <button onClick={() => deleteLabGuideVersion(version)} title="Eliminar versión" style={{ color: '#c0392b' }}>Eliminar</button>
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                            <div className="save-version">
                                <input value={newLabGuideVersionName} onChange={e => setNewLabGuideVersionName(e.target.value)} placeholder="Nombre de la versión" />
                                <button onClick={saveLabGuide} disabled={!newLabGuideVersionName.trim()}>Guardar Versión Lab Guide</button>
                            </div>
                        </>
                    )}
                </div>
            )}
            <div className="book-editor-content">
                {viewMode === 'book' ? (
                    <>
                        <div className="lesson-navigator">
                            <h3>Contenido del Libro</h3>
                            <div className="navigator-stats">
                                {Object.keys(groupLessonsByModule()).length} módulos · {bookData.lessons.length} lecciones
                            </div>
                            <div className="navigator-actions">
                                <button
                                    className="btn-toggle-all"
                                    onClick={toggleAllModules}
                                    title={Object.keys(collapsedModules).some(k => collapsedModules[k]) ? "Expandir todo" : "Colapsar todo"}
                                >
                                    {Object.keys(collapsedModules).some(k => collapsedModules[k]) ? "📂 Expandir Todo" : "📁 Colapsar Todo"}
                                </button>
                            </div>
                            <div className="lesson-list">
                                {renderLessonsByModule()}
                            </div>
                        </div>
                        <div className="lesson-editor">
                            {isEditing && (
                                <div className="save-version-inline">
                                    <input
                                        value={newVersionName}
                                        onChange={e => setNewVersionName(e.target.value)}
                                        placeholder="Nombre de la versión"
                                        className="version-name-input"
                                    />
                                    <button
                                        onClick={saveVersion}
                                        disabled={!newVersionName.trim()}
                                        className="btn-save-version"
                                        title="Guardar una nueva versión de este libro"
                                    >
                                        💾 Guardar Versión
                                    </button>
                                </div>
                            )}
                            <div className="lesson-header">
                                <h3>{currentLesson.title}</h3>
                                <div className="lesson-stats">Palabras: {currentLesson.content.split(/\s+/).filter(Boolean).length}</div>
                            </div>
                            <div className="editor-container">
                                {isEditing ? (
                                    <div
                                        ref={editorRef}
                                        className="content-editor"
                                        contentEditable={true}
                                        suppressContentEditableWarning={true}
                                        onInput={handleContentChange}
                                        onPaste={handlePaste}
                                        tabIndex={0}
                                    />
                                ) : (
                                    <div
                                        ref={editorRef}
                                        className="content-editor"
                                        contentEditable={false}
                                        dangerouslySetInnerHTML={{ __html: formatContentForEditing(currentLesson.content) }}
                                    />
                                )}
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="lab-guide-viewer">
                        <div className="lab-guide-header">
                            <div>
                                <h2>🧪 Guía de Laboratorios</h2>
                                <div className="lab-guide-info">
                                    <span>📄 {labGuideData?.filename}</span>
                                    {labGuideData?.lastModified && (
                                        <span>📅 {new Date(labGuideData.lastModified).toLocaleDateString('es-ES')}</span>
                                    )}
                                </div>
                            </div>
                            {isEditing && (
                                <div className="editor-toolbar">
                                    <button onClick={() => applyHeading(1)} title="Título 1">H1</button>
                                    <button onClick={() => applyHeading(2)} title="Título 2">H2</button>
                                    <button onClick={() => applyHeading(3)} title="Título 3">H3</button>
                                    <button onClick={() => document.execCommand('bold', false, null)} title="Negrita">B</button>
                                    <button onClick={() => document.execCommand('italic', false, null)} title="Cursiva">I</button>
                                    <button onClick={() => document.execCommand('insertUnorderedList', false, null)} title="Lista">•</button>
                                    <button onClick={() => handleImageUpload()} title="Agregar Imagen">🖼️</button>
                                    <button onClick={() => handleCopyFormat()} title="Copiar Formato">📋</button>
                                    <button onClick={() => handleApplyFormat()} title="Aplicar Formato">🖌️</button>
                                </div>
                            )}
                        </div>
                        {isEditing && (
                            <div className="save-version-inline">
                                <input
                                    value={newLabGuideVersionName}
                                    onChange={e => setNewLabGuideVersionName(e.target.value)}
                                    placeholder="Nombre de la versión del Lab Guide"
                                    className="version-name-input"
                                />
                                <button
                                    onClick={saveLabGuide}
                                    disabled={!newLabGuideVersionName.trim()}
                                    className="btn-save-version"
                                    title="Guardar una nueva versión del Lab Guide"
                                >
                                    💾 Guardar Versión Lab Guide
                                </button>
                            </div>
                        )}
                        <div className="lab-guide-content">
                            {isEditing ? (
                                <div
                                    ref={editorRef}
                                    className="content-editor"
                                    contentEditable={true}
                                    suppressContentEditableWarning={true}
                                    onInput={(e) => {
                                        // Just track the HTML - don't update labGuideData to avoid re-render
                                        setLabGuideEditingHtml(e.currentTarget.innerHTML);
                                    }}
                                />
                            ) : (
                                <div
                                    className="content-viewer"
                                    dangerouslySetInnerHTML={{ __html: formatContentForEditing(labGuideData?.content || '') }}
                                />
                            )}
                        </div>
                    </div>
                )}

                {/* PowerPoint Generation Modal */}
                {showPPTModal && (
                    <div className="ppt-modal-overlay" onClick={() => !pptGenerating && setShowPPTModal(false)}>
                        <div className="ppt-modal-content" onClick={(e) => e.stopPropagation()}>
                            <div className="ppt-modal-header">
                                <h2>📊 Generar Presentación PowerPoint</h2>
                                <button
                                    className="ppt-modal-close"
                                    onClick={() => setShowPPTModal(false)}
                                    disabled={pptGenerating}
                                >
                                    ✕
                                </button>
                            </div>

                            <div className="ppt-modal-body">
                                <div className="ppt-form-group">
                                    <label>Versión del Libro:</label>
                                    <select
                                        value={selectedPPTVersion}
                                        onChange={(e) => setSelectedPPTVersion(e.target.value)}
                                        disabled={pptGenerating}
                                    >
                                        <option value="current">📄 Versión Actual</option>
                                        <option value="original">📄 Versión Original</option>
                                        {versions.map((v, idx) => (
                                            <option key={idx} value={v.key}>
                                                📋 {v.name} ({new Date(v.timestamp).toLocaleDateString()})
                                            </option>
                                        ))}
                                    </select>
                                    <small>Selecciona qué versión del libro usar para generar las diapositivas</small>
                                </div>

                                <div className="ppt-form-group">
                                    <label>Estilo de Presentación:</label>
                                    <select
                                        value={pptStyle}
                                        onChange={(e) => setPptStyle(e.target.value)}
                                        disabled={pptGenerating}
                                    >
                                        <option value="professional">💼 Profesional - Diseño corporativo limpio</option>
                                        <option value="educational">📚 Educativo - Amigable para estudiantes</option>
                                        <option value="modern">✨ Moderno - Minimalista y dinámico</option>
                                    </select>
                                </div>

                                <div className="ppt-form-group">
                                    <label>Diapositivas por Lección:</label>
                                    <input
                                        type="number"
                                        min="3"
                                        max="10"
                                        value={slidesPerLesson}
                                        onChange={(e) => setSlidesPerLesson(parseInt(e.target.value))}
                                        disabled={pptGenerating}
                                    />
                                    <small>Número aproximado de diapositivas por cada lección (3-10)</small>
                                </div>

                                <div className="ppt-form-group">
                                    <label>Modelo de IA:</label>
                                    <select
                                        value={pptModelProvider}
                                        onChange={(e) => setPptModelProvider(e.target.value)}
                                        disabled={pptGenerating}
                                    >
                                        <option value="bedrock">AWS Bedrock (Claude 4.5 Sonnet)</option>
                                        <option value="openai">OpenAI (GPT-5)</option>
                                    </select>
                                </div>

                                <div className="ppt-info-box">
                                    <strong>ℹ️ Información:</strong>
                                    <ul>
                                        <li>Se generarán aproximadamente {slidesPerLesson * (bookData?.lessons?.length || 0)} diapositivas</li>
                                        <li>Las imágenes del libro se reutilizarán automáticamente</li>
                                        <li>El proceso puede tardar 5-10 minutos</li>
                                        <li>La presentación se guardará en S3 para descargar</li>
                                    </ul>
                                </div>
                            </div>

                            <div className="ppt-modal-footer">
                                <button
                                    className="btn-cancel"
                                    onClick={() => setShowPPTModal(false)}
                                    disabled={pptGenerating}
                                >
                                    Cancelar
                                </button>
                                <button
                                    className="btn-generate-ppt-submit"
                                    onClick={generatePowerPoint}
                                    disabled={pptGenerating}
                                >
                                    {pptGenerating ? (
                                        <>
                                            <span className="spinner-small"></span>
                                            Generando...
                                        </>
                                    ) : (
                                        '📊 Generar Presentación'
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default BookEditor;