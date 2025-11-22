// src/components/InfographicViewer.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import './InfographicViewer.css';

const API_BASE = 'https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod';

function InfographicViewer() {
    const { folder } = useParams();
    const navigate = useNavigate();
    const [infographic, setInfographic] = useState(null);
    const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('presentation'); // 'presentation' or 'grid'
    const [isFullscreen, setIsFullscreen] = useState(false);

    useEffect(() => {
        loadInfographic();
    }, [folder]);

    useEffect(() => {
        const handleKeyPress = (e) => {
            if (e.key === 'Escape') {
                if (isFullscreen) {
                    setIsFullscreen(false);
                } else if (viewMode === 'presentation') {
                    navigate('/presentaciones');
                }
            } else if (viewMode === 'presentation' && !isFullscreen) {
                if (e.key === 'ArrowRight' || e.key === ' ') {
                    nextSlide();
                } else if (e.key === 'ArrowLeft') {
                    previousSlide();
                }
            } else if (viewMode === 'presentation' && isFullscreen) {
                if (e.key === 'ArrowRight' || e.key === ' ') {
                    nextSlide();
                } else if (e.key === 'ArrowLeft') {
                    previousSlide();
                }
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, [currentSlideIndex, viewMode, infographic, isFullscreen]);

    const loadInfographic = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/infographic/${encodeURIComponent(folder)}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            // Filter out hidden slides for presentation view
            const visibleSlides = data.slides.filter(slide => !slide.hidden);
            setInfographic({
                ...data,
                allSlides: data.slides, // Keep all slides for grid view
                slides: visibleSlides  // Only visible slides for presentation
            });
        } catch (err) {
            console.error('Error loading infographic:', err);
            setError('Error al cargar la presentación. Por favor, intenta de nuevo.');
        } finally {
            setLoading(false);
        }
    };

    const nextSlide = () => {
        if (infographic && currentSlideIndex < infographic.slides.length - 1) {
            setCurrentSlideIndex(currentSlideIndex + 1);
        }
    };

    const previousSlide = () => {
        if (currentSlideIndex > 0) {
            setCurrentSlideIndex(currentSlideIndex - 1);
        }
    };

    const goToSlide = (index) => {
        setCurrentSlideIndex(index);
        setViewMode('presentation');
    };

    const toggleFullscreen = () => {
        setIsFullscreen(!isFullscreen);
    };

    const downloadAsPDF = () => {
        // Open print dialog which allows saving as PDF
        window.print();
    };

    const renderSlide = (slide, index) => {
        const isCurrentSlide = index === currentSlideIndex;
        const hasSubtitle = slide.subtitle && slide.subtitle.trim() !== '';

        return (
            <div
                key={index}
                className={`slide ${isCurrentSlide ? 'active' : ''}`}
                data-slide={index + 1}
            >
                {/* Slide Header */}
                <div className="slide-header">
                    <div className="slide-title">{slide.title}</div>
                    {hasSubtitle && <div className="slide-subtitle">{slide.subtitle}</div>}
                </div>

                {/* Slide Content */}
                <div className={`slide-content ${hasSubtitle ? 'with-subtitle' : ''}`}>
                    {renderContentBlocks(slide.content_blocks || [])}
                </div>

                {/* Slide Number */}
                <div className="slide-number">
                    {index + 1} / {infographic.slides.length}
                </div>
            </div>
        );
    };

    const renderContentBlocks = (blocks) => {
        return blocks.map((block, idx) => {
            switch (block.type) {
                case 'bullets':
                    return (
                        <div key={idx}>
                            {block.heading && <div className="content-heading">{block.heading}</div>}
                            <ul className="bullets">
                                {block.items.map((item, itemIdx) => (
                                    <li key={itemIdx}>{item}</li>
                                ))}
                            </ul>
                        </div>
                    );

                case 'image':
                    const imageUrl = infographic.image_url_mapping?.[block.image_reference] || '';
                    return (
                        <div key={idx}>
                            {imageUrl ? (
                                <img src={imageUrl} className="slide-image" alt={block.image_reference} />
                            ) : (
                                <div className="image-placeholder">
                                    Imagen: {block.image_reference}
                                </div>
                            )}
                            {block.caption && <div className="image-caption">{block.caption}</div>}
                        </div>
                    );

                case 'callout':
                    return (
                        <div key={idx} className="callout">
                            {block.text}
                        </div>
                    );

                default:
                    return null;
            }
        });
    };

    if (loading) {
        return (
            <div className="viewer-container">
                <div className="loading-spinner">
                    <div className="spinner"></div>
                    <p>Cargando presentación...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="viewer-container">
                <div className="error-message">
                    <h2>⚠️ Error</h2>
                    <p>{error}</p>
                    <button onClick={() => navigate('/presentaciones')}>
                        Volver a Presentaciones
                    </button>
                </div>
            </div>
        );
    }

    if (!infographic || !infographic.slides || infographic.slides.length === 0) {
        return (
            <div className="viewer-container">
                <div className="error-message">
                    <h2>📭 Sin diapositivas</h2>
                    <p>Esta presentación no tiene diapositivas.</p>
                    <button onClick={() => navigate('/presentaciones')}>
                        Volver a Presentaciones
                    </button>
                </div>
            </div>
        );
    }

    const currentSlide = infographic.slides[currentSlideIndex];

    return (
        <div className={`viewer-container ${isFullscreen ? 'fullscreen-mode' : ''}`}>
            {/* Top Controls */}
            <div className="viewer-controls">
                <button onClick={() => navigate('/presentaciones')} className="btn-back">
                    ← Volver
                </button>

                <div className="view-mode-toggle">
                    <button
                        className={viewMode === 'presentation' ? 'active' : ''}
                        onClick={() => setViewMode('presentation')}
                    >
                        🖼️ Presentación
                    </button>
                    <button
                        className={viewMode === 'grid' ? 'active' : ''}
                        onClick={() => setViewMode('grid')}
                    >
                        ⊞ Cuadrícula
                    </button>
                </div>

                <div className="viewer-title">
                    <h2>{infographic.course_title || 'Presentación'}</h2>
                    <span className="slide-counter">
                        {currentSlideIndex + 1} / {infographic.slides.length}
                    </span>
                </div>

                <div className="viewer-actions">
                    <button
                        onClick={downloadAsPDF}
                        className="btn-download"
                        title="Descargar como PDF"
                    >
                        📄 PDF
                    </button>

                    <button
                        onClick={toggleFullscreen}
                        className="btn-fullscreen"
                        title={isFullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'}
                    >
                        {isFullscreen ? '⊗' : '⛶'} {isFullscreen ? 'Salir' : 'Pantalla completa'}
                    </button>

                    <button
                        onClick={() => navigate(`/presentaciones/editor/${folder}`)}
                        className="btn-edit"
                    >
                        ✏️ Editar
                    </button>
                </div>
            </div>

            {/* Main Content */}
            {viewMode === 'presentation' ? (
                <div className="presentation-view">
                    <div className="slide-viewport">
                        {renderSlide(currentSlide, currentSlideIndex)}
                    </div>

                    {/* Navigation Controls */}
                    <div className="slide-navigation">
                        <button
                            onClick={previousSlide}
                            disabled={currentSlideIndex === 0}
                            className="nav-btn"
                        >
                            ← Anterior
                        </button>

                        <div className="progress-bar">
                            <div
                                className="progress-fill"
                                style={{
                                    width: `${((currentSlideIndex + 1) / infographic.slides.length) * 100}%`
                                }}
                            ></div>
                        </div>

                        <button
                            onClick={nextSlide}
                            disabled={currentSlideIndex === infographic.slides.length - 1}
                            className="nav-btn"
                        >
                            Siguiente →
                        </button>
                    </div>

                    <div className="keyboard-hint">
                        💡 Usa las teclas ← → o espacio para navegar
                    </div>
                </div>
            ) : (
                <div className="grid-view">
                    {(infographic.allSlides || infographic.slides).map((slide, index) => (
                        <div
                            key={index}
                            className={`grid-slide-card ${slide.hidden ? 'hidden-slide-card' : ''}`}
                            onClick={() => !slide.hidden && goToSlide(index)}
                            style={{ cursor: slide.hidden ? 'not-allowed' : 'pointer' }}
                        >
                            <div className="grid-slide-preview">
                                {renderSlide(slide, index)}
                            </div>
                            <div className="grid-slide-info">
                                <span className="grid-slide-number">{index + 1}</span>
                                <span className="grid-slide-title">{slide.title}</span>
                                {slide.hidden && <span className="hidden-indicator">🚫 Oculta</span>}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default InfographicViewer;
