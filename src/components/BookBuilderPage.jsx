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
    const [limit] = useState(6);
    const [totalCount, setTotalCount] = useState(0);
    const [isSearching, setIsSearching] = useState(false);

    // Load projects when page or search changes (with debounce for search)
    useEffect(() => {
        const debounceTimer = setTimeout(() => {
            loadProjects(currentPage, searchTerm);
        }, searchTerm ? 300 : 0);

        return () => clearTimeout(debounceTimer);
    }, [currentPage, searchTerm]);

    // Reset to page 1 when search changes
    useEffect(() => {
        if (searchTerm) {
            setCurrentPage(1);
        }
    }, [searchTerm]);

    const loadProjects = async (page = 1, search = '') => {
        try {
            setLoading(true);
            if (search) setIsSearching(true);

            // Build URL with search parameter for backend filtering
            let url = `${API_BASE}/list-projects?page=${page}&limit=${limit}`;
            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }

            const response = await fetch(url, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
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
            setIsSearching(false);
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



    // Projects are now filtered server-side, just use the results directly
    const filteredProjects = projects;

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
                    placeholder="Buscar en todos los proyectos..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="search-input"
                />
                <div className="pagination-info">
                    {searchTerm ? `Resultados: ${totalCount}` : `Total: ${totalCount} proyectos`}
                </div>
            </div>

            {loading && (
                <div style={{ textAlign: 'center', marginTop: '1rem' }}>
                    <p style={{ color: '#666', marginBottom: '0.5rem' }}>
                        {isSearching ? 'Buscando...' : 'Cargando proyectos...'}
                    </p>
                    <div style={{
                        width: '100%',
                        maxWidth: '300px',
                        margin: '0 auto',
                        height: '6px',
                        background: '#e0e0e0',
                        borderRadius: '3px',
                        overflow: 'hidden'
                    }}>
                        <div style={{
                            height: '100%',
                            width: '30%',
                            background: 'linear-gradient(90deg, #007bff, #00c6ff)',
                            borderRadius: '3px',
                            animation: 'loading-progress 1.5s ease-in-out infinite'
                        }} />
                    </div>
                </div>
            )}

            {!loading && (
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
                                                📚 Acceder
                                            </button>
                                            {project.hasLabGuide && (
                                                <button
                                                    className="btn-primary"
                                                    onClick={() => openBookEditor(project, 'lab')}
                                                    style={{ marginLeft: '10px' }}
                                                >
                                                    🧪 Lab Guide
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
                        <div className="pagination-wrapper">
                            <div className="pagination-controls">
                                <button
                                    onClick={() => handlePageChange(currentPage - 1)}
                                    disabled={currentPage === 1}
                                    className="pagination-btn"
                                >
                                    ← Anterior
                                </button>

                                <div className="pagination-center">
                                    <span className="pagination-status">
                                        Página {currentPage} de {totalPages}
                                    </span>
                                </div>

                                <button
                                    onClick={() => handlePageChange(currentPage + 1)}
                                    disabled={currentPage === totalPages}
                                    className="pagination-btn"
                                >
                                    Siguiente →
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

export default BookBuilderPage;