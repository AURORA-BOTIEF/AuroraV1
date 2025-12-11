// src/components/InstructoresExternosPortal.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchAuthSession } from 'aws-amplify/auth';
import './InstructoresExternosPortal.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;
const PRESENTACIONES_API = 'https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod';

function InstructoresExternosPortal() {
    const navigate = useNavigate();
    const [courses, setCourses] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [userEmail, setUserEmail] = useState('');
    const [activeTab, setActiveTab] = useState('cursos'); // 'cursos' or 'presentaciones'
    const [presentations, setPresentations] = useState([]);
    const [loadingPresentations, setLoadingPresentations] = useState(false);

    useEffect(() => {
        loadUserAndCourses();
    }, []);

    const loadUserAndCourses = async () => {
        try {
            setLoading(true);

            // Get current user's email from Cognito
            const session = await fetchAuthSession();
            const email = session.tokens?.idToken?.payload?.email;

            if (!email) {
                throw new Error('No se pudo obtener el email del usuario');
            }

            setUserEmail(email);

            // Load assigned courses for this instructor (reusing student-courses endpoint)
            const encodedEmail = encodeURIComponent(email);
            const response = await fetch(`${API_BASE}/student-courses/${encodedEmail}`);

            if (!response.ok) {
                throw new Error('Error al cargar cursos asignados');
            }

            const data = await response.json();
            setCourses(data.courses || []);
        } catch (err) {
            console.error('Error loading courses:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const loadPresentations = async () => {
        if (courses.length === 0) return;

        setLoadingPresentations(true);
        try {
            const response = await fetch(`${PRESENTACIONES_API}/list-infographics?limit=100`);
            if (!response.ok) {
                throw new Error('Error al cargar presentaciones');
            }
            const data = await response.json();

            // Filter presentations to only show those matching assigned courses
            const assignedFolders = courses.map(c => c.courseId.toLowerCase());
            const filteredPresentations = (data.infographics || []).filter(p => {
                const folderLower = (p.folder || '').toLowerCase();
                return assignedFolders.some(af => folderLower.includes(af) || af.includes(folderLower));
            });

            setPresentations(filteredPresentations);
        } catch (err) {
            console.error('Error loading presentations:', err);
        } finally {
            setLoadingPresentations(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'presentaciones' && courses.length > 0 && presentations.length === 0) {
            loadPresentations();
        }
    }, [activeTab, courses]);

    const openBookEditor = (course, bookType = 'theory') => {
        // Full edit access for external instructors
        navigate(`/book-editor/${course.courseId}?bookType=${bookType}&returnTo=/portal-instructor`);
    };

    const openBookBuilder = (courseId) => {
        navigate(`/generador-contenidos/book-builder?courseId=${courseId}`);
    };

    const viewPresentation = (folder) => {
        navigate(`/presentaciones/viewer/${encodeURIComponent(folder)}`);
    };

    const editPresentation = (folder) => {
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

    if (loading) {
        return (
            <div className="instructores-portal">
                <div className="loading-container">
                    <div className="loading-spinner"></div>
                    <p>Cargando tus cursos...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="instructores-portal">
                <div className="error-container">
                    <h2>❌ Error</h2>
                    <p>{error}</p>
                    <button onClick={loadUserAndCourses}>Reintentar</button>
                </div>
            </div>
        );
    }

    return (
        <div className="instructores-portal">
            <div className="instructores-header">
                <h1>👨‍🏫 Portal del Instructor</h1>
                <p>Bienvenido, <strong>{userEmail}</strong></p>
                <p className="subtitle">Accede a los cursos y presentaciones que te han sido asignados</p>
            </div>

            <div className="instructor-tabs">
                <button
                    className={`tab-btn ${activeTab === 'cursos' ? 'active' : ''}`}
                    onClick={() => setActiveTab('cursos')}
                >
                    📚 Mis Cursos
                </button>
                <button
                    className={`tab-btn ${activeTab === 'presentaciones' ? 'active' : ''}`}
                    onClick={() => setActiveTab('presentaciones')}
                >
                    📊 Presentaciones
                </button>
            </div>

            {courses.length === 0 ? (
                <div className="no-courses">
                    <div className="no-courses-icon">📭</div>
                    <h2>No tienes cursos asignados</h2>
                    <p>Contacta a tu administrador para que te asigne los cursos correspondientes.</p>
                </div>
            ) : (
                <>
                    {activeTab === 'cursos' && (
                        <div className="courses-grid">
                            {courses.map(course => (
                                <div key={course.courseId} className="course-card">
                                    <div className="course-icon">📘</div>
                                    <div className="course-info">
                                        <h3>{course.title}</h3>
                                        {course.description && (
                                            <p className="course-description">{course.description}</p>
                                        )}
                                        <div className="course-meta">
                                            {course.assignedAt && (
                                                <span className="assigned-date">
                                                    Asignado: {formatDate(course.assignedAt)}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="course-actions">
                                        {course.hasBook && (
                                            <button
                                                className="btn-action theory"
                                                onClick={() => openBookEditor(course, 'theory')}
                                                title="Acceder al curso"
                                            >
                                                📖 Acceder
                                            </button>
                                        )}
                                        {course.hasLabGuide && (
                                            <button
                                                className="btn-action lab"
                                                onClick={() => openBookEditor(course, 'lab')}
                                                title="Editar guía de laboratorio"
                                            >
                                                🧪 Guía Labs
                                            </button>
                                        )}
                                        {!course.hasBook && !course.hasLabGuide && (
                                            <span className="no-content">No hay contenido disponible aún</span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {activeTab === 'presentaciones' && (
                        <div className="presentations-section">
                            {loadingPresentations ? (
                                <div className="loading-container small">
                                    <div className="loading-spinner"></div>
                                    <p>Cargando presentaciones...</p>
                                </div>
                            ) : presentations.length === 0 ? (
                                <div className="no-courses">
                                    <div className="no-courses-icon">📊</div>
                                    <h2>No hay presentaciones disponibles</h2>
                                    <p>Aún no se han generado presentaciones para tus cursos asignados.</p>
                                </div>
                            ) : (
                                <div className="presentations-grid">
                                    {presentations.map(pres => (
                                        <div key={pres.folder} className="presentation-card">
                                            <div className="presentation-thumbnail">
                                                {pres.thumbnail_url ? (
                                                    <img src={pres.thumbnail_url} alt={pres.title} />
                                                ) : (
                                                    <div className="placeholder-thumb">📊</div>
                                                )}
                                            </div>
                                            <div className="presentation-info">
                                                <h3>{pres.title}</h3>
                                                <p className="presentation-topic">{pres.course_topic}</p>
                                                <p className="presentation-date">
                                                    {formatDate(pres.created_date)}
                                                </p>
                                            </div>
                                            <div className="presentation-actions">
                                                <button
                                                    className="btn-action view"
                                                    onClick={() => viewPresentation(pres.folder)}
                                                >
                                                    👁️ Ver
                                                </button>
                                                <button
                                                    className="btn-action edit"
                                                    onClick={() => editPresentation(pres.folder)}
                                                >
                                                    ✏️ Editar
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

export default InstructoresExternosPortal;
