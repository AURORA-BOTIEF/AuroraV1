// src/components/InfographicEditor.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getBlobUrlForS3Object } from '../utils/s3ImageLoader';
import './InfographicEditor.css';

const API_BASE = 'https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod';

function InfographicEditor() {
    const { folder } = useParams();
    const navigate = useNavigate();
    const [infographic, setInfographic] = useState(null);
    const [selectedSlideIndex, setSelectedSlideIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [hasChanges, setHasChanges] = useState(false);

    const iframeRef = React.useRef(null);

    useEffect(() => {
        loadInfographic();
    }, [folder]);

    // Fetch and update images when infographic loads
    useEffect(() => {
        if (infographic && infographic.html_content) {
            fetchImages(infographic.html_content);
        }
    }, [infographic]);

    const fetchImages = async (htmlContent) => {
        // Find all S3 URLs to fetch in background
        const s3UrlPattern = /https?:\/\/[^\/\s"']+\.s3[^\/\s"']*?\.amazonaws\.com\/[^"'\s)]+/gi;
        const matches = htmlContent.match(s3UrlPattern) || [];
        const s3Urls = [...new Set(matches)];

        if (s3Urls.length === 0) return;

        console.log(`Found ${s3Urls.length} unique S3 URLs - starting background fetch`);

        for (const s3Url of s3Urls) {
            try {
                // Fetch blob URL
                const blobUrl = await getBlobUrlForS3Object(s3Url);

                // Send to iframe to update image
                if (iframeRef.current && iframeRef.current.contentWindow) {
                    iframeRef.current.contentWindow.postMessage({
                        type: 'UPDATE_IMAGE_SRC',
                        originalSrc: s3Url,
                        newSrc: blobUrl
                    }, '*');
                }
            } catch (error) {
                console.error(`Failed to load background image: ${s3Url}`, error);
            }
        }
    };

    // Update iframe content when selected slide changes
    useEffect(() => {
        const iframe = iframeRef.current;
        if (iframe && iframe.contentDocument && infographic) {
            const doc = iframe.contentDocument;

            // Inject script for handling image updates if not present
            if (!doc.getElementById('image-updater-script')) {
                const script = doc.createElement('script');
                script.id = 'image-updater-script';
                script.textContent = `
                    window.addEventListener('message', (event) => {
                        if (event.data.type === 'UPDATE_IMAGE_SRC') {
                            const { originalSrc, newSrc } = event.data;
                            
                            // Update img tags
                            const images = document.querySelectorAll('img');
                            images.forEach(img => {
                                // Check both attribute and resolved URL, handling potential encoding differences
                                const currentSrc = img.getAttribute('src');
                                const resolvedSrc = img.src;
                                
                                if (currentSrc === originalSrc || 
                                    resolvedSrc === originalSrc || 
                                    resolvedSrc === originalSrc.replace(/ /g, '%20') ||
                                    decodeURIComponent(resolvedSrc) === originalSrc) {
                                    img.src = newSrc;
                                }
                            });

                            // Update background images
                            const allElements = document.querySelectorAll('*');
                            allElements.forEach(el => {
                                const style = window.getComputedStyle(el);
                                const bgImage = style.backgroundImage;
                                if (bgImage && bgImage !== 'none' && bgImage.includes(originalSrc)) {
                                    el.style.backgroundImage = 'url(' + newSrc + ')';
                                }
                            });
                        }
                    });
                `;
                doc.head.appendChild(script);
            }

            // Remove existing injected style if any
            const existingStyle = doc.getElementById('preview-style');
            if (existingStyle) {
                existingStyle.remove();
            }

            // Inject new style to show selected slide
            const style = doc.createElement('style');
            style.id = 'preview-style';
            style.textContent = `
                body { 
                    overflow: auto !important; 
                    background-color: transparent !important;
                    scrollbar-width: thin;
                }
                .slide { 
                    display: none !important; 
                    position: absolute !important; 
                    top: 0; left: 0; 
                    transform-origin: top left;
                }
                .slide[data-slide="${selectedSlideIndex + 1}"] { 
                    display: block !important; 
                }
                /* Hide scrollbars for cleaner look but allow scroll */
                ::-webkit-scrollbar {
                    width: 8px;
                }
                ::-webkit-scrollbar-track {
                    background: transparent;
                }
                ::-webkit-scrollbar-thumb {
                    background: #ccc;
                    border-radius: 4px;
                }
            `;
            doc.head.appendChild(style);
        }
    }, [selectedSlideIndex, infographic]);

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
                const errorData = await response.json().catch(() => ({}));
                console.error('Server error details:', errorData);
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('Saved successfully:', result);
            setHasChanges(false);
            alert('✅ Cambios guardados correctamente');
        } catch (err) {
            console.error('Error saving infographic:', err);
            setError(`Error al guardar: ${err.message}`);
            alert(`❌ Error al guardar: ${err.message}`);
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

    const toggleSlideVisibility = (index) => {
        const updated = { ...infographic };
        updated.slides[index].hidden = !updated.slides[index].hidden;
        setInfographic(updated);
        setHasChanges(true);
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
            {/* ... header ... */}
            <div className="editor-header">
                {/* ... existing header code ... */}
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
                {/* ... sidebar and edit panel ... */}
                <div className="slides-sidebar">
                    {/* ... sidebar content ... */}
                    <h3>Diapositivas ({infographic.slides.length})</h3>
                    <div className="slides-list">
                        {infographic.slides.map((slide, index) => (
                            <div
                                key={index}
                                className={`slide-item ${index === selectedSlideIndex ? 'active' : ''} ${slide.hidden ? 'hidden-slide' : ''}`}
                            >
                                <div
                                    className="slide-item-content"
                                    onClick={() => setSelectedSlideIndex(index)}
                                >
                                    <span className="slide-item-number">{index + 1}</span>
                                    <span className="slide-item-title">{slide.title}</span>
                                </div>
                                <button
                                    className="btn-toggle-visibility"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        toggleSlideVisibility(index);
                                    }}
                                    title={slide.hidden ? 'Mostrar en presentación' : 'Ocultar en presentación'}
                                >
                                    {slide.hidden ? '👁️‍🗨️' : '👁️'}
                                </button>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="editor-content-scrollable">
                    {/* Preview Panel */}
                    <div className="preview-panel">
                        <h3>Vista Previa (Fidelidad Real)</h3>
                        <div className="slide-preview-container" style={{
                            width: '100%',
                            minHeight: '480px', // Fixed height for preview
                            position: 'relative',
                            background: '#e0e0e0',
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            padding: '20px'
                        }}>
                            {infographic && infographic.html_content ? (
                                <div style={{
                                    width: '100%',
                                    height: '432px',
                                    position: 'relative',
                                    background: 'transparent',
                                    flexShrink: 0,
                                    display: 'flex',
                                    justifyContent: 'center',
                                    alignItems: 'center',
                                    overflow: 'visible'
                                }}>
                                    <div style={{
                                        width: '1280px',
                                        height: '720px',
                                        transform: 'scale(0.6)',
                                        transformOrigin: 'center center',
                                        flexShrink: 0,
                                        boxShadow: '0 4px 15px rgba(0,0,0,0.2)',
                                        background: 'white'
                                    }}>
                                        <iframe
                                            ref={iframeRef}
                                            title="Slide Preview"
                                            srcDoc={infographic.html_content}
                                            style={{
                                                width: '100%',
                                                height: '100%',
                                                border: 'none',
                                                pointerEvents: 'none'
                                            }}
                                        />
                                    </div>
                                </div>
                            ) : (
                                <div className="loading-preview">Cargando vista previa...</div>
                            )}
                        </div>
                    </div>

                    <div className="edit-panel">
                        {/* ... edit panel content ... */}
                        <div className="slide-edit-header">
                            <h3>Diapositiva {selectedSlideIndex + 1}</h3>
                            <div className="slide-badges">
                                <span className="layout-badge">📐 {selectedSlide.layout || selectedSlide.layout_hint || 'single-column'}</span>
                                {selectedSlide.hidden && (
                                    <span className="hidden-badge">🚫 Oculta en presentación</span>
                                )}
                            </div>
                        </div>

                        <div className="edit-form">
                            {/* ... form content ... */}
                            <div className="form-group">
                                <label>Título</label>
                                <input
                                    type="text"
                                    value={selectedSlide.title}
                                    onChange={(e) => updateSlideTitle(selectedSlideIndex, e.target.value)}
                                    className="input-title"
                                />
                            </div>

                            <div className="form-group">
                                <label>Subtítulo (opcional)</label>
                                <input
                                    type="text"
                                    value={selectedSlide.subtitle || ''}
                                    onChange={(e) => updateSlideSubtitle(selectedSlideIndex, e.target.value)}
                                    className="input-subtitle"
                                />
                            </div>

                            <div className="form-group">
                                <label>Contenido</label>
                                {selectedSlide.content_blocks && selectedSlide.content_blocks.map((block, blockIdx) => (
                                    <div key={blockIdx} className="content-block">
                                        {(block.type === 'bullets' || block.type === 'nested-bullets') && (
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
                                                <p><strong>Referencia:</strong> {block.image_reference}</p>
                                                {infographic.image_url_mapping && infographic.image_url_mapping[block.image_reference] ? (
                                                    <div className="image-preview-container">
                                                        <img
                                                            src={infographic.image_url_mapping[block.image_reference]}
                                                            alt={block.image_reference}
                                                            className="editor-image-preview"
                                                            style={{ maxWidth: '100%', maxHeight: '200px', objectFit: 'contain', marginTop: '10px', borderRadius: '4px', border: '1px solid #ddd' }}
                                                        />
                                                    </div>
                                                ) : (
                                                    <p className="image-missing-warning">⚠️ Imagen no encontrada en el mapeo</p>
                                                )}
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
                </div>
            </div>

        </div>
    );
}

export default InfographicEditor;
