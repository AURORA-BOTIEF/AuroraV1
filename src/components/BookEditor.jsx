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
                throw new Error('Failed to load book data');
            }

            const data = await response.json();

            if (data.bookData) {
                setBookData(data.bookData);
            } else if (data.bookContent) {
                // Parse markdown into book structure
                const parsedBook = parseMarkdownToBook(data.bookContent);
                setBookData(parsedBook);
            } else {
                throw new Error('No book data available');
            }
        } catch (error) {
            console.error('Error loading book:', error);
            alert('Error loading book: ' + error.message);
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
                { name: 'Current', timestamp: new Date().toISOString(), isCurrent: true }
            ]);
        } catch (error) {
            console.error('Error loading versions:', error);
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
                throw new Error('Failed to save book');
            }

            const result = await response.json();
            alert('Book saved successfully!');
        } catch (error) {
            console.error('Error saving book:', error);
            alert('Error saving book: ' + error.message);
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
            alert('Please enter a version name');
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
                throw new Error('Failed to get upload URL');
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
                throw new Error('Failed to upload version');
            }

            setVersions(prev => [...prev, {
                name: newVersionName,
                timestamp: versionData.saved_at,
                key: versionKey
            }]);

            setNewVersionName('');
            alert('Version saved successfully!');
        } catch (error) {
            console.error('Error saving version:', error);
            alert('Error saving version: ' + error.message);
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

    const addTextBlock = () => {
        const currentLesson = bookData.lessons[currentLessonIndex];
        const newContent = currentLesson.content + '\n\n## New Section\n\nAdd your content here...\n\n';
        updateLessonContent(currentLessonIndex, newContent);
    };

    const addImagePlaceholder = () => {
        const currentLesson = bookData.lessons[currentLessonIndex];
        const newContent = currentLesson.content + '\n\n![Image Description](image-url-here)\n\n';
        updateLessonContent(currentLessonIndex, newContent);
    };

    const removeContent = () => {
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            range.deleteContents();
            const currentLesson = bookData.lessons[currentLessonIndex];
            const newContent = editorRef.current.innerHTML;
            updateLessonContent(currentLessonIndex, newContent);
        }
    };

    if (loading) {
        return <div className="book-editor-loading">Loading book...</div>;
    }

    if (!bookData) {
        return <div className="book-editor-error">No book data found for this project.</div>;
    }

    const currentLesson = bookData.lessons[currentLessonIndex];

    return (
        <div className="book-editor">
            <div className="book-editor-header">
                <h2>{bookData.metadata.title}</h2>
                <div className="book-editor-actions">
                    <button onClick={saveBook} disabled={saving}>
                        {saving ? 'Saving...' : 'Save Book'}
                    </button>
                    <button onClick={() => setShowVersionHistory(!showVersionHistory)}>
                        Versions ({versions.length})
                    </button>
                    <button onClick={onClose}>Close</button>
                </div>
            </div>

            {showVersionHistory && (
                <div className="version-history">
                    <h3>Version History</h3>
                    <div className="version-list">
                        {versions.map((version, index) => (
                            <div key={index} className={`version-item ${version.isCurrent ? 'current' : ''}`}>
                                <span>{version.name}</span>
                                <span>{new Date(version.timestamp).toLocaleString()}</span>
                            </div>
                        ))}
                    </div>
                    <div className="save-version">
                        <input
                            type="text"
                            placeholder="Version name"
                            value={newVersionName}
                            onChange={(e) => setNewVersionName(e.target.value)}
                        />
                        <button onClick={saveVersion}>Save Version</button>
                    </div>
                </div>
            )}

            <div className="book-editor-content">
                <div className="lesson-navigator">
                    <h3>Lessons</h3>
                    <div className="lesson-list">
                        {bookData.lessons.map((lesson, index) => (
                            <div
                                key={index}
                                className={`lesson-item ${index === currentLessonIndex ? 'active' : ''}`}
                                onClick={() => setCurrentLessonIndex(index)}
                            >
                                {lesson.title}
                            </div>
                        ))}
                    </div>
                </div>

                <div className="lesson-editor">
                    <div className="editor-toolbar">
                        <button onClick={addTextBlock}>Add Text Block</button>
                        <button onClick={addImagePlaceholder}>Add Image</button>
                        <button onClick={removeContent}>Remove Selected</button>
                    </div>

                    <div className="lesson-header">
                        <h3>{currentLesson.title}</h3>
                        <div className="lesson-stats">
                            {currentLesson.content.split(/\s+/).length} words
                        </div>
                    </div>

                    <div
                        className="content-editor"
                        ref={editorRef}
                        contentEditable
                        dangerouslySetInnerHTML={{ __html: formatContentForEditing(currentLesson.content) }}
                        onInput={(e) => updateLessonContent(currentLessonIndex, e.target.innerHTML)}
                    />
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