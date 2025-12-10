// src/components/EstudiantesPortal.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchAuthSession } from 'aws-amplify/auth';
import './EstudiantesPortal.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;

function EstudiantesPortal() {
    const navigate = useNavigate();
    const [courses, setCourses] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [userEmail, setUserEmail] = useState('');

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

            // Load assigned courses for this user
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

    const openCourse = (course, bookType = 'theory') => {
        // Open in view-only mode for students
        navigate(`/book-editor/${course.courseId}?bookType=${bookType}&viewOnly=true&returnTo=/mis-cursos`);
    };

    if (loading) {
        return (
            <div className="estudiantes-portal">
                <div className="loading-container">
                    <div className="loading-spinner"></div>
                    <p>Cargando tus cursos...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="estudiantes-portal">
                <div className="error-container">
                    <h2>❌ Error</h2>
                    <p>{error}</p>
                    <button onClick={loadUserAndCourses}>Reintentar</button>
                </div>
            </div>
        );
    }

    return (
        <div className="estudiantes-portal">
            <div className="estudiantes-header">
                <h1>📚 Mis Cursos</h1>
                <p>Bienvenido, <strong>{userEmail}</strong></p>
                <p className="subtitle">Aquí puedes acceder a los cursos que te han sido asignados</p>
            </div>

            {courses.length === 0 ? (
                <div className="no-courses">
                    <div className="no-courses-icon">📭</div>
                    <h2>No tienes cursos asignados</h2>
                    <p>Contacta a tu administrador para que te asigne los cursos correspondientes.</p>
                </div>
            ) : (
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
                                            Asignado: {new Date(course.assignedAt).toLocaleDateString('es-ES')}
                                        </span>
                                    )}
                                </div>
                            </div>
                            <div className="course-actions">
                                {course.hasBook && (
                                    <button
                                        className="btn-view"
                                        onClick={() => openCourse(course, 'theory')}
                                    >
                                        📖 Acceder
                                    </button>
                                )}
                                {course.hasLabGuide && (
                                    <button
                                        className="btn-view lab"
                                        onClick={() => openCourse(course, 'lab')}
                                    >
                                        🧪 Ver Labs
                                    </button>
                                )}
                                {!course.hasBook && !course.hasLabGuide && (
                                    <span className="no-content">Contenido no disponible aún</span>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default EstudiantesPortal;
