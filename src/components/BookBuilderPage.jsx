// src/components/BookBuilderPage.jsx
import React, { useState, useEffect } from 'react';
import { Auth } from 'aws-amplify';
import { SignatureV4 } from '@aws-sdk/signature-v4';
import { Sha256 } from '@aws-crypto/sha256-js';
import BookEditor from './BookEditor';
import './BookBuilderPage.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;

function BookBuilderPage() {
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedProject, setSelectedProject] = useState(null);
    const [showEditor, setShowEditor] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');

    useEffect(() => {
        loadProjects();
    }, []);

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

    const loadProjects = async () => {
        try {
            setLoading(true);

            const response = await makeSignedRequest(`${API_BASE}/list-projects`, {
                method: 'GET'
            });

            if (!response.ok) {
                throw new Error('Failed to load projects');
            }

            const data = await response.json();
            setProjects(data.projects || []);
        } catch (error) {
            console.error('Error loading projects:', error);
            alert('Error loading projects: ' + error.message);
        } finally {
            setLoading(false);
        }
    };

    const buildBook = async (projectFolder) => {
        try {
            const body = {
                project_folder: projectFolder,
                course_bucket: 'crewai-course-artifacts'
            };

            const response = await makeSignedRequest(`${API_BASE}/build-book`, {
                method: 'POST',
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                throw new Error('Failed to build book');
            }

            const result = await response.json();
            alert('Book built successfully!');

            // Refresh projects to show the new book
            loadProjects();
        } catch (error) {
            console.error('Error building book:', error);
            alert('Error building book: ' + error.message);
        }
    };

    const openBookEditor = (project) => {
        setSelectedProject(project);
        setShowEditor(true);
    };

    const closeBookEditor = () => {
        setShowEditor(false);
        setSelectedProject(null);
        loadProjects(); // Refresh in case book was modified
    };

    const filteredProjects = projects.filter(project =>
        project.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        project.folder.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (showEditor && selectedProject) {
        return (
            <BookEditor
                projectFolder={selectedProject.folder}
                onClose={closeBookEditor}
            />
        );
    }

    return (
        <div className="book-builder-page">
            <div className="page-header">
                <h1>Book Builder</h1>
                <p>Create and edit complete course books with text and images</p>
            </div>

            <div className="search-section">
                <input
                    type="text"
                    placeholder="Search projects..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="search-input"
                />
            </div>

            {loading ? (
                <div className="loading">Loading projects...</div>
            ) : (
                <div className="projects-grid">
                    {filteredProjects.map((project) => (
                        <div key={project.folder} className="project-card">
                            <div className="project-header">
                                <h3>{project.title}</h3>
                                <span className="project-folder">{project.folder}</span>
                            </div>

                            <div className="project-info">
                                <p>{project.description}</p>
                                <div className="project-stats">
                                    <span>{project.lessonCount} lessons</span>
                                    {project.created && (
                                        <span>Created: {new Date(project.created).toLocaleDateString()}</span>
                                    )}
                                </div>
                            </div>

                            <div className="project-actions">
                                {project.hasBook ? (
                                    <button
                                        className="btn-primary"
                                        onClick={() => openBookEditor(project)}
                                    >
                                        Edit Book
                                    </button>
                                ) : (
                                    <button
                                        className="btn-secondary"
                                        onClick={() => buildBook(project.folder)}
                                    >
                                        Build Book
                                    </button>
                                )}

                                <button
                                    className="btn-outline"
                                    onClick={() => openBookEditor(project)}
                                >
                                    Open Editor
                                </button>
                            </div>
                        </div>
                    ))}

                    {filteredProjects.length === 0 && (
                        <div className="no-projects">
                            <h3>No projects found</h3>
                            <p>Generate some courses first to create books from them.</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default BookBuilderPage;