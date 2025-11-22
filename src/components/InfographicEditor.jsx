// src/components/InfographicEditor.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import './InfographicEditor.css';

const API_BASE = 'https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2';

function InfographicEditor() {
    const { folder } = useParams();
    const navigate = useNavigate();
    const [infographic, setInfographic] = useState(null);
    const [selectedSlideIndex, setSelectedSlideIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [hasChanges, setHasChanges] = useState(false);

    useEffect(() => {
        loadInfographic();
    }, [folder]);

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
            setHasChanges(false);
        } catch (err) {
            console.error('Error loading infographic:', err);
            setError('Error al cargar la presentación.');
        } finally {
            setLoading(false);
        }
    };

    const saveChanges = async () => {
        if (!infographic || !hasChanges) return;

        setSaving(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/infographic`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    project_folder: folder,
                    structure: infographic
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('Saved successfully:', result);
            setHasChanges(false);
            alert('✅ Cambios guardados correctamente');
        } catch (err) {
            console.error('Error saving infographic:', err);
            setError('Error al guardar los cambios.');
            alert('❌ Error al guardar los cambios');
        } finally {
            setSaving(false);
        }
    };

    const updateSlideTitle = (index, newTitle) => {
        const updated = { ...infographic };
        updated.slides[index].title = newTitle;
        setInfographic(updated);
        setHasChanges(true);
    };

    const updateSlideSubtitle = (index, newSubtitle) => {
        const updated = { ...infographic };
        updated.slides[index].subtitle = newSubtitle;
        setInfographic(updated);
        setHasChanges(true);
    };

    const updateBullet = (slideIndex, blockIndex, bulletIndex, newText) => {
        const updated = { ...infographic };
        const block = updated.slides[slideIndex].content_blocks[blockIndex];
        if (block && block.type === 'bullets') {
            block.items[bulletIndex] = newText;
            setInfographic(updated);
            setHasChanges(true);
        }
    };

    const addBullet = (slideIndex, blockIndex) => {
        const updated = { ...infographic };
        const block = updated.slides[slideIndex].content_blocks[blockIndex];
        if (block && block.type === 'bullets') {
            block.items.push('Nueva viñeta');
            setInfographic(updated);
            setHasChanges(true);
        }
    };

    const removeBullet = (slideIndex, blockIndex, bulletIndex) => {
        const updated = { ...infographic };
        const block = updated.slides[slideIndex].content_blocks[blockIndex];
        if (block && block.type === 'bullets' && block.items.length > 1) {
            block.items.splice(bulletIndex, 1);
            setInfographic(updated);
            setHasChanges(true);
        }
    };

    if (loading) {
        return (
            <div className="editor-container">
                <div className="loading-spinner">
                    <div className="spinner"></div>
                    <p>Cargando editor...</p>
                </div>
            </div>
        );
    }

    if (error && !infographic) {
        return (
            <div className="editor-container">
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
            <div className="editor-container">
                <div className="error-message">
                    <h2>📭 Sin diapositivas</h2>
                    <p>Esta presentación no tiene diapositivas para editar.</p>
                    <button onClick={() => navigate('/presentaciones')}>
                        Volver a Presentaciones
                    </button>
                </div>
            </div>
        );
    }

    const selectedSlide = infographic.slides[selectedSlideIndex];

    return (
        <div className="editor-container">
            {/* Top Controls */}
            <div className="editor-header">
                <button onClick={() => navigate('/presentaciones')} className="btn-back">
                    ← Volver
                </button>

                <div className="editor-title">
                    <h2>✏️ Editor de Presentación</h2>
                    <span className="course-title">{infographic.course_title}</span>
                </div>

                <div className="editor-actions">
                    {hasChanges && <span className="unsaved-indicator">● Cambios sin guardar</span>}
                    <button
                        onClick={saveChanges}
                        disabled={!hasChanges || saving}
                        className="btn-save"
                    >
                        {saving ? '💾 Guardando...' : '💾 Guardar Cambios'}
                    </button>
                    <button
                        onClick={() => navigate(`/presentaciones/viewer/${folder}`)}
                        className="btn-preview"
                    >
                        👁️ Vista Previa
                    </button>
                </div>
            </div>

            <div className="editor-main">
                {/* Slide List Sidebar */}
                <div className="slides-sidebar">
                    <h3>Diapositivas ({infographic.slides.length})</h3>
                    <div className="slides-list">
                        {infographic.slides.map((slide, index) => (
                            <div
                                key={index}
                                className={`slide-item ${index === selectedSlideIndex ? 'active' : ''}`}
                                onClick={() => setSelectedSlideIndex(index)}
                            >
                                <span className="slide-item-number">{index + 1}</span>
                                <span className="slide-item-title">{slide.title}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Edit Panel */}
                <div className="edit-panel">
                    <div className="slide-edit-header">
                        <h3>Diapositiva {selectedSlideIndex + 1}</h3>
                    </div>

                    <div className="edit-form">
                        {/* Title */}
                        <div className="form-group">
                            <label>Título</label>
                            <input
                                type="text"
                                value={selectedSlide.title}
                                onChange={(e) => updateSlideTitle(selectedSlideIndex, e.target.value)}
                                className="input-title"
                            />
                        </div>

                        {/* Subtitle */}
                        <div className="form-group">
                            <label>Subtítulo (opcional)</label>
                            <input
                                type="text"
                                value={selectedSlide.subtitle || ''}
                                onChange={(e) => updateSlideSubtitle(selectedSlideIndex, e.target.value)}
                                className="input-subtitle"
                            />
                        </div>

                        {/* Content Blocks */}
                        <div className="form-group">
                            <label>Contenido</label>
                            {selectedSlide.content_blocks && selectedSlide.content_blocks.map((block, blockIdx) => (
                                <div key={blockIdx} className="content-block">
                                    {block.type === 'bullets' && (
                                        <div className="bullets-block">
                                            {block.heading && (
                                                <div className="block-heading">
                                                    <strong>Encabezado:</strong> {block.heading}
                                                </div>
                                            )}
                                            <div className="bullets-list">
                                                {block.items.map((bullet, bulletIdx) => (
                                                    <div key={bulletIdx} className="bullet-item">
                                                        <span className="bullet-number">{bulletIdx + 1}.</span>
                                                        <input
                                                            type="text"
                                                            value={bullet}
                                                            onChange={(e) => updateBullet(selectedSlideIndex, blockIdx, bulletIdx, e.target.value)}
                                                            className="input-bullet"
                                                        />
                                                        <button
                                                            onClick={() => removeBullet(selectedSlideIndex, blockIdx, bulletIdx)}
                                                            className="btn-remove-bullet"
                                                            disabled={block.items.length <= 1}
                                                        >
                                                            ✕
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                            <button
                                                onClick={() => addBullet(selectedSlideIndex, blockIdx)}
                                                className="btn-add-bullet"
                                            >
                                                + Agregar viñeta
                                            </button>
                                        </div>
                                    )}

                                    {block.type === 'image' && (
                                        <div className="image-block">
                                            <p><strong>Imagen:</strong> {block.image_reference}</p>
                                            {block.caption && <p><em>Caption:</em> {block.caption}</p>}
                                        </div>
                                    )}

                                    {block.type === 'callout' && (
                                        <div className="callout-block">
                                            <p><strong>Nota destacada:</strong> {block.text}</p>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Preview Panel */}
                <div className="preview-panel">
                    <h3>Vista Previa</h3>
                    <div className="slide-preview">
                        <div className="slide">
                            <div className="slide-header">
                                <div className="slide-title">{selectedSlide.title}</div>
                                {selectedSlide.subtitle && (
                                    <div className="slide-subtitle">{selectedSlide.subtitle}</div>
                                )}
                            </div>
                            <div className="slide-content">
                                {selectedSlide.content_blocks && selectedSlide.content_blocks.map((block, idx) => {
                                    if (block.type === 'bullets') {
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
                                    }
                                    if (block.type === 'callout') {
                                        return <div key={idx} className="callout">{block.text}</div>;
                                    }
                                    return null;
                                })}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default InfographicEditor;
