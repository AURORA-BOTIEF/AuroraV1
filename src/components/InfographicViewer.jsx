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

    useEffect(() => {
        loadInfographic();
    }, [folder]);

    useEffect(() => {
        const handleKeyPress = (e) => {
            if (viewMode === 'presentation') {
                if (e.key === 'ArrowRight' || e.key === ' ') {
                    nextSlide();
                } else if (e.key === 'ArrowLeft') {
                    previousSlide();
                } else if (e.key === 'Escape') {
                    navigate('/presentaciones');
                }
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, [currentSlideIndex, viewMode, infographic]);

    const loadInfographic = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/infographic/${encodeURIComponent(folder)}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setInfographic(data);
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
        <div className="viewer-container">
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

                <button
                    onClick={() => navigate(`/presentaciones/editor/${folder}`)}
                    className="btn-edit"
                >
                    ✏️ Editar
                </button>
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
                    {infographic.slides.map((slide, index) => (
                        <div
                            key={index}
                            className="grid-slide-card"
                            onClick={() => goToSlide(index)}
                        >
                            <div className="grid-slide-preview">
                                {renderSlide(slide, index)}
                            </div>
                            <div className="grid-slide-info">
                                <span className="grid-slide-number">{index + 1}</span>
                                <span className="grid-slide-title">{slide.title}</span>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default InfographicViewer;
