// src/components/BookEditor.jsx
import React, { useState, useEffect, useRef } from 'react';
import { replaceS3UrlsWithDataUrls, uploadImageToS3 } from '../utils/s3ImageLoader';
import { S3Client, PutObjectCommand, ListObjectsV2Command, GetObjectCommand } from '@aws-sdk/client-s3';
import { fetchAuthSession } from 'aws-amplify/auth';
import './BookEditor.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;
const IDENTITY_POOL_ID = import.meta.env.VITE_IDENTITY_POOL_ID || import.meta.env.VITE_AWS_IDENTITY_POOL_ID || '';
const AWS_REGION = import.meta.env.VITE_AWS_REGION || 'us-east-1';

function BookEditor({ projectFolder, onClose }) {
    const [bookData, setBookData] = useState(null);
    const [originalBookData, setOriginalBookData] = useState(null); // Store original for "Original" version
    const [loading, setLoading] = useState(true);
    const [loadingImages, setLoadingImages] = useState(false);
    const [saving, setSaving] = useState(false);
    const [currentLessonIndex, setCurrentLessonIndex] = useState(0);
    const [isEditing, setIsEditing] = useState(false);
    const [versions, setVersions] = useState([]);
    const [sessionVersionKey, setSessionVersionKey] = useState(null);
    const [showVersionHistory, setShowVersionHistory] = useState(false);
    const [newVersionName, setNewVersionName] = useState('');
    const [viewingVersion, setViewingVersion] = useState(null);
    const [viewingContent, setViewingContent] = useState('');
    const [loadingVersion, setLoadingVersion] = useState(false);
    const editorRef = useRef(null);
    const lastAppliedLessonRef = useRef({ index: null, content: null, isEditing: null });
    const [editingHtml, setEditingHtml] = useState(null);
    const selectionRef = useRef(null);
    // (Quill removed) we prefer Lexical editor; contentEditable is fallback

    useEffect(() => {
        if (projectFolder) {
            loadBook();
            loadVersions();
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

            const response = await fetch(`${API_BASE}/load-book/${projectFolder}`, {
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

            let bookToSet = null;

            // Priority: inline bookData > inline bookContent > presigned URLs
            if (data.bookData) {
                // Process images in bookData lessons
                console.log('Loading images from S3 (inlined bookData)...');
                for (let lesson of data.bookData.lessons) {
                    if (lesson.content) {
                        lesson.content = await replaceS3UrlsWithDataUrls(lesson.content);
                    }
                }
                bookToSet = data.bookData;
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
                const fetchedJson = await jsonResp.json();
                // Process images
                for (let lesson of fetchedJson.lessons || []) {
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

        const closeLists = () => {
            if (inUl) { out += '</ul>'; inUl = false; }
            if (inOl) { out += '</ol>'; inOl = false; }
        };

        for (let rawLine of lines) {
            const line = rawLine.trimEnd();
            if (/^\s*$/.test(line)) {
                // blank line closes lists and adds paragraph separation
                closeLists();
                out += '<p></p>';
                continue;
            }

            // Headings h1..h6 (support ###### .. #)
            const hMatch = line.match(/^(#{1,6})\s+(.*)$/);
            if (hMatch) {
                closeLists();
                const level = Math.min(6, hMatch[1].length);
                out += `<h${level}>${hMatch[2].trim()}</h${level}>`;
                console.log(`Converted heading: "${line}" -> <h${level}>`);
                continue;
            }

            // Blockquote
            const bq = line.match(/^>\s?(.*)$/);
            if (bq) {
                closeLists();
                out += `<blockquote>${bq[1]}</blockquote>`;
                continue;
            }

            // Unordered list item
            const ul = line.match(/^[-\*]\s+(.*)$/);
            if (ul) {
                if (!inUl) { closeLists(); out += '<ul>'; inUl = true; }
                out += `<li>${ul[1]}</li>`;
                continue;
            }

            // Ordered list item
            const ol = line.match(/^\d+\.\s+(.*)$/);
            if (ol) {
                if (!inOl) { closeLists(); out += '<ol>'; inOl = true; }
                out += `<li>${ol[1]}</li>`;
                continue;
            }

            // Check if this line contains an image markdown (including those with long data URLs)
            // Support both ![alt](url) and ![[VISUAL: description]](url) formats
            const imgMatch = line.match(/!\[{1,2}([^\]]*)\]{1,2}\(([^)]+)\)/);
            if (imgMatch) {
                closeLists();
                const alt = imgMatch[1];
                const src = imgMatch[2];
                // Add styling to ensure images display properly
                out += `<p style="text-align: center;"><img alt="${alt}" src="${src}" style="max-width: 100%; height: auto; display: inline-block;" /></p>`;
                continue;
            }

            // Inline formatting: bold and emphasis
            let inline = line
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>');

            // If the line contains HTML-like block tags already, preserve them
            if (/^<\/?(p|div|h\d|ul|ol|li|img|blockquote|span)/i.test(inline)) {
                closeLists();
                out += inline;
            } else {
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
    }, [currentLessonIndex, isEditing, bookData]);

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

    const currentLesson = bookData.lessons?.[currentLessonIndex] || { title: '', content: '' };

    return (
        <div className="book-editor">
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
                    <button
                        className={isEditing ? 'btn-editing' : 'btn-edit'}
                        onClick={() => {
                            console.log('=== Edit button clicked ===', isEditing ? 'Finalizing' : 'Entering edit mode');
                            const startTime = performance.now();

                            if (isEditing) {
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
                        📋 Versiones ({versions.length + 1})
                    </button>
                    <button onClick={onClose} className="btn-close">✕ Cerrar</button>
                </div>
            </div>
            {showVersionHistory && (
                <div className="version-history">
                    <h3>Historial de Versiones</h3>
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
                </div>
            )}
            <div className="book-editor-content">
                <div className="lesson-navigator">
                    <h3>Lecciones</h3>
                    <div className="lesson-list">
                        {bookData.lessons.map((lesson, idx) => (
                            <div key={idx} className={`lesson-item ${idx === currentLessonIndex ? 'active' : ''}`} onClick={() => setCurrentLessonIndex(idx)}>
                                {lesson.title || `Lección ${idx + 1}`}
                            </div>
                        ))}
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
                            // Use the classic contentEditable editor while editing so the
                            // user sees the same rendered HTML (images, headings, lists)
                            // they see in read-only mode. This keeps the toolbar and
                            // execCommand behaviour working and avoids Lexical image
                            // node registration complexity.
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
                            // Read-only visualization: use contentEditable with HTML rendering
                            // The useEffect will populate this with formatted HTML
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
        </div>
    );
}

export default BookEditor;