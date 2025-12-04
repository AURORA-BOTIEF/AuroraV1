// src/components/RegenerateLesson.jsx
import React, { useState } from 'react';
import { post } from 'aws-amplify/api';
import { fetchAuthSession } from 'aws-amplify/auth';
import './RegenerateLesson.css';

/**
 * RegenerateLesson Component
 * 
 * Provides UI for regenerating a single lesson with optional additional requirements.
 * Invokes the course generator state machine with theory-only content type.
 * 
 * Props:
 * - projectFolder: string - Current project folder name
 * - outlineKey: string - S3 key to the outline file
 * - currentLessonId: string - Current lesson ID (e.g., "01-02" for module 1, lesson 2)
 * - currentLessonTitle: string - Current lesson title for display
 * - moduleNumber: number - Module number the lesson belongs to
 * - lessonNumber: number - Lesson number within the module
 * - onClose: function - Callback to close the modal
 * - onSuccess: function - Callback on successful regeneration start
 */
function RegenerateLesson({
    projectFolder,
    outlineKey,
    currentLessonId,
    currentLessonTitle,
    moduleNumber,
    lessonNumber,
    onClose,
    onSuccess
}) {
    const [lessonRequirements, setLessonRequirements] = useState('');
    const [isRegenerating, setIsRegenerating] = useState(false);
    const [error, setError] = useState(null);
    const [showSuccessModal, setShowSuccessModal] = useState(false);

    /**
     * Handle lesson regeneration
     * Invokes state machine via /start-job API endpoint
     */
    const handleRegenerate = async () => {
        try {
            setError(null);
            setIsRegenerating(true);

            if (!moduleNumber) {
                throw new Error('No se pudo determinar el número de módulo para esta lección');
            }

            // Get user email for notifications
            let userEmail = null;
            try {
                const session = await fetchAuthSession();
                userEmail = session?.tokens?.idToken?.payload?.email || null;
                console.log('📧 User email for notifications:', userEmail);
            } catch (emailError) {
                console.warn('Could not extract user email:', emailError);
            }

            // Build request body
            console.log('🔍 DEBUG RegenerateLesson props:', {
                moduleNumber,
                currentLessonId,
                projectFolder,
                outlineKey,
                willSendModuleNumber: moduleNumber
            });

            const requestBody = {
                course_bucket: 'crewai-course-artifacts',
                outline_s3_key: outlineKey,
                project_folder: projectFolder,
                content_type: 'theory',  // Theory only, not labs
                model_provider: 'bedrock',
                image_model: 'models/gemini-2.5-flash-image',
                module_number: moduleNumber,  // Only the module containing this lesson (backend expects module_number, not modules_to_generate)
                lesson_to_generate: currentLessonId,  // Specific lesson ID (e.g., "01-02")
                user_email: userEmail
            };

            // Add lesson requirements if provided
            if (lessonRequirements.trim()) {
                requestBody.lesson_requirements = lessonRequirements.trim();
            }

            console.log('🚀 Regenerating lesson with params:', requestBody);

            // Call API
            const response = await post({
                apiName: 'CourseGeneratorAPI',
                path: '/start-job',
                options: {
                    body: requestBody
                }
            });

            console.log('✅ Lesson regeneration started:', response);

            // Show custom success modal
            setShowSuccessModal(true);

            // Call success callback
            if (onSuccess) {
                onSuccess(response);
            }

        } catch (err) {
            console.error('❌ Error regenerating lesson:', err);
            setError(err.message || 'Error al regenerar la lección');
            setIsRegenerating(false);
        }
    };

    /**
     * Handle closing the success modal
     */
    const handleSuccessClose = () => {
        setShowSuccessModal(false);
        onClose();
    };

    return (
        <>
            {!showSuccessModal && (
                <div className="regenerate-lesson-overlay" onClick={onClose}>
                    <div className="regenerate-lesson-modal" onClick={(e) => e.stopPropagation()}>
                        <div className="regenerate-lesson-header">
                            <h2>📖 Regenerar Lección</h2>
                            <button
                                className="regenerate-lesson-close"
                                onClick={onClose}
                                disabled={isRegenerating}
                                title="Cerrar"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="regenerate-lesson-body">
                            <div className="regenerate-lesson-info">
                                <p><strong>Lección Actual:</strong></p>
                                <p className="lesson-title">{currentLessonTitle || currentLessonId}</p>
                                <p className="lesson-id">ID: {currentLessonId}</p>
                                <p className="lesson-module">Módulo: {moduleNumber} | Lección: {lessonNumber}</p>
                            </div>

                            <div className="regenerate-lesson-form">
                                <label htmlFor="lessonRequirements">
                                    📝 Requisitos Adicionales (Opcional)
                                </label>
                                <textarea
                                    id="lessonRequirements"
                                    rows={4}
                                    value={lessonRequirements}
                                    onChange={(e) => setLessonRequirements(e.target.value)}
                                    disabled={isRegenerating}
                                    placeholder="Ej.: Profundizar en optimización de rendimiento, incluir más ejemplos del mundo real, enfocarse en mejores prácticas..."
                                    className="lesson-requirements-input"
                                />
                                <small className="form-hint">
                                    Especifica temas a enfatizar, profundidad adicional, ejemplos a incluir, o consideraciones especiales para esta lección
                                </small>
                            </div>

                            {error && (
                                <div className="regenerate-lesson-error">
                                    ⚠️ {error}
                                </div>
                            )}

                            <div className="regenerate-lesson-warning">
                                <strong>⚠️ Nota:</strong> La lección actual será reemplazada por la versión recién generada.
                                Se recomienda guardar una versión antes de regenerar.
                            </div>
                        </div>

                        <div className="regenerate-lesson-footer">
                            <button
                                className="btn-cancel"
                                onClick={onClose}
                                disabled={isRegenerating}
                            >
                                Cancelar
                            </button>
                            <button
                                className="btn-regenerate"
                                onClick={handleRegenerate}
                                disabled={isRegenerating}
                            >
                                {isRegenerating ? (
                                    <>
                                        <span className="spinner-small"></span>
                                        Regenerando...
                                    </>
                                ) : (
                                    '🚀 Regenerar Lección'
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Modal de Éxito */}
            {showSuccessModal && (
                <div className="regenerate-lesson-success-overlay" onClick={handleSuccessClose}>
                    <div className="regenerate-lesson-success-modal" onClick={(e) => e.stopPropagation()}>
                        <div className="regenerate-lesson-success-header">
                            <h3>✅ Regeneración Lista para Iniciar</h3>
                        </div>
                        <div className="regenerate-lesson-success-body">
                            <p>⏱️ <span className="highlight">Tiempo estimado:</span> 2-3 minutos</p>
                            <p>Recibirás una notificación por email cuando la lección esté lista.</p>
                            <p>Actualiza el editor de libro para ver la lección actualizada.</p>
                        </div>
                        <div className="regenerate-lesson-success-footer">
                            <button className="btn-success-cancel" onClick={handleSuccessClose}>
                                Cancelar
                            </button>
                            <button className="btn-success-ok" onClick={handleSuccessClose}>
                                Aceptar
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

export default RegenerateLesson;
