// src/components/InfographicViewer.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getBlobUrlForS3Object } from '../utils/s3ImageLoader';
import './InfographicViewer.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL || "https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod";

function InfographicViewer() {
    const { folder } = useParams();
    const navigate = useNavigate();
    const [infographic, setInfographic] = useState(null);
    const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('presentation'); // 'presentation' or 'grid'
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [fullscreenScale, setFullscreenScale] = useState(1);
    const [zoomedImage, setZoomedImage] = useState(null); // For image zoom feature

    const [htmlContent, setHtmlContent] = useState(null);
    const iframeRef = React.useRef(null);

    useEffect(() => {
        loadInfographic();
    }, [folder]);

    // Fetch and prepare HTML content when available
    useEffect(() => {
        console.log('=== INFOGRAPHIC DATA RECEIVED ===');
        console.log('Infographic object:', infographic);

        if (infographic) {
            console.log('Available keys:', Object.keys(infographic));
            console.log('Has html_content?', 'html_content' in infographic);
            console.log('Has html_url?', 'html_url' in infographic);
            console.log('Has image_url_mapping?', 'image_url_mapping' in infographic);

            if (infographic.image_url_mapping) {
                console.log('Image URL mapping entries:', Object.keys(infographic.image_url_mapping).length);
                console.log('Image URLs:', Object.values(infographic.image_url_mapping));
            }

            if (infographic.html_content) {
                console.log('HTML content length:', infographic.html_content.length);
                fetchHtmlContent(infographic.html_content);
            } else if (infographic.html_url) {
                console.warn('⚠️ Received html_url instead of html_content! URL:', infographic.html_url);
            } else {
                console.error('✗ No HTML content or URL found in response!');
            }
        }
    }, [infographic]);

    // Update iframe when current slide changes
    useEffect(() => {
        if (iframeRef.current && iframeRef.current.contentWindow && infographic) {
            // Map the current visible index to the original index in the full list
            // This is crucial because the iframe contains ALL slides (including hidden ones)
            // but our state (currentSlideIndex) tracks only VISIBLE slides.
            const currentSlide = infographic.slides[currentSlideIndex];
            const originalIndex = infographic.allSlides.indexOf(currentSlide);

            if (originalIndex !== -1) {
                iframeRef.current.contentWindow.postMessage({
                    type: 'NAVIGATE_SLIDE',
                    index: originalIndex
                }, '*');
            }
        }
    }, [currentSlideIndex, infographic]);

    const fetchHtmlContent = async (htmlContent) => {
        try {
            console.log('=== PROCESSING HTML CONTENT ===');
            console.log('HTML content length:', htmlContent?.length);

            // Render HTML immediately with original URLs
            // We will fetch images in background and update them via postMessage
            let text = htmlContent;

            // Find all S3 URLs to fetch in background
            const s3UrlPattern = /https?:\/\/[^\/\s"']+\.s3[^\/\s"']*?\.amazonaws\.com\/[^"'\s)]+/gi;
            const matches = text.match(s3UrlPattern) || [];
            const s3Urls = [...new Set(matches)];

            console.log(`Found ${s3Urls.length} unique S3 URLs - starting background fetch`);

            // Start background fetch process
            (async () => {
                let successCount = 0;
                let failCount = 0;

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

                        successCount++;
                    } catch (error) {
                        failCount++;
                        console.error(`Failed to load background image: ${s3Url}`, error);
                    }
                }
                console.log(`Background image loading complete: ${successCount} success, ${failCount} failed`);
            })();

            // Inject styles and scripts for single-slide pagination and grid view
            const styleInjection = `
                <style>
                    /* === BASE STYLES === */
                    body {
                        margin: 0 !important;
                        padding: 0 !important;
                        overflow: hidden !important;
                        width: 100vw !important;
                        height: 100vh !important;
                        background-color: white;
                        transition: background-color 0.3s;
                    }

                    /* Hide everything that is not a slide (in presentation mode) */
                    body:not(.grid-mode) > *:not(.slide):not(script):not(style) {
                        display: none !important;
                    }

                    /* === PRESENTATION MODE (Default - No Wrappers) === */
                    .slide {
                        display: none !important;
                        position: absolute !important;
                        top: 0 !important;
                        left: 0 !important;
                        width: 100% !important;
                        height: 100% !important;
                        margin: 0 !important;
                        padding: 0 !important;
                        overflow: hidden !important;
                        z-index: 0 !important;
                    }
                    
                    .slide.active {
                        display: block !important;
                        z-index: 10 !important;
                    }

                    /* === GRID MODE STYLES (With Wrappers) === */
                    body.grid-mode {
                        display: grid !important;
                        grid-template-columns: repeat(auto-fill, 320px) !important;
                        gap: 30px !important;
                        padding: 40px !important;
                        overflow-y: auto !important;
                        height: 100vh !important;
                        background-color: #1a1a1a !important;
                        justify-content: center !important;
                        align-content: start !important;
                    }
                    
                    /* In grid mode, hide direct non-wrapper children */
                    body.grid-mode > *:not(.slide-wrapper):not(script):not(style) {
                        display: none !important;
                    }

                    body.grid-mode .slide-wrapper {
                        display: block !important;
                        position: relative !important;
                        width: 320px !important;
                        height: 180px !important;
                        overflow: hidden !important;
                        border-radius: 8px !important;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
                        cursor: pointer !important;
                        background-color: white !important;
                        transition: transform 0.2s, box-shadow 0.2s !important;
                    }

                    body.grid-mode .slide-wrapper:hover {
                        transform: scale(1.05) !important;
                        box-shadow: 0 10px 25px rgba(0,0,0,0.5) !important;
                        z-index: 20 !important;
                        outline: 3px solid #4682B4 !important;
                    }

                    /* The Slide inside the Wrapper in Grid Mode */
                    body.grid-mode .slide {
                        display: block !important; /* Always visible inside wrapper */
                        position: absolute !important;
                        top: 0 !important;
                        left: 0 !important;
                        
                        /* Force Full HD Resolution */
                        width: 1280px !important;
                        height: 720px !important;
                        
                        /* Scale to 320x180 */
                        transform: scale(0.25) !important; 
                        transform-origin: top left !important;
                        
                        margin: 0 !important;
                        padding: 0 !important;
                        box-sizing: border-box !important;
                        z-index: 0 !important;
                    }
                </style>
                <script>
                    (function() {
                        let currentSlide = 0;
                        let viewMode = 'presentation';
                        
                        // Wrap slides for grid layout
                        function wrapSlides() {
                            const slides = document.querySelectorAll('.slide');
                            slides.forEach(slide => {
                                    const wrapper = document.createElement('div');
                                    wrapper.className = 'slide-wrapper';
                                    slide.parentNode.insertBefore(wrapper, slide);
                                    wrapper.appendChild(slide);
                                    
                                    // Forward click from wrapper to parent logic
                                    wrapper.onclick = (e) => {
                                        e.stopPropagation();
                                        // Find index
                                        const allWrappers = Array.from(document.querySelectorAll('.slide-wrapper'));
                                        const index = allWrappers.indexOf(wrapper);
                                        window.parent.postMessage({
                                            type: 'SLIDE_CLICKED',
                                            index: index
                                        }, '*');
                                    };
                            });
                        }

                        // Unwrap slides for presentation layout (restore original DOM)
                        function unwrapSlides() {
                            const wrappers = document.querySelectorAll('.slide-wrapper');
                            wrappers.forEach(wrapper => {
                                const slide = wrapper.querySelector('.slide');
                                if (slide) {
                                    wrapper.parentNode.insertBefore(slide, wrapper);
                                }
                                wrapper.remove();
                            });
                        }

                        function showSlide(index) {
                            // In presentation mode, we work with .slide directly
                            const slides = document.querySelectorAll('.slide');
                            slides.forEach((slide, i) => {
                                if (i === index) {
                                    slide.classList.add('active');
                                } else {
                                    slide.classList.remove('active');
                                }
                            });
                        }
                        
                        // Listen for messages from parent
                        window.addEventListener('message', (event) => {
                            if (event.data.type === 'NAVIGATE_SLIDE') {
                                currentSlide = event.data.index;
                                if (viewMode === 'presentation') {
                                    showSlide(currentSlide);
                                }
                            } else if (event.data.type === 'UPDATE_IMAGE_SRC') {
                                const images = document.querySelectorAll('img[src="' + event.data.originalSrc + '"]');
                                images.forEach(img => {
                                    img.src = event.data.newSrc;
                                });
                            } else if (event.data.type === 'SET_VIEW_MODE') {
                                viewMode = event.data.mode;
                                if (viewMode === 'grid') {
                                    wrapSlides();
                                    document.body.classList.add('grid-mode');
                                } else {
                                    document.body.classList.remove('grid-mode');
                                    unwrapSlides();
                                    showSlide(currentSlide);
                                }
                            }
                        });
                        
                        function initSlides() {
                            // Start in presentation mode (unwrapped)
                            showSlide(0);
                        }
                        
                        setTimeout(initSlides, 0);
                        if (document.readyState === 'loading') {
                            document.addEventListener('DOMContentLoaded', initSlides);
                        } else {
                            initSlides();
                        }
                        window.addEventListener('load', initSlides);
                    })();

                    // Image click handler for zoom (only in presentation mode)
                    document.addEventListener('DOMContentLoaded', () => {
                        const images = document.querySelectorAll('img');
                        images.forEach(img => {
                            img.style.cursor = 'zoom-in';
                            img.onclick = (e) => {
                                // Only allow zoom in presentation mode
                                if (document.body.classList.contains('grid-mode')) return;
                                
                                e.stopPropagation();
                                window.parent.postMessage({
                                    type: 'IMAGE_CLICK',
                                    src: img.src
                                }, '*');
                            };
                        });
                    });

                    // Forward keydown events
                    document.addEventListener('keydown', (e) => {
                        if (['ArrowRight', 'ArrowLeft', ' ', 'PageUp', 'PageDown', 'Escape'].includes(e.key)) {
                            window.parent.postMessage({
                                type: 'KEYDOWN',
                                key: e.key
                            }, '*');
                        }
                    });
                </script>
            </head>
    `;

            let modifiedHtml = text.replace(/<\/head>/i, styleInjection);

            // Fallback if no head tag found
            if (modifiedHtml === text) {
                modifiedHtml = styleInjection + text;
            }


            setHtmlContent(modifiedHtml);
        } catch (err) {
            console.error('Error fetching HTML content:', err);
        }
    };

    useEffect(() => {
        const handleFullscreenChange = () => {
            const isNowFullscreen = !!document.fullscreenElement;
            setIsFullscreen(isNowFullscreen);

            if (isNowFullscreen) {
                // Small delay to ensure DOM is updated
                setTimeout(() => {
                    updateFullscreenScale();
                }, 100);
            }
        };

        const updateFullscreenScale = () => {
            const scaleX = window.innerWidth / 1280;
            const scaleY = window.innerHeight / 720;
            const scale = Math.min(scaleX, scaleY); // 100% fill
            setFullscreenScale(scale);
            console.log('Fullscreen scale applied:', scale, 'Screen:', window.innerWidth, 'x', window.innerHeight);
        };

        document.addEventListener('fullscreenchange', handleFullscreenChange);
        document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
        document.addEventListener('msfullscreenchange', handleFullscreenChange);
        window.addEventListener('resize', updateFullscreenScale);

        return () => {
            document.removeEventListener('fullscreenchange', handleFullscreenChange);
            document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
            document.removeEventListener('msfullscreenchange', handleFullscreenChange);
            window.removeEventListener('resize', updateFullscreenScale);
        };
    }, []);

    // Handle keyboard navigation
    useEffect(() => {
        const handleKeyPress = (e) => {
            // If image is zoomed, ESC closes it
            if (zoomedImage) {
                if (e.key === 'Escape') {
                    setZoomedImage(null);
                }
                return; // Don't navigate slides while zoomed
            }

            // If fullscreen, ESC exits (handled by browser usually, but good to have)
            if (isFullscreen && e.key === 'Escape') {
                setIsFullscreen(false);
                return;
            }

            // Slide navigation
            if (viewMode === 'presentation') {
                if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
                    nextSlide();
                } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
                    previousSlide();
                }
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, [currentSlideIndex, viewMode, infographic, isFullscreen, zoomedImage]);

    // Handle messages from iframe (image clicks and keyboard navigation)
    useEffect(() => {
        const handleMessage = (event) => {
            if (event.data.type === 'IMAGE_CLICK') {
                setZoomedImage(event.data.src);
            } else if (event.data.type === 'KEYDOWN') {
                const key = event.data.key;

                // Handle ESC key from iframe
                if (key === 'Escape') {
                    if (zoomedImage) {
                        setZoomedImage(null);
                    } else if (isFullscreen) {
                        setIsFullscreen(false);
                    }
                    return;
                }

                // Handle navigation keys from iframe
                if (!zoomedImage && viewMode === 'presentation') {
                    if (key === 'ArrowRight' || key === ' ' || key === 'PageDown') {
                        nextSlide();
                    } else if (key === 'ArrowLeft' || key === 'PageUp') {
                        previousSlide();
                    }
                }
            } else if (event.data.type === 'SLIDE_CLICKED') {
                // The iframe sends the ORIGINAL index (including hidden slides)
                // We need to map this back to our VISIBLE index
                if (infographic && infographic.allSlides) {
                    const originalIndex = event.data.index;
                    const targetSlide = infographic.allSlides[originalIndex];

                    if (targetSlide && !targetSlide.hidden) {
                        const visibleIndex = infographic.slides.indexOf(targetSlide);
                        if (visibleIndex !== -1) {
                            goToSlide(visibleIndex);
                        }
                    }
                }
            }
        };

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [zoomedImage, isFullscreen, viewMode, currentSlideIndex, infographic]);

    // Handle view mode changes
    useEffect(() => {
        if (iframeRef.current && iframeRef.current.contentWindow) {
            iframeRef.current.contentWindow.postMessage({
                type: 'SET_VIEW_MODE',
                mode: viewMode
            }, '*');
        }
    }, [viewMode]);

    const loadInfographic = async (forceRefresh = false) => {
        setLoading(true);
        setError(null);

        try {
            let url = `${API_BASE}/infographic/${encodeURIComponent(folder)}`;

            if (forceRefresh) {
                url += `?_t=${new Date().getTime()}`;
            }

            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status} `);
            }

            const data = await response.json();

            // Add timestamp to html_url if forcing refresh
            if (forceRefresh && data.html_url) {
                const separator = data.html_url.includes('?') ? '&' : '?';
                data.html_url = `${data.html_url}${separator} _t = ${new Date().getTime()} `;
            }

            // Filter out hidden slides for presentation view
            const visibleSlides = data.slides.filter(slide => !slide.hidden);
            setInfographic({
                ...data,
                allSlides: data.slides, // Keep all slides for grid view
                slides: visibleSlides  // Only visible slides for presentation
            });

            if (forceRefresh) {
                console.log('Infographic reloaded with fresh data');
                // Show a temporary success message
                const toast = document.createElement('div');
                toast.textContent = '✅ Presentación recargada';
                toast.style.position = 'fixed';
                toast.style.bottom = '20px';
                toast.style.left = '50%';
                toast.style.transform = 'translateX(-50%)';
                toast.style.backgroundColor = '#4CAF50';
                toast.style.color = 'white';
                toast.style.padding = '10px 20px';
                toast.style.borderRadius = '5px';
                toast.style.zIndex = '10000';
                toast.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
                document.body.appendChild(toast);
                setTimeout(() => document.body.removeChild(toast), 3000);
            }
        } catch (err) {
            console.error('Error loading infographic:', err);
            setError('Error al cargar la presentación. Por favor, intenta de nuevo.');
        } finally {
            setLoading(false);
        }
    };

    const nextSlide = () => {
        if (infographic && currentSlideIndex < infographic.slides.length - 1) {
            // Find next visible slide
            let nextIndex = currentSlideIndex + 1;
            while (nextIndex < infographic.slides.length && infographic.slides[nextIndex].hidden) {
                nextIndex++;
            }

            if (nextIndex < infographic.slides.length) {
                setCurrentSlideIndex(nextIndex);
            }
        }
    };

    const previousSlide = () => {
        if (currentSlideIndex > 0) {
            // Find previous visible slide
            let prevIndex = currentSlideIndex - 1;
            while (prevIndex >= 0 && infographic.slides[prevIndex].hidden) {
                prevIndex--;
            }

            if (prevIndex >= 0) {
                setCurrentSlideIndex(prevIndex);
            }
        }
    };

    const goToSlide = (index) => {
        setCurrentSlideIndex(index);
        setViewMode('presentation');
    };

    const containerRef = React.useRef(null);

    const toggleFullscreen = () => {
        console.log('Toggle fullscreen called');
        if (!document.fullscreenElement) {
            // Request fullscreen on the viewer container
            const container = containerRef.current;
            console.log('Container ref:', container);

            if (container) {
                try {
                    if (container.requestFullscreen) {
                        container.requestFullscreen();
                    } else if (container.webkitRequestFullscreen) {
                        container.webkitRequestFullscreen();
                    } else if (container.msRequestFullscreen) {
                        container.msRequestFullscreen();
                    }
                    setIsFullscreen(true);
                } catch (err) {
                    console.error('Error entering fullscreen:', err);
                }
            } else {
                console.error('Container ref is null');
            }
        } else {
            // Exit fullscreen
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) {
                document.msExitFullscreen();
            }
            setIsFullscreen(false);
        }
    };



    // renderSlide and renderContentBlocks are no longer needed in the parent component
    // as the iframe will handle rendering all slides, including the grid view.

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
        <div ref={containerRef} className={`viewer-container ${isFullscreen ? 'fullscreen-mode' : ''}`}>
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
                    <span className="slide-counter">
                        {currentSlideIndex + 1} / {infographic.slides.length}
                    </span>
                </div>

                <div className="viewer-actions">


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

                    <button
                        onClick={() => loadInfographic(true)}
                        className="btn-reload"
                        title="Recargar presentación"
                        style={{ backgroundColor: '#e74c3c', marginLeft: '0.5rem' }}
                    >
                        🔄
                    </button>
                </div>
            </div>

            {/* Presentation View (Used for both Presentation and Grid modes) */}
            <div className="presentation-view">
                <div
                    className="slide-viewport"
                    style={
                        viewMode === 'presentation'
                            ? (isFullscreen ? { transform: `scale(${fullscreenScale})` } : {})
                            : { width: '100%', maxWidth: '100%', height: '100%', background: '#1a1a1a', boxShadow: 'none' }
                    }
                >
                    {htmlContent ? (
                        <iframe
                            ref={iframeRef}
                            srcDoc={htmlContent}
                            className="slide-iframe"
                            title="Presentación"
                            allowFullScreen
                            style={{
                                background: viewMode === 'grid' ? '#1a1a1a' : 'white'
                            }}
                        />
                    ) : (
                        <div className="loading-spinner">
                            <div className="spinner"></div>
                            <p>Cargando presentación...</p>
                        </div>
                    )}
                </div>

                {/* Navigation Controls (Only in Presentation Mode) */}
                {viewMode === 'presentation' && (
                    <>
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
                            Usa las teclas ← → o espacio para navegar
                        </div>
                    </>
                )}
            </div>

            {/* Image Zoom Overlay */}
            {zoomedImage && (
                <div className="image-zoom-overlay" onClick={() => setZoomedImage(null)}>
                    <button className="close-zoom-btn" onClick={() => setZoomedImage(null)}>×</button>
                    <img
                        src={zoomedImage}
                        alt="Zoomed"
                        className="zoomed-image"
                        onClick={(e) => e.stopPropagation()} // Prevent closing when clicking image
                    />
                    <div className="zoom-hint">
                        Haz clic fuera de la imagen para cerrar
                    </div>
                </div>
            )}
        </div>
    );
}

export default InfographicViewer;
