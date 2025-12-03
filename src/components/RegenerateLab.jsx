// src/components/RegenerateLab.jsx
import React, { useState } from 'react';
import { post } from 'aws-amplify/api';
import { fetchAuthSession } from 'aws-amplify/auth';
import './RegenerateLab.css';

/**
 * RegenerateLab Component
 * 
 * Provides UI for regenerating a single lab guide with optional additional requirements.
 * Invokes the course generator state machine with lab-only content type.
 * 
 * Props:
 * - projectFolder: string - Current project folder name
 * - outlineKey: string - S3 key to the outline file
 * - currentLabId: string - Current lab ID (e.g., "02-00-01")
 * - currentLabTitle: string - Current lab title for display
 * - onClose: function - Callback to close the modal
 * - onSuccess: function - Callback on successful regeneration start
 */
function RegenerateLab({ projectFolder, outlineKey, currentLabId, currentLabTitle, onClose, onSuccess }) {
    const [labRequirements, setLabRequirements] = useState('');
    const [isRegenerating, setIsRegenerating] = useState(false);
    const [error, setError] = useState(null);

    /**
     * Extract module number from lab ID
     * Example: "02-00-01" -> 2
     */
    const getModuleNumber = () => {
        if (!currentLabId) return null;
        const moduleNum = parseInt(currentLabId.split('-')[0], 10);
        return isNaN(moduleNum) ? null : moduleNum;
    };

    /**
     * Handle lab regeneration
     * Invokes state machine via /start-job API endpoint
     */
    const handleRegenerate = async () => {
        try {
            setError(null);
            setIsRegenerating(true);

            // Get module number
            const moduleNumber = getModuleNumber();
            if (!moduleNumber) {
                throw new Error('No se pudo determinar el número de módulo del lab actual');
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
            const requestBody = {
                course_bucket: 'crewai-course-artifacts',
                outline_s3_key: outlineKey, // Use actual outline key from BookEditor
                project_folder: projectFolder,
                content_type: 'labs',  // Labs only, not theory
                model_provider: 'bedrock',  // Force Bedrock for lab reliability
                image_model: 'models/gemini-2.5-flash-image',
                modules_to_generate: [moduleNumber],  // Only current module
                user_email: userEmail
            };

            // Add lab requirements if provided
            if (labRequirements.trim()) {
                requestBody.lab_requirements = labRequirements.trim();
            }

            console.log('🚀 Regenerating lab with params:', requestBody);

            // Call API
            const response = await post({
                apiName: 'CourseGeneratorAPI',
                path: '/start-job',
                options: {
                    body: requestBody
                }
            });

            console.log('✅ Lab regeneration started:', response);

            // Show success message
            const executionName = response.response?.executionArn?.split(':').pop() || 'unknown';
            alert(
                `✅ Regeneración de Laboratorio Iniciada\n\n` +
                `📝 Lab: ${currentLabTitle}\n` +
                `📦 Módulo: ${moduleNumber}\n` +
                `🔧 Modelo: Bedrock (Claude Sonnet 4.5)\n\n` +
                `⏱️ Tiempo estimado: 2-3 minutos\n\n` +
                `Recibirás una notificación por correo cuando el lab esté listo.\n` +
                `Refresca el editor de libro para ver el lab actualizado.`
            );

            // Call success callback
            if (onSuccess) {
                onSuccess(response);
            }

            // Close modal
            onClose();

        } catch (err) {
            console.error('❌ Error regenerating lab:', err);
            setError(err.message || 'Error al regenerar el laboratorio');
            setIsRegenerating(false);
        }
    };

    return (
        <div className="regenerate-lab-overlay" onClick={onClose}>
            <div className="regenerate-lab-modal" onClick={(e) => e.stopPropagation()}>
                <div className="regenerate-lab-header">
                    <h2>🔄 Regenerar Laboratorio</h2>
                    <button
                        className="regenerate-lab-close"
                        onClick={onClose}
                        disabled={isRegenerating}
                        title="Cerrar"
                    >
                        ✕
                    </button>
                </div>

                <div className="regenerate-lab-body">
                    <div className="regenerate-lab-info">
                        <p><strong>Lab Actual:</strong></p>
                        <p className="lab-title">{currentLabTitle || currentLabId}</p>
                        <p className="lab-id">ID: {currentLabId}</p>
                        <p className="lab-module">Módulo: {getModuleNumber()}</p>
                    </div>

                    <div className="regenerate-lab-form">
                        <label htmlFor="labRequirements">
                            🧪 Requerimientos Adicionales (Opcional)
                        </label>
                        <textarea
                            id="labRequirements"
                            rows={4}
                            value={labRequirements}
                            onChange={(e) => setLabRequirements(e.target.value)}
                            disabled={isRegenerating}
                            placeholder="Ej: Usar contenedores Docker, enfocarse en servicios AWS, incluir troubleshooting común..."
                            className="lab-requirements-input"
                        />
                        <small className="form-hint">
                            Especifica requisitos técnicos, plataformas, herramientas específicas, o consideraciones especiales que deben incluirse en los laboratorios
                        </small>
                    </div>

                    {error && (
                        <div className="regenerate-lab-error">
                            ⚠️ {error}
                        </div>
                    )}

                    <div className="regenerate-lab-warning">
                        <strong>⚠️ Nota:</strong> El laboratorio actual será reemplazado por la nueva versión generada.
                        Se recomienda crear una versión antes de regenerar.
                    </div>
                </div>

                <div className="regenerate-lab-footer">
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
                            '🚀 Regenerar Laboratorio'
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default RegenerateLab;
