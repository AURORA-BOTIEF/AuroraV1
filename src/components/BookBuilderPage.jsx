// src/components/BookBuilderPage.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './BookBuilderPage.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;

function BookBuilderPage() {
    const navigate = useNavigate();
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');

    // Pagination state
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [limit] = useState(10);
    const [totalCount, setTotalCount] = useState(0);

    useEffect(() => {
        loadProjects(currentPage);
    }, [currentPage]);

    const loadProjects = async (page = 1) => {
        try {
            setLoading(true);

            const response = await fetch(`${API_BASE}/list-projects?page=${page}&limit=${limit}`, {
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
            setTotalPages(data.total_pages || 1);
            setTotalCount(data.total_count || 0);
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
            loadProjects(currentPage);
        } catch (error) {
            console.error('Error building book:', error);
            alert('Error building book: ' + error.message);
        }
    };

    const openBookEditor = (project, bookType = 'theory') => {
        navigate(`/book-editor/${project.folder}?bookType=${bookType}`);
    };



    // Filter locally for search within the current page
    // Note: For full dataset search, backend would need search support
    const filteredProjects = projects.filter(project =>
        project.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        project.folder.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= totalPages) {
            setCurrentPage(newPage);
        }
    };

    // Removed: if (showEditor && selectedProject) { ... } block

    return (
        <div className="book-builder-page">
            <div className="page-header">
                <h1>Editor de Libros</h1>
                <p>Visualiza y edita los libros completos de tus cursos con texto e imágenes</p>
            </div>

            <div className="search-section">
                <input
                    type="text"
                    placeholder="Buscar proyectos en esta página..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="search-input"
                />
                <div className="pagination-info">
                    Total: {totalCount} proyectos
                </div>
            </div>

            {loading ? (
                <div className="loading">Cargando proyectos...</div>
            ) : (
                <>
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
                                            <span>Creado: {project.created.split('-').reverse().join('/')}</span>
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
                                                📚 Ver/Editar Libro
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
                                <p>No hay proyectos en esta página que coincidan con tu búsqueda.</p>
                            </div>
                        )}
                    </div>

                    {/* Pagination Controls */}
                    {totalPages > 1 && (
                        <div className="pagination-controls">
                            <button
                                onClick={() => handlePageChange(currentPage - 1)}
                                disabled={currentPage === 1}
                                className="pagination-btn"
                            >
                                &laquo; Anterior
                            </button>

                            <span className="pagination-status">
                                Página {currentPage} de {totalPages}
                            </span>

                            <button
                                onClick={() => handlePageChange(currentPage + 1)}
                                disabled={currentPage === totalPages}
                                className="pagination-btn"
                            >
                                Siguiente &raquo;
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

export default BookBuilderPage;