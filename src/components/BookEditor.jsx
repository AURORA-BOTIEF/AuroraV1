// src/components/BookEditor.jsx
import React, { useState, useEffect, useRef } from 'react';
import { replaceS3UrlsWithDataUrls, uploadImageToS3 } from '../utils/s3ImageLoader';
import { S3Client, PutObjectCommand, ListObjectsV2Command, GetObjectCommand } from '@aws-sdk/client-s3';
import { Upload } from '@aws-sdk/lib-storage';
import { fetchAuthSession } from 'aws-amplify/auth';
import './BookEditor.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;
const IDENTITY_POOL_ID = import.meta.env.VITE_IDENTITY_POOL_ID || import.meta.env.VITE_AWS_IDENTITY_POOL_ID || '';
const AWS_REGION = import.meta.env.VITE_AWS_REGION || 'us-east-1';

function BookEditor({ projectFolder, onClose }) {
    const [bookData, setBookData] = useState(null);
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
                title: 'Course Book',
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
        // Basic conversions: headings, bold, italic, images, paragraphs, line breaks
        let html = markdown
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/gim, '<em>$1</em>')
            .replace(/!\[([^\]]*)\]\(([^)]+)\)/gim, '<img alt="$1" src="$2" />')
            .replace(/\n\n+/gim, '</p><p>')
            .replace(/\n/gim, '<br/>');
        // Wrap in paragraph if not starting with block
        if (!html.startsWith('<')) html = `<p>${html}</p>`;
        // Ensure paragraphs are well formed
        html = html.replace(/<p><\/p>/g, '');
        if (!html.startsWith('<p') && !html.startsWith('<h')) html = `<p>${html}</p>`;
        return html;
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

    const viewVersion = async (version) => {
        try {
            setViewingVersion(version);
            setViewingContent('Cargando...');
            const session = await fetchAuthSession();
            if (!session || !session.credentials) throw new Error('No credentials');
            const { S3Client, GetObjectCommand } = await import('@aws-sdk/client-s3');
            const s3 = new S3Client({ region: AWS_REGION, credentials: session.credentials });
            const bucket = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';

            // Prefer markdown snapshot: replace .json with .md
            const mdKey = version.key.replace(/\.json$/i, '.md');
            try {
                const resp = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: mdKey }));
                const text = await resp.Body.transformToString();
                setViewingContent(text);
                return;
            } catch (e) {
                // fallback to JSON
            }

            // Fallback: fetch JSON and pretty-print
            const resp2 = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: version.key }));
            const jsonText = await resp2.Body.transformToString();
            setViewingContent(jsonText);
        } catch (e) {
            console.error('Failed to load version content:', e);
            setViewingContent('Error cargando la versión: ' + String(e));
        }
    };

    // Load a version into the editor for editing. This will NOT overwrite the original files.
    const editVersion = async (version) => {
        try {
            const session = await fetchAuthSession();
            if (!session || !session.credentials) throw new Error('No credentials');
            const { S3Client, GetObjectCommand } = await import('@aws-sdk/client-s3');
            const s3 = new S3Client({ region: AWS_REGION, credentials: session.credentials });
            const resp = await s3.send(new GetObjectCommand({ Bucket: import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts', Key: version.key }));
            const jsonText = await resp.Body.transformToString();
            const parsed = JSON.parse(jsonText);
            // Set bookData to parsed version and enter edit mode
            setBookData(parsed);
            setCurrentLessonIndex(0);
            setIsEditing(true);
            // Set editor HTML to the first lesson content formatted for editing
            const firstHtml = formatContentForEditing(parsed.lessons?.[0]?.content || '');
            try { editorRef.current && (editorRef.current.innerHTML = firstHtml); } catch (e) { }
            setEditingHtml(firstHtml);
            alert('Versión cargada para edición. Recuerda: cambios solo se guardarán al crear una "Guardar Versión" manual.');
        } catch (e) {
            console.error('Failed to load version for edit:', e);
            alert('Error al cargar versión para editar: ' + String(e));
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

            // Try to avoid multipart uploads (and checksum complexity) by using a large partSize
            // so small/medium files are uploaded in a single request. If lib-storage still
            // performs multipart upload and S3 responds with a checksum-related error, fall
            // back to a single PutObjectCommand.
            const bucketName = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';
            const MAX_SINGLE_PUT = 64 * 1024 * 1024; // 64 MB

            const uploader = new Upload({
                client: s3,
                params: {
                    Bucket: bucketName,
                    Key: s3Key,
                    Body: bookJson,
                    ContentType: 'application/json',
                    // Ensure bucket owner gets full control so Lambda (bucket owner)
                    // can read objects uploaded by Cognito-authenticated identities.

                },
                queueSize: 4,
                partSize: Math.min(MAX_SINGLE_PUT, Math.max(5 * 1024 * 1024, bookJson.length + 1)),
            });

            uploader.on('httpUploadProgress', (progress) => {
                console.debug('Upload progress', progress);
            });

            try {
                await uploader.done();
            } catch (err) {
                console.warn('Upload failed, attempting single PutObject fallback:', err && err.message);
                const msg = String(err && err.message || '').toLowerCase();
                if (msg.includes('crc32') || msg.includes('checksum')) {
                    // Retry with single PutObject and the same ACL so bucket owner can read
                    await s3.send(new PutObjectCommand({
                        Bucket: bucketName,
                        Key: s3Key,
                        Body: bookJson,
                        ContentType: 'application/json',

                    }));
                } else {
                    throw err;
                }
            }

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
            const versionData = {
                ...bookData,
                version_name: newVersionName,
                saved_at: new Date().toISOString()
            };

            const timestamp = Date.now();
            const safeVersionName = newVersionName.replace(/\s+/g, '_');
            // Original filename (keep integrity): prefer metadata.filename if present, else default
            const originalFilename = (bookData && (bookData.filename || (bookData.metadata && bookData.metadata.filename))) || 'course_book_data.json';
            const baseName = originalFilename.replace(/\.[^/.]+$/, '');
            const versionJsonName = `${baseName}_${timestamp}_${safeVersionName}.json`;
            const versionKey = `${projectFolder}/versions/${versionJsonName}`;
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
            const uploader = new Upload({
                client: s3,
                params: {
                    Bucket: bucketName,
                    Key: versionKey,
                    Body: JSON.stringify(versionData, null, 2),
                    ContentType: 'application/json',

                },
                queueSize: 2,
                partSize: 5 * 1024 * 1024,
            });

            try {
                await uploader.done();
            } catch (err) {
                console.warn('Version upload failed, attempting single PutObject fallback:', err && err.message);
                const msg = String(err && err.message || '').toLowerCase();
                if (msg.includes('crc32') || msg.includes('checksum')) {
                    await s3.send(new PutObjectCommand({
                        Bucket: bucketName,
                        Key: versionKey,
                        Body: JSON.stringify(versionData, null, 2),
                        ContentType: 'application/json',

                    }));
                } else {
                    throw err;
                }
            }

            // Also save a markdown snapshot for easier previewing
            try {
                const markdown = generateMarkdownFromBook(versionData);
                const mdName = `${baseName}_${timestamp}_${safeVersionName}.md`;
                const mdKey = `${projectFolder}/versions/${mdName}`;
                // Try single PutObject for the markdown snapshot
                await s3.send(new PutObjectCommand({ Bucket: bucketName, Key: mdKey, Body: markdown, ContentType: 'text/markdown' }));
            } catch (e) {
                console.warn('Failed to save markdown snapshot for version:', e);
            }

            setVersions(prev => [...prev, {
                name: newVersionName,
                timestamp: versionData.saved_at,
                key: versionKey
            }]);

            setNewVersionName('');
            alert('¡Versión guardada exitosamente!');
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
                for (const file of files) {
                    try {
                        const s3Url = await uploadImageToS3(file, projectFolder);
                        // Insert image at caret
                        insertHtmlAtCursor(`<img src="${s3Url}" alt="pasted-image" />`);
                    } catch (err) {
                        console.error('Failed to upload pasted file image:', err);
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
            editorRef.current && (editorRef.current.innerHTML += html);
            return;
        }
        const range = sel.getRangeAt(0);
        range.deleteContents();
        const el = document.createElement('div');
        el.innerHTML = html;
        const frag = document.createDocumentFragment();
        let node, lastNode;
        while ((node = el.firstChild)) {
            lastNode = frag.appendChild(node);
        }
        range.insertNode(frag);
        // Move selection to after inserted content
        if (lastNode) {
            range.setStartAfter(lastNode);
            range.setEndAfter(lastNode);
            sel.removeAllRanges();
            sel.addRange(range);
        }
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
        // Basic HTML to Markdown conversion
        return html
            .replace(/<h1>(.*?)<\/h1>/g, '# $1\n')
            .replace(/<h2>(.*?)<\/h2>/g, '## $1\n')
            .replace(/<h3>(.*?)<\/h3>/g, '### $1\n')
            .replace(/<strong>(.*?)<\/strong>/g, '**$1**')
            .replace(/<em>(.*?)<\/em>/g, '*$1*')
            // Convert images back to markdown with double brackets if they have VISUAL in alt
            .replace(/<img[^>]*alt="(\[?VISUAL[^\]"]*\]?)"[^>]*src="([^"]*)"[^>]*>/gi, '![[$1]]($2)')
            // Convert other images to normal markdown
            .replace(/<img[^>]*alt="([^"]*)"[^>]*src="([^"]*)"[^>]*>/gi, '![$1]($2)')
            .replace(/<\/p><p>/g, '\n\n')
            .replace(/<br\s*\/?>/g, '\n')
            .replace(/<[^>]+>/g, ''); // Remove remaining HTML tags
    };

    // Save editingHtml back into bookData (convert to markdown) when finalizing edit
    const finalizeEditing = () => {
        if (!bookData) return;
        const html = editingHtml ?? editorRef.current?.innerHTML ?? '';
        const markdown = convertHtmlToMarkdown(html);
        updateLessonContent(currentLessonIndex, markdown);
        setIsEditing(false);
    };

    // Basic execCommand wrapper for toolbar actions. Modern browsers may deprecate execCommand,
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
        if (!sel || sel.rangeCount === 0) return;
        const node = sel.anchorNode && sel.anchorNode.nodeType === 3 ? sel.anchorNode.parentNode : sel.anchorNode;
        if (!node) return;
        formatClipboard.current = node.getAttribute ? node.getAttribute('style') : null;
        // Visual feedback could be added
    }

    function handleApplyFormat() {
        if (!formatClipboard.current) return;
        const sel = window.getSelection();
        if (!sel || sel.rangeCount === 0) return;
        const range = sel.getRangeAt(0);
        const span = document.createElement('span');
        if (formatClipboard.current) span.setAttribute('style', formatClipboard.current);
        span.appendChild(range.extractContents());
        range.insertNode(span);
        const editor = editorRef.current;
        if (editor) setEditingHtml(editor.innerHTML);
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
            <div className="book-editor-header">
                <h2>{bookData.metadata.title}</h2>
                <div className="book-editor-actions">
                    <button
                        className={isEditing ? 'btn-editing' : 'btn-edit'}
                        onClick={() => {
                            if (isEditing) {
                                finalizeEditing();
                            } else {
                                setIsEditing(true);
                            }
                        }}
                    >
                        {isEditing ? '✓ Finalizar Edición' : '✏️ Editar'}
                    </button>
                    {/* Save button intentionally removed: use "Guardar Versión" to create versions */}
                    <button onClick={() => setShowVersionHistory(!showVersionHistory)}>
                        📋 Versiones ({versions.length})
                    </button>
                    <button onClick={onClose} className="btn-close">✕ Cerrar</button>
                </div>
            </div>
            {showVersionHistory && (
                <div className="version-history">
                    <h3>Historial de Versiones</h3>
                    <div className="version-list">
                        {versions.map((version, index) => (
                            <div key={index} className={`version-item ${version.isCurrent ? 'current' : ''}`}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                        <button className="version-name" onClick={() => viewVersion(version)}>Ver</button>
                                        <button onClick={() => editVersion(version)}>Editar</button>
                                        <div style={{ marginLeft: '0.5rem' }}>{version.name}</div>
                                    </div>
                                    <div className="version-meta">{version.timestamp ? new Date(version.timestamp).toLocaleString('es-ES') : ''}</div>
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
                    <div className="editor-toolbar">
                        <button onClick={() => execCommand('bold')}>B</button>
                        <button onClick={() => execCommand('italic')}>I</button>
                        <button onClick={() => handleCopyFormat()}>Copiar Formato</button>
                        <button onClick={() => handleApplyFormat()}>Aplicar Formato</button>
                    </div>
                    <div className="lesson-header">
                        <h3>{currentLesson.title}</h3>
                        <div className="lesson-stats">Palabras: {currentLesson.content.split(/\s+/).filter(Boolean).length}</div>
                    </div>
                    <div className="editor-container">
                        {useLexical && LexicalEditorWrapper ? (
                            <LexicalEditorWrapper
                                initialHtml={editingHtml ?? formatContentForEditing(currentLesson.content)}
                                readOnly={!isEditing}
                                onChange={(html) => setEditingHtml(html)}
                                projectFolder={projectFolder}
                            />
                        ) : useQuillEditor && ReactQuill ? (
                            <ReactQuill
                                ref={quillRef}
                                theme="snow"
                                value={editingHtml ?? formatContentForEditing(currentLesson.content)}
                                readOnly={!isEditing}
                                onChange={(html) => { setEditingHtml(html); }}
                            />
                        ) : (
                            <div
                                ref={editorRef}
                                className="content-editor"
                                contentEditable={isEditing}
                                suppressContentEditableWarning={true}
                                onInput={handleContentChange}
                                onPaste={handlePaste}
                            />
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default BookEditor;