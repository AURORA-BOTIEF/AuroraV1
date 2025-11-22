// src/components/BookEditor.jsx
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { replaceS3UrlsWithDataUrls, uploadImageToS3 } from '../utils/s3ImageLoader';
import { S3Client, PutObjectCommand, ListObjectsV2Command, GetObjectCommand } from '@aws-sdk/client-s3';
import { fetchAuthSession } from 'aws-amplify/auth';
import { load as loadYaml } from 'js-yaml';
import './BookEditor.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;
const IDENTITY_POOL_ID = import.meta.env.VITE_IDENTITY_POOL_ID || import.meta.env.VITE_AWS_IDENTITY_POOL_ID || '';
const AWS_REGION = import.meta.env.VITE_AWS_REGION || 'us-east-1';

function BookEditor({ projectFolder, bookType = 'theory', onClose }) {
    const navigate = useNavigate();
    const [bookData, setBookData] = useState(null);
    const [originalBookData, setOriginalBookData] = useState(null); // Store original for "Original" version
    const [loading, setLoading] = useState(true);
    const [loadingImages, setLoadingImages] = useState(false);
    const [saving, setSaving] = useState(false);
    const [currentLessonIndex, setCurrentLessonIndex] = useState(0);
    const [currentLabLessonIndex, setCurrentLabLessonIndex] = useState(0);
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
            const match = lesson.title.match(/(?:Module|Módulo)\s*(\d+)/i);
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
        const data = viewMode === 'book' ? bookData : labGuideData;
        if (!data || !data.lessons || !Array.isArray(data.lessons)) return {};

        const modules = {};
        data.lessons.forEach((lesson, index) => {
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
        const activeIndex = viewMode === 'book' ? currentLessonIndex : currentLabLessonIndex;
        const setActiveIndex = viewMode === 'book' ? setCurrentLessonIndex : setCurrentLabLessonIndex;

        return moduleNumbers.map(moduleNum => {
            const module = modules[moduleNum];
            const isCollapsed = collapsedModules[moduleNum];

            // Get module title from first lesson's moduleTitle property, or use default
            const firstLesson = module.lessons[0];
            let moduleTitle = firstLesson?.moduleTitle || `Módulo ${moduleNum}`;

            // Ensure localization
            if (moduleTitle && typeof moduleTitle === 'string') {
                moduleTitle = moduleTitle.replace(/\bModule\b/g, 'Módulo');
            }

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
                                    className={`lesson-item ${lesson.originalIndex === activeIndex ? 'active' : ''}`}
                                    onClick={() => setActiveIndex(lesson.originalIndex)}
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
                                    moduleTitle: (module.module_title || module.title || `Módulo ${moduleIdx + 1}`).replace(/\bModule\b/g, 'Módulo'),
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
                // Parse book content immediately without waiting for images
                console.log('Parsing book content (images will load in background)...');
                const parsedBook = parseMarkdownToBook(data.bookContent);

                // Set book data immediately for fast UI display
                setBookData(parsedBook);
                setOriginalBookData(JSON.parse(JSON.stringify(parsedBook)));
                setLoadingImages(false);

                // Load images in the background
                console.log('Loading images from S3 in background...');
                replaceS3UrlsWithDataUrls(data.bookContent).then(contentWithImages => {
                    const parsedBookWithImages = parseMarkdownToBook(contentWithImages);
                    setBookData(parsedBookWithImages);
                    setOriginalBookData(JSON.parse(JSON.stringify(parsedBookWithImages)));
                    console.log('Images loaded successfully');
                }).catch(err => {
                    console.error('Error loading images:', err);
                });

                return; // Exit early since we've set the state
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

                // Parse immediately without waiting for images
                const parsedBook = parseMarkdownToBook(markdown);
                setBookData(parsedBook);
                setOriginalBookData(JSON.parse(JSON.stringify(parsedBook)));
                setLoadingImages(false);

                // Load images in background
                console.log('Loading images from S3 in background...');
                replaceS3UrlsWithDataUrls(markdown).then(contentWithImages => {
                    const parsedBookWithImages = parseMarkdownToBook(contentWithImages);
                    setBookData(parsedBookWithImages);
                    setOriginalBookData(JSON.parse(JSON.stringify(parsedBookWithImages)));
                    console.log('Images loaded successfully');
                }).catch(err => {
                    console.error('Error loading images:', err);
                });

                return; // Exit early since we've set the state
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
            const outlinePrefix = `${projectFolder}/outline/`;

            // 1. Fetch Outline
            const outlineResponse = await s3.send(new ListObjectsV2Command({
                Bucket: bucketName,
                Prefix: outlinePrefix,
                MaxKeys: 10
            }));

            let outlineData = null;
            let outlineFilename = 'none';

            if (outlineResponse.Contents && outlineResponse.Contents.length > 0) {
                // Prioritize YAML over JSON
                let outlineFile = outlineResponse.Contents.find(obj =>
                    obj.Key.endsWith('.yaml') || obj.Key.endsWith('.yml')
                );

                if (!outlineFile) {
                    outlineFile = outlineResponse.Contents.find(obj => obj.Key.endsWith('.json'));
                }

                if (outlineFile) {
                    outlineFilename = outlineFile.Key;
                    console.log('Loading outline from:', outlineFilename);

                    const outlineObj = await s3.send(new GetObjectCommand({
                        Bucket: bucketName,
                        Key: outlineFile.Key
                    }));
                    const outlineContent = await outlineObj.Body.transformToString();

                    if (outlineFile.Key.endsWith('.json')) {
                        outlineData = JSON.parse(outlineContent);
                    } else {
                        outlineData = loadYaml(outlineContent);
                    }
                }
            }

            // 2. Fetch Lab Guide Markdown
            const response = await s3.send(new ListObjectsV2Command({
                Bucket: bucketName,
                Prefix: labGuidePrefix,
                MaxKeys: 50
            }));

            if (!response.Contents) {
                console.log('No contents found in book folder');
                return;
            }

            // Look for lab guide file (_LabGuide_complete)
            const labGuideFile = response.Contents.find(obj =>
                obj.Key && obj.Key.includes('_LabGuide_complete')
            );

            if (!labGuideFile) {
                console.log('No lab guide file found.');
                return;
            }

            console.log('Found lab guide:', labGuideFile.Key);

            const labGuideResponse = await s3.send(new GetObjectCommand({
                Bucket: bucketName,
                Key: labGuideFile.Key
            }));

            const labGuideContent = await labGuideResponse.Body.transformToString();

            // 3. Parse using Outline immediately without waiting for images
            let parsedBook;
            if (outlineData) {
                console.log('Parsing Lab Guide using Outline (images will load in background)...');
                parsedBook = parseMarkdownWithOutline(labGuideContent, outlineData, { onlyLabs: true, filename: outlineFilename });
                console.log(`Parsed ${parsedBook.lessons.length} lessons using outline.`);
            } else {
                console.log('Parsing Lab Guide using simple headers (fallback)...');
                parsedBook = parseMarkdownToBook(labGuideContent);
            }

            // Set Lab Guide data immediately for fast UI display
            setLabGuideData({
                ...parsedBook,
                filename: labGuideFile.Key.split('/').pop(),
                lastModified: labGuideFile.LastModified
            });

            // Load images in the background
            console.log('Loading Lab Guide images from S3 in background...');
            replaceS3UrlsWithDataUrls(labGuideContent).then(contentWithImages => {
                let parsedBookWithImages;
                if (outlineData) {
                    parsedBookWithImages = parseMarkdownWithOutline(contentWithImages, outlineData, { onlyLabs: true, filename: outlineFilename });
                } else {
                    parsedBookWithImages = parseMarkdownToBook(contentWithImages);
                }

                setLabGuideData({
                    ...parsedBookWithImages,
                    filename: labGuideFile.Key.split('/').pop(),
                    lastModified: labGuideFile.LastModified
                });
                console.log('Lab Guide images loaded successfully');
            }).catch(err => {
                console.error('Error loading Lab Guide images:', err);
            });

            console.log('Lab guide loaded successfully');
        } catch (error) {
            console.error('Error loading lab guide:', error);
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
            // If editing, we need to update the current lesson's content in the local copy first
            let contentToSave = labGuideData;

            if (isEditing) {
                const currentHtml = labGuideEditingHtml || editorRef.current?.innerHTML || '';
                // We need to convert this HTML to markdown and update the specific lesson
                // But wait, labGuideEditingHtml is just for the current lesson.
                // We need to update the specific lesson in the labGuideData structure.

                const markdown = convertHtmlToMarkdown(currentHtml);
                const updatedLessons = [...(labGuideData.lessons || [])];
                if (updatedLessons[currentLabLessonIndex]) {
                    updatedLessons[currentLabLessonIndex] = {
                        ...updatedLessons[currentLabLessonIndex],
                        content: markdown
                    };
                }

                contentToSave = {
                    ...labGuideData,
                    lessons: updatedLessons
                };
            }

            // Convert the entire book structure back to markdown
            const markdown = generateMarkdownFromBook(contentToSave);

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
            setLabGuideData(contentToSave);

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

        return { lessons };


    };

    const parseMarkdownWithOutline = (markdown, outline, options = {}) => {
        const { onlyLabs = false, filename = 'unknown' } = options;
        const normalizedMd = markdown.replace(/\r\n/g, '\n');
        const lines = normalizedMd.split('\n');

        // 1. Extract all headers with their line numbers
        const headers = [];
        // Allow optional space after #
        const headerRegex = /^(#{1,6})\s*(.+)$/;

        lines.forEach((line, index) => {
            const match = line.match(headerRegex);
            if (match) {
                headers.push({
                    level: match[1].length,
                    title: match[2].trim(),
                    lineIndex: index,
                    raw: line
                });
            }
        });

        // Debug info collector
        const debugLog = [];
        debugLog.push(`Outline File: ${filename}`);
        debugLog.push(`Found ${headers.length} headers in markdown.`);
        if (headers.length > 0) {
            debugLog.push(`First 5 headers: ${headers.slice(0, 5).map(h => h.title).join(', ')}`);
        }

        // 2. Map outline items to headers
        const modules = [];
        const flatLessons = [];

        // Helper to normalize strings for comparison
        const normalize = (str) => str.toLowerCase()
            .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // Remove accents
            .replace(/[^\w\s]/g, '') // Remove non-word chars
            .replace(/\s+/g, ' ')
            .trim();

        // Helper to find best matching header
        const findHeader = (title, startLine = 0) => {
            if (!title) return null;
            const normTitle = normalize(title);

            // 1. Exact match (case insensitive, normalized)
            let match = headers.find(h => h.lineIndex >= startLine && normalize(h.title) === normTitle);
            if (match) return match;

            // 2. Try "Module X" / "Módulo X" match for modules
            // Matches "Module 1", "Módulo 1", "Module 01", etc.
            const modMatch = title.match(/(?:Module|Módulo)\s+(\d+)/i);
            if (modMatch) {
                const modNumber = modMatch[1];
                // Look for header containing "Module <num>" or "Modulo <num>"
                // We use word boundaries or just simple inclusion?
                // "module 1" should match "module 1" or "module 01"
                // Let's try simple inclusion of the number
                match = headers.find(h => {
                    if (h.lineIndex < startLine) return false;
                    const normH = normalize(h.title);
                    // Check for "module <num>" or "modulo <num>"
                    if (normH.includes(`module ${modNumber}`) || normH.includes(`modulo ${modNumber}`)) return true;
                    if (normH.includes(`module 0${modNumber}`) || normH.includes(`modulo 0${modNumber}`)) return true;
                    return false;
                });
                if (match) return match;
            }

            // 3. Strong fuzzy match (contains) - Header contains Outline Title
            match = headers.find(h => h.lineIndex >= startLine && normalize(h.title).includes(normTitle));
            if (match) return match;

            // 4. Reverse contains (Outline Title contains Header)
            match = headers.find(h => normTitle.includes(normalize(h.title)));

            return match;
        };

        let lastLineIndex = 0; // This variable will become obsolete but is kept for now to minimize diff

        // Track which headers have already been matched to avoid duplicates
        const usedHeaders = new Set();

        // Access modules from outline.course.modules (YAML structure) or outline.modules (flat structure)
        const modulesList = (outline.course && outline.course.modules) || outline.modules || [];

        if (modulesList.length === 0) {
            debugLog.push("CRITICAL: No modules found in outline object. Checked outline.course.modules and outline.modules.");
            debugLog.push(`Outline keys: ${Object.keys(outline).join(', ')} `);
            if (outline.course) debugLog.push(`Outline.course keys: ${Object.keys(outline.course).join(', ')} `);
        }

        // Iterate through outline modules
        modulesList.forEach((outModule, modIdx) => {
            const moduleObj = {
                title: outModule.title,
                lessons: []
            };

            debugLog.push(`Processing Module: "${outModule.title}"`);
            debugLog.push(`  Module has ${outModule.lessons ? outModule.lessons.length : 0} lessons in outline`);

            // Collect all potential lesson items (Lessons + Lab Activities)
            const moduleItems = [];

            if (outModule.lessons) {
                outModule.lessons.forEach((outLesson) => {
                    // Add the Lesson itself (ONLY if not in onlyLabs mode)
                    if (!onlyLabs) {
                        moduleItems.push({
                            title: outLesson.title,
                            type: 'lesson',
                            original: outLesson
                        });
                    }

                    // Add Lab Activities nested in the lesson
                    if (outLesson.lab_activities) {
                        outLesson.lab_activities.forEach(lab => {
                            moduleItems.push({
                                title: lab.title,
                                type: 'lab',
                                original: lab
                            });
                        });
                    }
                });
            }

            // Now try to find headers for these items
            // The module assignment comes from the outline, not from markdown headers
            moduleItems.forEach((item, idx) => {
                // Search the entire document for this lab activity
                const header = findHeader(item.title, 0);

                if (header && !usedHeaders.has(header.lineIndex)) {
                    usedHeaders.add(header.lineIndex);

                    const lessonObj = {
                        title: item.title,
                        content: '',
                        module_title: outModule.title,  // Module comes from outline structure
                        moduleNumber: modIdx + 1,  // Set moduleNumber to prevent fallback logic
                        lesson_number: flatLessons.length + 1,
                        filename: `module_${modIdx + 1}_item_${flatLessons.length + 1}.md`,
                        startLine: header.lineIndex,
                        type: item.type
                    };

                    moduleObj.lessons.push(lessonObj);
                    flatLessons.push(lessonObj);

                    debugLog.push(`  ✓ Matched "${item.title}" -> "${header.title}" (Module from outline: ${outModule.title}, moduleNumber: ${modIdx + 1})`);
                } else if (header && usedHeaders.has(header.lineIndex)) {
                    debugLog.push(`  ⚠ Header for "${item.title}" already used`);
                } else {
                    debugLog.push(`  ✗ FAILED to match "${item.title}"`);
                }
            });

            // If no items found for this module, but we have a module header,
            // maybe we should add a placeholder or the whole module content?
            // But for Lab Guide, usually there are items.

            modules.push(moduleObj);
        });

        // 3. Extract content for each lesson
        // Sort by line number to ensure correct order and content capture
        const sortedLessons = flatLessons.sort((a, b) => a.startLine - b.startLine);

        sortedLessons.forEach((lesson, idx) => {
            const nextLesson = sortedLessons[idx + 1];

            // The end line is the start of the next lesson, OR the start of the next Module (if we tracked that)
            // But simpler: just go until the next *found* lesson.
            // This effectively merges "fragments" (unmatched headers) into the current lesson.
            const endLine = nextLesson ? nextLesson.startLine : lines.length;

            // Extract lines
            // We start from startLine + 1 to skip the header itself (optional, but usually cleaner)
            // Or keep the header? The BookEditor usually expects content *without* the main title if it renders it separately.
            // But here, let's keep the header if it's part of the flow, or remove it if it duplicates the sidebar title.
            // Let's include the header line for context, or maybe startLine + 1.
            // Standard `parseMarkdownToBook` excludes the header (line.substring(2)).
            // Let's exclude the header line.
            const contentLines = lines.slice(lesson.startLine + 1, endLine);
            lesson.content = contentLines.join('\n').trim();

            delete lesson.startLine;
        });

        return {
            metadata: {
                title: '📚 Libro del Curso',
                author: 'Aurora AI',
                generated_at: new Date().toISOString(),
                total_lessons: flatLessons.length,
                total_words: flatLessons.reduce((sum, lesson) => sum + lesson.content.split(/\s+/).length, 0),
                debug_log: debugLog // Return log
            },
            lessons: flatLessons,
            table_of_contents: flatLessons.map(lesson => `- ${lesson.title} `)
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
        try {
            let markdown = `# ${book.metadata?.title || 'Course Book'}\n\n`;

            if (book.metadata?.author) {
                markdown += `**Author:** ${book.metadata.author}\n`;
            }
            if (book.metadata?.generated_at) {
                markdown += `**Generated:** ${new Date(book.metadata.generated_at).toLocaleDateString()}\n`;
            }
            markdown += `\n---\n\n`;

            // Table of contents (optional)
            if (book.table_of_contents && Array.isArray(book.table_of_contents)) {
                markdown += `# Table of Contents\n\n`;
                book.table_of_contents.forEach(item => {
                    markdown += `${item}\n`;
                });
                markdown += `\n---\n\n`;
            }

            // Lessons content
            const lessons = book.lessons || [];
            lessons.forEach((lesson, index) => {
                markdown += `# Lesson ${index + 1}: ${lesson.title || 'Untitled'}\n\n`;
                markdown += (lesson.content || '') + '\n\n';
                markdown += `---\n\n`;
            });

            // Statistics
            markdown += `## Book Statistics\n\n`;
            markdown += `- **Total Lessons**: ${book.metadata?.total_lessons || lessons.length}\n`;
            markdown += `- **Total Words**: ${book.metadata?.total_words || 0}\n`;
            markdown += `- **Last Updated**: ${new Date().toLocaleString()}\n`;

            return markdown;
        } catch (error) {
            console.error('Error generating markdown:', error);
            // Return minimal markdown on error
            return `# Course Book\n\nError generating full markdown: ${error.message}\n`;
        }
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
                    console.error('❌ Failed to upload inline images before version save:', e);
                    alert('Error: No se pudieron subir algunas imágenes a S3. Por favor, intenta de nuevo.');
                    return; // Don't save version with embedded images
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

                // CRITICAL: Also update modules structure if it exists
                if (bookData.modules && Array.isArray(bookData.modules)) {
                    const updatedModules = bookData.modules.map(module => {
                        return {
                            ...module,
                            lessons: (module.lessons || []).map((moduleLesson, idx) => {
                                const matchingLesson = updatedLessons.find(l =>
                                    l.title === moduleLesson.title ||
                                    l.lesson_number === moduleLesson.lesson_number
                                );
                                return matchingLesson || moduleLesson;
                            })
                        };
                    });
                    bookToVersion.modules = updatedModules;
                }
            }

            // CRITICAL: Replace ALL embedded images in ALL lessons with S3 URLs
            console.log('🔍 Scanning all lessons for embedded images...');
            try {
                const { replaceDataUrlsWithS3Urls } = await import('../utils/s3ImageLoader');
                const cleanedLessons = [];
                let totalImagesFound = 0;
                let totalImagesUploaded = 0;

                for (const lesson of bookToVersion.lessons || []) {
                    if (!lesson.content) {
                        cleanedLessons.push(lesson);
                        continue;
                    }

                    const beforeSize = lesson.content.length;
                    const imageCount = (lesson.content.match(/data:image/g) || []).length;
                    totalImagesFound += imageCount;

                    if (imageCount > 0) {
                        console.log(`📸 Found ${imageCount} embedded image(s) in lesson "${lesson.title}"`);
                        const cleanedContent = await replaceDataUrlsWithS3Urls(lesson.content, projectFolder);
                        const afterSize = cleanedContent.length;

                        if (afterSize < beforeSize) {
                            totalImagesUploaded += imageCount;
                            console.log(`✅ Uploaded ${imageCount} image(s) - size reduced from ${(beforeSize / 1024).toFixed(1)}KB to ${(afterSize / 1024).toFixed(1)}KB`);
                        }

                        cleanedLessons.push({
                            ...lesson,
                            content: cleanedContent
                        });
                    } else {
                        cleanedLessons.push(lesson);
                    }
                }

                if (totalImagesFound > 0) {
                    console.log(`✅ Processed ${totalImagesUploaded}/${totalImagesFound} embedded images`);

                    // CRITICAL: Update BOTH lessons and modules structures
                    bookToVersion = {
                        ...bookToVersion,
                        lessons: cleanedLessons
                    };

                    // If modules structure exists, update it too
                    if (bookToVersion.modules && Array.isArray(bookToVersion.modules)) {
                        console.log('🔄 Updating modules structure to match lessons...');
                        const updatedModules = bookToVersion.modules.map(module => {
                            return {
                                ...module,
                                lessons: (module.lessons || []).map((moduleLesson, idx) => {
                                    // Find corresponding lesson in cleanedLessons by index or title
                                    const matchingLesson = cleanedLessons.find(l =>
                                        l.title === moduleLesson.title ||
                                        l.lesson_number === moduleLesson.lesson_number
                                    );
                                    return matchingLesson || moduleLesson;
                                })
                            };
                        });
                        bookToVersion.modules = updatedModules;
                        console.log('✅ Modules structure updated');
                    }
                } else {
                    console.log('✅ No embedded images found - all images already on S3');
                }
            } catch (e) {
                console.error('❌ Failed to clean embedded images from lessons:', e);
                alert('Error: No se pudieron procesar las imágenes incrustadas. La versión puede ser muy grande.');
                // Continue anyway - user chose to proceed
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
                console.log('📝 Generating markdown snapshot...');
                const markdown = generateMarkdownFromBook(versionData);
                const mdName = `${baseName}_${safeVersionName}.md`;
                const mdKey = `${projectFolder}/versions/${mdName}`;

                console.log(`📤 Uploading markdown to: ${mdKey}`);
                await s3.send(new PutObjectCommand({
                    Bucket: bucketName,
                    Key: mdKey,
                    Body: markdown,
                    ContentType: 'text/markdown'
                }));
                console.log('✅ Markdown snapshot saved successfully');
            } catch (e) {
                console.error('❌ Failed to save markdown snapshot for version:', e);
                alert('Advertencia: No se pudo guardar el archivo .md (solo se guardó el JSON)');
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
            if (viewMode === 'book') {
                setEditingHtml(htmlContent);
            } else {
                setLabGuideEditingHtml(htmlContent);
            }
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
                                if (viewMode === 'book') {
                                    setEditingHtml(editorRef.current?.innerHTML ?? '');
                                } else {
                                    setLabGuideEditingHtml(editorRef.current?.innerHTML ?? '');
                                }
                            } catch (err) {
                                console.error('Failed to upload pasted file image:', err);
                            }
                        })();
                    } catch (err) {
                        console.error('Failed to handle pasted file image:', err);
                    }
                }
                // update editingHtml after inserts
                if (viewMode === 'book') {
                    setEditingHtml(editorRef.current?.innerHTML ?? '');
                } else {
                    setLabGuideEditingHtml(editorRef.current?.innerHTML ?? '');
                }
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
        console.log('=== Finalizing Edit START ===');
        const startTime = performance.now();

        const html = (viewMode === 'book' ? editingHtml : labGuideEditingHtml) ?? editorRef.current?.innerHTML ?? '';
        console.log('HTML to convert length:', html.length);

        const markdown = convertHtmlToMarkdown(html);
        console.log('Markdown result length:', markdown.length);

        if (viewMode === 'book') {
            if (!bookData) return;
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

            setEditingHtml(null);
        } else {
            if (!labGuideData) return;
            // Update the specific lesson in labGuideData
            const updatedLessons = [...(labGuideData.lessons || [])];
            if (updatedLessons[currentLabLessonIndex]) {
                updatedLessons[currentLabLessonIndex] = {
                    ...updatedLessons[currentLabLessonIndex],
                    content: markdown
                };
            }

            const updatedLabData = {
                ...labGuideData,
                lessons: updatedLessons
            };

            setLabGuideData(updatedLabData);

            // Process images
            const contentWithImages = await replaceS3UrlsWithDataUrls(markdown);
            updatedLessons[currentLabLessonIndex].content = contentWithImages;
            setLabGuideData({
                ...updatedLabData,
                lessons: updatedLessons
            });

            setLabGuideEditingHtml(null);
        }

        // Exit edit mode - the useEffect will handle re-rendering the formatted HTML
        setIsEditing(false);

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
            // Update editingHtml after command
            const editor = editorRef.current;
            if (editor) {
                if (viewMode === 'book') {
                    setEditingHtml(editor.innerHTML);
                } else {
                    setLabGuideEditingHtml(editor.innerHTML);
                }
            }
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
        if (editor) {
            if (viewMode === 'book') {
                setEditingHtml(editor.innerHTML);
            } else {
                setLabGuideEditingHtml(editor.innerHTML);
            }
        }

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

            if (selectedPPTVersion === 'original') {
                // User wants original book - construct the original book path
                // Original books are typically at: project_folder/theory-book/Generated_Course_Book_data.json
                // or project_folder/book/Generated_Course_Book_data.json
                bookVersionKey = `${projectFolder}/${bookType}-book/Generated_Course_Book_data.json`;
                console.log('🎯 Using original book path:', bookVersionKey);
            } else if (selectedPPTVersion !== 'current') {
                // User selected a specific version from the versions list
                const version = versions.find(v => v.key === selectedPPTVersion);
                if (version) {
                    bookVersionKey = version.key;
                    console.log('🎯 Using selected version:', bookVersionKey);
                } else {
                    throw new Error('Versión seleccionada no encontrada');
                }
            }
            // For 'current', we leave bookVersionKey as null
            // and let the Lambda discover the latest _data.json file

            console.log('🎯 Generating PPT from version:', bookVersionKey || 'auto-discover latest');

            const requestBody = {
                course_bucket: import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts',
                project_folder: projectFolder,
                book_version_key: bookVersionKey, // null means auto-discover
                book_type: bookType, // 'theory' or 'lab' - tells Lambda which book to use
                model_provider: pptModelProvider,
                slides_per_lesson: 999, // High number to ensure all content is included
                use_all_content: true, // Flag to generate slides for ALL content
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
            fetch(`${API_BASE}/generate-infographic`, {
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

                console.log('✅ Infographic generated:', data);

                // Enhanced success notification for HTML infographic
                const successMessage = `✅ ¡Infografía Interactiva Generada!\n\n` +
                    `📊 ${data.total_slides} diapositivas creadas\n` +
                    `✏️ Contenido 100% editable en navegador\n` +
                    `📄 Exportable a PDF (Ctrl+P)\n` +
                    `🎨 Estilo: ${pptStyle}\n` +
                    `📝 Diapositivas por lección: ${slidesPerLesson}`;

                // Create download link for the HTML file (editable)
                if (data.html_s3_key) {
                    const htmlUrl = `https://crewai-course-artifacts.s3.amazonaws.com/${data.html_s3_key}`;
                    const pptxUrl = data.pptx_s3_key ?
                        `https://crewai-course-artifacts.s3.amazonaws.com/${data.pptx_s3_key}` : null;

                    let fullMessage = successMessage +
                        `\n\n� HTML Editable: ${htmlUrl}\n` +
                        `\n💡 Haz clic en cualquier texto para editar\n` +
                        `💾 Botón "Save Changes" para descargar versión editada\n` +
                        `📄 Botón "Download PDF" para exportar a PDF`;

                    if (pptxUrl) {
                        fullMessage += `\n\n📊 PowerPoint: ${pptxUrl}`;
                    }

                    fullMessage += `\n\n¿Deseas abrir la infografía editable ahora?`;

                    // Show notification with download option
                    if (confirm(fullMessage)) {
                        window.open(htmlUrl, '_blank');
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

    const activeBookData = viewMode === 'book' ? bookData : labGuideData;
    const activeIndex = viewMode === 'book' ? currentLessonIndex : currentLabLessonIndex;
    const setActiveIndex = viewMode === 'book' ? setCurrentLessonIndex : setCurrentLabLessonIndex;
    const currentLesson = activeBookData?.lessons?.[activeIndex] || { title: '', content: '' };

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
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginRight: '15px' }}>
                    <button
                        onClick={() => navigate('/generador-contenidos/book-builder')}
                        className="nav-icon-btn"
                        title="Volver a la lista"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.5rem' }}
                    >
                        ⬅️
                    </button>
                    <button
                        onClick={() => navigate('/')}
                        className="nav-icon-btn"
                        title="Ir al inicio"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.5rem' }}
                    >
                        🏠
                    </button>
                </div>
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
                <div className="lesson-navigator" data-view-mode={viewMode}>
                    <h3>{viewMode === 'book' ? 'Contenido del Libro' : 'Contenido del Lab Guide'}</h3>
                    <div className="navigator-stats">
                        {Object.keys(groupLessonsByModule()).length} módulos · {activeBookData?.lessons?.length || 0} lecciones
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
                                value={viewMode === 'book' ? newVersionName : newLabGuideVersionName}
                                onChange={e => viewMode === 'book' ? setNewVersionName(e.target.value) : setNewLabGuideVersionName(e.target.value)}
                                placeholder={viewMode === 'book' ? "Nombre de la versión" : "Nombre de la versión del Lab Guide"}
                                className="version-name-input"
                            />
                            <button
                                onClick={viewMode === 'book' ? saveVersion : saveLabGuide}
                                disabled={viewMode === 'book' ? !newVersionName.trim() : !newLabGuideVersionName.trim()}
                                className="btn-save-version"
                                title={viewMode === 'book' ? "Guardar una nueva versión de este libro" : "Guardar una nueva versión del Lab Guide"}
                            >
                                {viewMode === 'book' ? "💾 Guardar Versión" : "💾 Guardar Versión Lab Guide"}
                            </button>
                        </div>
                    )}
                    <div className="lesson-header">
                        <h3>{currentLesson.title}</h3>
                        <div className="lesson-stats">Palabras: {currentLesson.content ? currentLesson.content.split(/\s+/).filter(Boolean).length : 0}</div>
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
            </div>

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
                                    <li>Se generará una presentación con TODO el contenido del libro</li>
                                    <li>El número de diapositivas se ajustará automáticamente según el contenido</li>
                                    <li>Las imágenes del libro se incluirán automáticamente</li>
                                    <li>El proceso puede tardar 5-15 minutos dependiendo del tamaño</li>
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

    );
}

export default BookEditor;