import React, { useState, useEffect } from 'react';
import { API } from 'aws-amplify';
import './GeneradorContenido.css';

const GeneradorContenido = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [executionStatus, setExecutionStatus] = useState(null);
    const [currentExecutionArn, setCurrentExecutionArn] = useState(null);

    const [params, setParams] = useState({
        course_topic: '',
        course_duration_hours: 40,
        module_to_generate: 1,
        performance_mode: 'balanced',
        model_provider: 'bedrock'
    });

    const handleParamChange = (e) => {
        const { name, value, type } = e.target;
        let processedValue = value;

        if (type === 'number') {
            processedValue = parseInt(value, 10);
        }

        setParams(prev => ({ ...prev, [name]: processedValue }));
    };

    const handleGenerar = async () => {
        if (!params.course_topic.trim()) {
            setError("Por favor, ingresa el tema del curso.");
            return;
        }

        setIsLoading(true);
        setError('');
        setSuccess('');
        setExecutionStatus(null);
        setCurrentExecutionArn(null);

        try {
            // Call the start-job API using Amplify API with IAM authorization
            const response = await API.post('CourseGeneratorAPI', '/start-job', {
                body: params,
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            console.log('Course generation started:', response);

            setCurrentExecutionArn(response.execution_arn);
            setSuccess(`Generación de contenido iniciada. ARN: ${response.execution_arn}`);

            // Start polling for status
            pollExecutionStatus(response.execution_arn);

        } catch (err) {
            console.error("Error al iniciar generación de contenido:", err);
            setError(err.message || "Ocurrió un error al iniciar la generación.");
        } finally {
            setIsLoading(false);
        }
    };

    const pollExecutionStatus = async (executionArn) => {
        const pollInterval = 10000; // 10 seconds

        const poll = async () => {
            try {
                const response = await API.get('CourseGeneratorAPI', `/exec-status/${encodeURIComponent(executionArn)}`, {});

                setExecutionStatus(response);

                if (response.status === 'RUNNING' || response.status === 'PENDING') {
                    // Continue polling
                    setTimeout(poll, pollInterval);
                } else if (response.status === 'SUCCEEDED') {
                    setSuccess(`¡Generación completada exitosamente! Se generaron ${response.result?.content_statistics?.total_words || 0} palabras en ${response.result?.generated_lessons?.length || 0} lecciones.`);
                } else {
                    // Failed or other terminal state
                    setError(`La generación falló: ${response.error || 'Estado desconocido'}`);
                }
            } catch (err) {
                console.error("Error checking execution status:", err);
                setError("Error al verificar el estado de la ejecución.");
            }
        };

        // Start polling
        setTimeout(poll, pollInterval);
    };

    const getStatusColor = (status) => {
        switch (status) {
            case 'SUCCEEDED': return 'green';
            case 'FAILED': return 'red';
            case 'RUNNING': return 'blue';
            case 'PENDING': return 'orange';
            default: return 'gray';
        }
    };

    return (
        <div className="generador-contenido-container">
            <h2>Generador de Contenido de Curso</h2>
            <p>Genera contenido completo de curso con lecciones, diagramas y material visual usando IA.</p>

            <div className="formulario-contenido">
                <div className="form-grid">
                    <div className="form-group">
                        <label>Tema del Curso *</label>
                        <input
                            name="course_topic"
                            value={params.course_topic}
                            onChange={handleParamChange}
                            placeholder="Ej: Kubernetes for DevOps Engineers"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Duración del Curso (horas)</label>
                        <input
                            name="course_duration_hours"
                            type="number"
                            min="10"
                            max="200"
                            value={params.course_duration_hours}
                            onChange={handleParamChange}
                        />
                    </div>

                    <div className="form-group">
                        <label>Módulo a Generar</label>
                        <input
                            name="module_to_generate"
                            type="number"
                            min="1"
                            max="20"
                            value={params.module_to_generate}
                            onChange={handleParamChange}
                        />
                    </div>

                    <div className="form-group">
                        <label>Modo de Rendimiento</label>
                        <select name="performance_mode" value={params.performance_mode} onChange={handleParamChange}>
                            <option value="fast">Rápido (1 agente)</option>
                            <option value="balanced">Equilibrado</option>
                            <option value="maximum_quality">Máxima Calidad</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Proveedor de IA</label>
                        <select name="model_provider" value={params.model_provider} onChange={handleParamChange}>
                            <option value="bedrock">AWS Bedrock (Claude)</option>
                            <option value="openai">OpenAI (GPT)</option>
                        </select>
                    </div>
                </div>

                <button
                    className="btn-generar-contenido"
                    onClick={handleGenerar}
                    disabled={isLoading}
                >
                    {isLoading ? 'Iniciando Generación...' : 'Generar Contenido del Curso'}
                </button>
            </div>

            {error && <div className="error-mensaje">{error}</div>}
            {success && <div className="success-mensaje">{success}</div>}

            {executionStatus && (
                <div className="execution-status">
                    <h3>Estado de la Generación</h3>
                    <div className="status-info">
                        <p><strong>Estado:</strong> <span style={{ color: getStatusColor(executionStatus.status) }}>{executionStatus.status}</span></p>
                        <p><strong>ARN:</strong> {executionStatus.execution_arn}</p>
                        {executionStatus.start_date && (
                            <p><strong>Inicio:</strong> {new Date(executionStatus.start_date).toLocaleString()}</p>
                        )}
                        {executionStatus.stop_date && (
                            <p><strong>Fin:</strong> {new Date(executionStatus.stop_date).toLocaleString()}</p>
                        )}
                        {executionStatus.user_email && (
                            <p><strong>Usuario:</strong> {executionStatus.user_email}</p>
                        )}
                        {executionStatus.course_topic && (
                            <p><strong>Curso:</strong> {executionStatus.course_topic}</p>
                        )}
                        {executionStatus.module_to_generate && (
                            <p><strong>Módulo:</strong> {executionStatus.module_to_generate}</p>
                        )}
                    </div>

                    {executionStatus.result && (
                        <div className="generation-results">
                            <h4>Resultados</h4>
                            <div className="stats">
                                <p><strong>Palabras Totales:</strong> {executionStatus.result.content_statistics?.total_words || 0}</p>
                                <p><strong>Lecciones Generadas:</strong> {executionStatus.result.generated_lessons?.length || 0}</p>
                                <p><strong>Proyecto:</strong> {executionStatus.result.project_folder}</p>
                                <p><strong>Bucket:</strong> {executionStatus.result.bucket}</p>
                            </div>

                            {executionStatus.result.generated_lessons && (
                                <div className="lessons-list">
                                    <h5>Lecciones Generadas:</h5>
                                    <ul>
                                        {executionStatus.result.generated_lessons.map((lesson, index) => (
                                            <li key={index}>
                                                <strong>{lesson.lesson_title}</strong> - {lesson.word_count} palabras
                                                {lesson.lesson_bloom_level && ` (Bloom: ${lesson.lesson_bloom_level})`}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}

                    {executionStatus.execution_history && executionStatus.execution_history.length > 0 && (
                        <div className="execution-history">
                            <h4>Historial de Ejecución</h4>
                            <div className="history-timeline">
                                {executionStatus.execution_history.slice(0, 10).map((event, index) => (
                                    <div key={index} className="history-event">
                                        <span className="event-time">{new Date(event.timestamp).toLocaleTimeString()}</span>
                                        <span className="event-type">{event.type}</span>
                                        {event.state_entered_event_details && (
                                            <span className="event-details"> → {event.state_entered_event_details.name}</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default GeneradorContenido;