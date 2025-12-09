// src/components/PresentacionesPage.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './PresentacionesPage.css';

const API_BASE = 'https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod';

function PresentacionesPage() {
    const navigate = useNavigate();
    const [infographics, setInfographics] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [searchTerm, setSearchTerm] = useState('');

    useEffect(() => {
        loadInfographics();
    }, [page]);

    const loadInfographics = async (forceRefresh = false) => {
        setLoading(true);
        setError(null);

        try {
            let url = `${API_BASE}/list-infographics?page=${page}&limit=12`;

            if (forceRefresh) {
                url += `&_t=${new Date().getTime()}`;
            }

            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setInfographics(data.infographics || []);
            setTotalPages(data.total_pages || 1);

            if (forceRefresh) {
                console.log('Cache cleared and list refreshed');
            }
        } catch (err) {
            console.error('Error loading infographics:', err);
            setError('Error al cargar las presentaciones. Por favor, intenta de nuevo.');
        } finally {
            setLoading(false);
        }
    };

    const handleView = (folder) => {
        navigate(`/presentaciones/viewer/${encodeURIComponent(folder)}`);
    };

    const handleEdit = (folder) => {
        navigate(`/presentaciones/editor/${encodeURIComponent(folder)}`);
    };

    const formatDate = (dateString) => {
        if (!dateString) return 'Fecha desconocida';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('es-MX', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        } catch {
            return dateString;
        }
    };

    const filteredInfographics = infographics.filter(infographic =>
        infographic.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        infographic.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        infographic.course_topic.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (loading && infographics.length === 0) {
        return (
            <div className="presentaciones-loading-overlay">
                <div className="presentaciones-loading-container">
                    <h1>📊 Presentaciones</h1>
                    <p>Cargando presentaciones...</p>
                    <div className="loading-bar-wrapper">
                        <div className="loading-bar"></div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="presentaciones-container">
            <div className="presentaciones-header">
                <h1>📊 Presentaciones de Cursos</h1>
                <p>Visualiza y edita las presentaciones generadas para tus cursos</p>
            </div>

            {error && (
                <div className="error-message">
                    <span>⚠️ {error}</span>
                    <button onClick={loadInfographics}>Reintentar</button>
                </div>
            )}

            <div className="presentaciones-controls">
                <input
                    type="text"
                    className="search-input"
                    placeholder="🔍 Buscar por título, descripción o tema..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
                <button onClick={() => loadInfographics(false)} className="presentaciones-refresh-btn">
                    🔄 Actualizar
                </button>

            </div>

            {filteredInfographics.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">📭</div>
                    <h2>No hay presentaciones disponibles</h2>
                    <p>
                        {searchTerm
                            ? 'No se encontraron presentaciones que coincidan con tu búsqueda.'
                            : 'Aún no se han generado presentaciones. Genera un curso primero para crear presentaciones.'}
                    </p>
                </div>
            ) : (
                <>
                    <div className="infographics-grid">
                        {filteredInfographics.map((infographic) => (
                            <div key={infographic.folder} className="infographic-card">
                                <div className="card-header">
                                    <h3>{infographic.title}</h3>
                                    <span className="slide-count">
                                        {infographic.total_slides || 0} diapositivas
                                    </span>
                                </div>

                                <div className="card-body">
                                    <p className="description">{infographic.description || 'Sin descripción'}</p>
                                    <div className="card-metadata">
                                        <span className="metadata-item">
                                            📅 {formatDate(infographic.created)}
                                        </span>
                                        <span className="metadata-item">
                                            🏷️ {infographic.course_topic || 'Sin tema'}
                                        </span>
                                    </div>
                                </div>

                                <div className="card-actions">
                                    <button
                                        className="btn-view"
                                        onClick={() => handleView(infographic.folder)}
                                    >
                                        👁️ Ver
                                    </button>
                                    <button
                                        className="btn-edit"
                                        onClick={() => handleEdit(infographic.folder)}
                                    >
                                        ✏️ Editar
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>

                    {totalPages > 1 && (
                        <div className="pagination">
                            <button
                                onClick={() => setPage(Math.max(1, page - 1))}
                                disabled={page === 1}
                                className="pagination-btn"
                            >
                                ← Anterior
                            </button>
                            <span className="pagination-info">
                                Página {page} de {totalPages}
                            </span>
                            <button
                                onClick={() => setPage(Math.min(totalPages, page + 1))}
                                disabled={page === totalPages}
                                className="pagination-btn"
                            >
                                Siguiente →
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

export default PresentacionesPage;
