// src/components/BookEditor.jsx
import React, { useState, useEffect, useRef } from 'react';
import { Auth } from 'aws-amplify';
import { S3Client, GetObjectCommand, PutObjectCommand } from '@aws-sdk/client-s3';
import { SignatureV4 } from '@aws-sdk/signature-v4';
import { Sha256 } from '@aws-crypto/sha256-js';
import './BookEditor.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;
const BOOK_API_ENDPOINT = `${API_BASE}/book`;

function BookEditor({ projectFolder, onClose }) {
    const [bookData, setBookData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [currentLessonIndex, setCurrentLessonIndex] = useState(0);
    const [isEditing, setIsEditing] = useState(false);
    const [versions, setVersions] = useState([]);
    const [showVersionHistory, setShowVersionHistory] = useState(false);
    const [newVersionName, setNewVersionName] = useState('');
    const editorRef = useRef(null);

    useEffect(() => {
        if (projectFolder) {
            loadBook();
            loadVersions();
        }
    }, [projectFolder]);

    const makeSignedRequest = async (url, options = {}) => {
        const credentials = await Auth.currentCredentials();
        const signer = new SignatureV4({
            credentials: {
                accessKeyId: credentials.accessKeyId,
                secretAccessKey: credentials.secretAccessKey,
                sessionToken: credentials.sessionToken,
            },
            region: 'us-east-1',
            service: 'execute-api',
            sha256: Sha256,
        });

        const urlObj = new URL(url);
        const request = {
            method: options.method || 'GET',
            hostname: urlObj.hostname,
            path: urlObj.pathname + urlObj.search,
            protocol: urlObj.protocol,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        };

        if (options.body) {
            request.body = options.body;
            request.headers['Content-Type'] = 'application/json';
        }

        const signedRequest = await signer.sign(request);
        return fetch(url, {
            method: signedRequest.method,
            headers: signedRequest.headers,
            body: options.body,
        });
    };

    const loadBook = async () => {
        try {
            setLoading(true);

            const response = await makeSignedRequest(`${API_BASE}/load-book/${projectFolder}`, {
                method: 'GET'
            });

            if (!response.ok) {
                throw new Error('No se pudo cargar los datos del libro');
            }

            const data = await response.json();

            if (data.bookData) {
                setBookData(data.bookData);
            } else if (data.bookContent) {
                // Parse markdown into book structure
                const parsedBook = parseMarkdownToBook(data.bookContent);
                setBookData(parsedBook);
            } else {
                throw new Error('No hay datos del libro disponibles');
            }
        } catch (error) {
            console.error('Error al cargar libro:', error);
            alert('Error al cargar libro: ' + error.message);
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

    const loadVersions = async () => {
        try {
            const credentials = await Auth.currentCredentials();
            const s3Client = new S3Client({
                region: 'us-east-1',
                credentials: {
                    accessKeyId: credentials.accessKeyId,
                    secretAccessKey: credentials.secretAccessKey,
                    sessionToken: credentials.sessionToken,
                },
            });

            // List version files
            const listCommand = {
                Bucket: 'crewai-course-artifacts',
                Prefix: `${projectFolder}/versions/`,
            };

            // For now, we'll create a simple version list
            // In a real implementation, you'd list S3 objects with version prefix
            setVersions([
                { name: 'Actual', timestamp: new Date().toISOString(), isCurrent: true }
            ]);
        } catch (error) {
            console.error('Error al cargar versiones:', error);
        }
    };

    const saveBook = async () => {
        if (!bookData) return;

        try {
            setSaving(true);

            const response = await makeSignedRequest(`${API_BASE}/save-book`, {
                method: 'POST',
                body: JSON.stringify({
                    projectFolder: projectFolder,
                    bookData: bookData
                })
            });

            if (!response.ok) {
                throw new Error('No se pudo guardar el libro');
            }

            const result = await response.json();
            alert('¡Libro guardado exitosamente!');
        } catch (error) {
            console.error('Error al guardar libro:', error);
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

            const versionKey = `${projectFolder}/versions/${Date.now()}_${newVersionName.replace(/\s+/g, '_')}.json`;

            // Get presigned URL for upload
            const presignResponse = await makeSignedRequest(`${API_BASE}/presign`, {
                method: 'POST',
                body: JSON.stringify({
                    key: versionKey,
                    contentType: 'application/json'
                })
            });

            if (!presignResponse.ok) {
                throw new Error('No se pudo obtener la URL de carga');
            }

            const { uploadUrl } = await presignResponse.json();

            // Upload the version data
            const uploadResponse = await fetch(uploadUrl, {
                method: 'PUT',
                body: JSON.stringify(versionData, null, 2),
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            if (!uploadResponse.ok) {
                throw new Error('No se pudo cargar la versión');
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

    const handleContentChange = (e) => {
        if (isEditing) {
            // Convert HTML back to markdown
            const htmlContent = e.target.innerHTML;
            const markdownContent = convertHtmlToMarkdown(htmlContent);
            updateLessonContent(currentLessonIndex, markdownContent);
        }
    };

    const convertHtmlToMarkdown = (html) => {
        // Basic HTML to Markdown conversion
        return html
            .replace(/<h1>(.*?)<\/h1>/g, '# $1\n')
            .replace(/<h2>(.*?)<\/h2>/g, '## $1\n')
            .replace(/<h3>(.*?)<\/h3>/g, '### $1\n')
            .replace(/<strong>(.*?)<\/strong>/g, '**$1**')
            .replace(/<em>(.*?)<\/em>/g, '*$1*')
            .replace(/<img alt="([^"]*)" src="([^"]*)"[^>]*>/g, '![$1]($2)')
            .replace(/<\/p><p>/g, '\n\n')
            .replace(/<br\s*\/?>/g, '\n')
            .replace(/<[^>]+>/g, ''); // Remove remaining HTML tags
    };

    if (loading) {
        return <div className="book-editor-loading">Cargando libro...</div>;
    }

    if (!bookData) {
        return <div className="book-editor-error">No se encontraron datos del libro para este proyecto.</div>;
    }

    const currentLesson = bookData.lessons[currentLessonIndex];

    return (
        <div className="book-editor">
            <div className="book-editor-header">
                <h2>{bookData.metadata.title}</h2>
                <div className="book-editor-actions">
                    <button
                        className={isEditing ? 'btn-editing' : 'btn-edit'}
                        onClick={() => setIsEditing(!isEditing)}
                    >
                        {isEditing ? '✓ Finalizar Edición' : '✏️ Editar'}
                    </button>
                    <button onClick={saveBook} disabled={saving || !isEditing}>
                        {saving ? 'Guardando...' : '💾 Guardar Libro'}
                    </button>
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
                                <span>{version.name}</span>
                                <span>{new Date(version.timestamp).toLocaleString('es-ES')}</span>
                            </div>
                        ))}
                    </div>
                    <div className="save-version">
                        <input
                            type="text"
                            placeholder="Nombre de la versión"
                            value={newVersionName}
                            onChange={(e) => setNewVersionName(e.target.value)}
                        />
                        <button onClick={saveVersion}>Guardar Versión</button>
                    </div>
                </div>
            )}

            <div className="book-editor-content">
                <div className="lesson-navigator">
                    <h3>Lecciones</h3>
                    <div className="lesson-list">
                        {bookData.lessons.map((lesson, index) => (
                            <div
                                key={index}
                                className={`lesson-item ${index === currentLessonIndex ? 'active' : ''}`}
                                onClick={() => setCurrentLessonIndex(index)}
                            >
                                <span className="lesson-number">{index + 1}</span>
                                <span className="lesson-title">{lesson.title}</span>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="lesson-editor">
                    {isEditing && (
                        <div className="editor-toolbar">
                            <div className="toolbar-info">
                                <span>💡 Edita el contenido directamente. Puedes agregar o eliminar texto e imágenes como en un editor de documentos.</span>
                            </div>
                        </div>
                    )}

                    <div className="lesson-header">
                        <h3>{currentLesson.title}</h3>
                        <div className="lesson-stats">
                            {currentLesson.content.split(/\s+/).length} palabras
                        </div>
                    </div>

                    <div
                        className={`content-editor ${isEditing ? 'editing-mode' : 'reading-mode'}`}
                        ref={editorRef}
                        contentEditable={isEditing}
                        suppressContentEditableWarning={true}
                        onInput={handleContentChange}
                        dangerouslySetInnerHTML={{ __html: formatContentForEditing(currentLesson.content) }}
                    />

                    {!isEditing && (
                        <div className="edit-hint">
                            <p>👆 Haz clic en "Editar" para modificar el contenido</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function formatContentForEditing(content) {
    // Convert markdown to basic HTML for editing
    return content
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
        .replace(/\*(.*)\*/gim, '<em>$1</em>')
        .replace(/!\[([^\]]*)\]\(([^)]*)\)/gim, '<img alt="$1" src="$2" />')
        .replace(/\n\n/gim, '</p><p>')
        .replace(/\n/gim, '<br/>');
}

export default BookEditor;