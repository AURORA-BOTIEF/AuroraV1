// src/components/BookBuilderPage.jsx
import React, { useState, useEffect } from 'react';
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

    const loadProjects = async () => {
        try {
            setLoading(true);

            const response = await fetch(`${API_BASE}/list-projects`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Response error:', errorText);
                throw new Error(`Failed to load projects: ${response.status} ${response.statusText}`);
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

            const response = await fetch(`${API_BASE}/build-book`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Build book error:', errorText);
                throw new Error(`Failed to build book: ${response.status}`);
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

    const openBookEditor = (project, bookType = 'theory') => {
        setSelectedProject({ ...project, bookType });
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
                bookType={selectedProject.bookType || 'theory'}
                onClose={closeBookEditor}
            />
        );
    }

    return (
        <div className="book-builder-page">
            <div className="page-header">
                <h1>Editor de Libros</h1>
                <p>Visualiza y edita los libros completos de tus cursos con texto e imágenes</p>
            </div>

            <div className="search-section">
                <input
                    type="text"
                    placeholder="Buscar proyectos..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="search-input"
                />
            </div>

            {loading ? (
                <div className="loading">Cargando proyectos...</div>
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
                                    <span>{project.lessonCount} lecciones</span>
                                    {project.created && (
                                        <span>Creado: {new Date(project.created).toLocaleDateString('es-ES')}</span>
                                    )}
                                </div>
                            </div>

                            <div className="project-actions">
                                {project.hasBook ? (
                                    <>
                                        <button
                                            className="btn-primary"
                                            onClick={() => openBookEditor(project, 'theory')}
                                        >
                                            📚 Libro Teoría
                                        </button>
                                        {project.hasLabGuide && (
                                            <button
                                                className="btn-primary"
                                                onClick={() => openBookEditor(project, 'lab')}
                                                style={{ marginLeft: '10px' }}
                                            >
                                                🧪 Guía de Labs
                                            </button>
                                        )}
                                    </>
                                ) : (
                                    <div className="no-book-message">
                                        <span>📖 El libro se generará automáticamente con el curso</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}

                    {filteredProjects.length === 0 && (
                        <div className="no-projects">
                            <h3>No se encontraron proyectos</h3>
                            <p>Primero genera algunos cursos para poder crear libros a partir de ellos.</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default BookBuilderPage;