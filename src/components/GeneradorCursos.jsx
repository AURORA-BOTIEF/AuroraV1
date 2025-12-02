// src/components/GeneradorCursos.jsx
import React, { useState, useEffect } from 'react';
import { getCurrentUser, fetchAuthSession, fetchUserAttributes } from 'aws-amplify/auth';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { Upload } from '@aws-sdk/lib-storage';
import { post } from 'aws-amplify/api';
import './GeneradorCursos.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;
const API_NAME = 'CourseGeneratorAPI';

function GeneradorCursos() {
    const [outlineFile, setOutlineFile] = useState(null);
    const [projectFolder, setProjectFolder] = useState('');
    const [moduleInput, setModuleInput] = useState('1');
    const [generateFullCourse, setGenerateFullCourse] = useState(true); // Always full course
    const [modelProvider, setModelProvider] = useState('bedrock');
    const [imageModel, setImageModel] = useState('models/gemini-2.5-flash-image'); // Default to cost-optimized
    const contentType = 'both'; // Always theory + labs
    const [labRequirements, setLabRequirements] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [userEmail, setUserEmail] = useState('');
    const [statusMessage, setStatusMessage] = useState('');
    const [errorMessage, setErrorMessage] = useState('');
    const [successMessage, setSuccessMessage] = useState('');

    const COURSE_BUCKET = 'crewai-course-artifacts';

    useEffect(() => {
        checkAuth();
    }, []);

    const checkAuth = async () => {
        try {
            const user = await getCurrentUser();
            const attributes = await fetchUserAttributes();
            setIsAuthenticated(true);
            setUserEmail(attributes.email || '');
            console.log('Usuario autenticado:', user.username, attributes.email);
        } catch (e) {
            setIsAuthenticated(false);
            console.log('Usuario no autenticado');
        }
    };

    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (file) {
            // Validate file type
            if (!file.name.endsWith('.yaml') && !file.name.endsWith('.yml')) {
                setErrorMessage('Por favor selecciona un archivo YAML válido (.yaml o .yml)');
                setOutlineFile(null);
                return;
            }
            setOutlineFile(file);
            setErrorMessage('');

            // Auto-generate project folder name if empty
            if (!projectFolder) {
                // Get date in YYMMDD format
                const date = new Date();
                const year = date.getFullYear().toString().slice(-2);
                const month = (date.getMonth() + 1).toString().padStart(2, '0');
                const day = date.getDate().toString().padStart(2, '0');
                const timestamp = `${year}${month}${day}`;

                const baseName = file.name.replace(/\.(yaml|yml)$/, '').replace(/[^a-zA-Z0-9-]/g, '-');
                setProjectFolder(`${timestamp}-${baseName}`);
            }
        }
    };

    const validateInputs = () => {
        if (!outlineFile) {
            setErrorMessage('Debes seleccionar un archivo de outline');
            return false;
        }

        if (!projectFolder.trim()) {
            setErrorMessage('Debes especificar un nombre de proyecto');
            return false;
        }

        if (!generateFullCourse) {
            const modulePattern = /^(\d+(-\d+)?)(,\d+(-\d+)?)*$/;
            if (!modulePattern.test(moduleInput.trim())) {
                setErrorMessage('Formato de módulos inválido. Ejemplos: "1", "1,3", "1-5", "1,3-5"');
                return false;
            }
        }

        return true;
    };

    const uploadToS3 = async (file, currentProjectFolder) => {
        try {
            const session = await fetchAuthSession();
            const s3Client = new S3Client({
                region: 'us-east-1',
                credentials: session.credentials,
            });

            // Use project folder structure as requested
            const key = `${currentProjectFolder}/outline/${file.name}`;

            const fileSize = file.size || 0;
            const MAX_SINGLE_PUT = 64 * 1024 * 1024;

            const upload = new Upload({
                client: s3Client,
                params: {
                    Bucket: COURSE_BUCKET,
                    Key: key,
                    Body: file,
                    ContentType: 'application/x-yaml',
                },
                queueSize: 3,
                partSize: Math.min(MAX_SINGLE_PUT, Math.max(5 * 1024 * 1024, fileSize + 1)),
            });

            try {
                await upload.done();
            } catch (err) {
                const msg = String(err?.message || '').toLowerCase();
                if (msg.includes('crc32') || msg.includes('checksum')) {
                    await s3Client.send(new PutObjectCommand({
                        Bucket: COURSE_BUCKET,
                        Key: key,
                        Body: file,
                        ContentType: 'application/x-yaml',
                    }));
                } else {
                    throw err;
                }
            }

            return key;
        } catch (error) {
            console.error('Error subiendo a S3:', error);
            throw new Error(`Error al subir el archivo: ${error.message}`);
        }
    };

    const startGeneration = async (uploadedKey, modules) => {
        try {
            const body = {
                course_bucket: COURSE_BUCKET,
                outline_s3_key: uploadedKey,
                project_folder: projectFolder,
                module_number: modules, // For single module or first module
                model_provider: modelProvider,
                image_model: imageModel, // 'gemini' or 'imagen'
                content_type: contentType, // 'theory', 'labs', or 'both'
                lab_requirements: labRequirements.trim() || undefined, // Optional
                user_email: userEmail, // Send user email for notifications
                // Note: NOT sending lesson_number = MODULE mode
            };

            console.log('Iniciando generación:', body);

            const restOperation = post({
                apiName: API_NAME,
                path: '/start-job',
                options: {
                    body: body,
                    headers: {
                        'Content-Type': 'application/json',
                    }
                }
            });

            const response = await restOperation.response;
            const data = await response.body.json();

            if (response.statusCode !== 200) {
                throw new Error(`Error al iniciar la generación: ${response.statusCode}`);
            }

            return data;
        } catch (error) {
            console.error('Error iniciando generación:', error);
            throw new Error(`Error al iniciar la generación: ${error.message}`);
        }
    };

    const parseModules = (input) => {
        // Parse "1", "1,3", "1-5", "1,3-5" into array of module numbers
        const modules = [];
        const parts = input.split(',');

        for (const part of parts) {
            const trimmed = part.trim();
            if (trimmed.includes('-')) {
                const [start, end] = trimmed.split('-').map(n => parseInt(n.trim()));
                for (let i = start; i <= end; i++) {
                    if (!modules.includes(i)) modules.push(i);
                }
            } else {
                const num = parseInt(trimmed);
                if (!modules.includes(num)) modules.push(num);
            }
        }

        return modules.sort((a, b) => a - b);
    };

    const handleGenerate = async () => {
        setErrorMessage('');
        setSuccessMessage('');
        setStatusMessage('');

        if (!validateInputs()) {
            return;
        }

        if (!isAuthenticated) {
            setErrorMessage('Debes estar autenticado para usar esta función');
            return;
        }

        setIsProcessing(true);

        try {
            // Step 1: Upload file to S3
            setStatusMessage('📤 Subiendo archivo de outline...');
            // Change: Pass projectFolder to upload function
            const uploadedKey = await uploadToS3(outlineFile, projectFolder);
            console.log('Archivo subido:', uploadedKey);

            // Step 2: Start generation - always full course with theory + labs
            setStatusMessage('🚀 Iniciando generación de curso completo...');
            await startGeneration(uploadedKey, 'all');
            setSuccessMessage('✅ Generación de contenido teórico y guía de laboratorios del curso completo iniciada exitosamente');

            // Show success message
            setStatusMessage('');

            // Reset form after a delay
            setTimeout(() => {
                setOutlineFile(null);
                setLabRequirements('');
                document.getElementById('fileInput').value = '';
            }, 3000);

        } catch (error) {
            console.error('Error en el proceso:', error);
            setErrorMessage(error.message);
            setStatusMessage('');
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div className="generador-cursos-page">
            <div className="page-header">
                <h1>🎓 Generador de Contenido de Cursos</h1>
                <p>Sistema inteligente de generación de contenido educativo mediante IA</p>
            </div>

            <div className="generator-container">
                {!isAuthenticated && (
                    <div className="alert alert-warning">
                        <strong>⚠️ Autenticación requerida</strong>
                        <p>Debes iniciar sesión para usar el generador de cursos.</p>
                        <button
                            className="btn-primary"
                            onClick={() => window.location.href = '/'}
                        >
                            Ir a Iniciar Sesión
                        </button>
                    </div>
                )}

                {isAuthenticated && (
                    <div className="generator-form">
                        {/* File Upload Section */}
                        <div className="form-section">
                            <h3>📁 Temario del Curso</h3>
                            <p className="section-description">
                                Selecciona el archivo YAML que contiene la estructura del curso
                            </p>

                            <div className="file-upload-area">
                                <input
                                    id="fileInput"
                                    type="file"
                                    accept=".yaml,.yml"
                                    onChange={handleFileSelect}
                                    disabled={isProcessing}
                                    className="file-input"
                                />
                                <label htmlFor="fileInput" className="file-label">
                                    {outlineFile ? (
                                        <>
                                            <span className="file-icon">📄</span>
                                            <span className="file-name">{outlineFile.name}</span>
                                            <span className="file-size">({(outlineFile.size / 1024).toFixed(1)} KB)</span>
                                        </>
                                    ) : (
                                        <>
                                            <span className="file-icon">📤</span>
                                            <span>Haz clic o arrastra el archivo aquí</span>
                                        </>
                                    )}
                                </label>
                            </div>
                        </div>

                        {/* Project Settings */}
                        <div className="form-section">
                            <h3>⚙️ Configuración del Proyecto</h3>

                            <div className="form-group">
                                <label htmlFor="projectFolder">Nombre del Proyecto</label>
                                <input
                                    id="projectFolder"
                                    type="text"
                                    value={projectFolder}
                                    onChange={(e) => setProjectFolder(e.target.value)}
                                    placeholder="ej: 20251011-aws-lambda-curso"
                                    disabled={isProcessing}
                                    className="form-input"
                                />
                                <small className="form-hint">
                                    Identificador único para este proyecto (se genera automáticamente)
                                </small>
                            </div>

                            <div className="form-group">
                                <label htmlFor="modelProvider">Proveedor de IA</label>
                                <select
                                    id="modelProvider"
                                    value={modelProvider}
                                    onChange={(e) => setModelProvider(e.target.value)}
                                    disabled={isProcessing}
                                    className="form-select"
                                >
                                    <option value="bedrock">AWS Bedrock (Claude 4.5 Sonnet)</option>
                                    <option value="openai">OpenAI (GPT-5)</option>
                                </select>
                                <small className="form-hint">
                                    Modelo de IA que se utilizará para generar el contenido
                                </small>
                            </div>

                            <div className="form-group">
                                <label htmlFor="imageModel">Modelo de Generación de Imágenes</label>
                                <select
                                    id="imageModel"
                                    value={imageModel}
                                    onChange={(e) => setImageModel(e.target.value)}
                                    disabled={isProcessing}
                                    className="form-select"
                                >
                                    <option value="models/gemini-2.5-flash-image">Gemini 2.5 Flash Image</option>
                                    {/* Gemini 3 Pro disabled due to Lambda timeout issues (takes ~10min per image) */}
                                    {/* <option value="models/gemini-3-pro-image-preview">Gemini 3 Pro Image Preview (Alta Calidad)</option> */}
                                </select>
                                <small className="form-hint">
                                    Modelo de IA usado para generar imágenes
                                </small>
                            </div>
                        </div>

                        {/* Lab Requirements - Always shown since we always generate labs */}
                        <div className="form-section">
                            <h3>🧪 Requerimientos Adicionales para Laboratorios (Opcional)</h3>
                            <p className="section-description">
                                Especifica requisitos técnicos, plataformas, herramientas específicas, o consideraciones especiales que deben incluirse en los laboratorios
                            </p>
                            <div className="form-group">
                                <textarea
                                    id="labRequirements"
                                    value={labRequirements}
                                    onChange={(e) => setLabRequirements(e.target.value)}
                                    placeholder="Ej: Usar contenedores Docker, enfocarse en servicios AWS, incluir troubleshooting común, considerar ambiente Windows..."
                                    disabled={isProcessing}
                                    className="form-input"
                                    rows="4"
                                    style={{
                                        resize: 'vertical',
                                        fontFamily: 'inherit',
                                        fontSize: '0.95rem',
                                        lineHeight: '1.5'
                                    }}
                                />
                            </div>
                        </div>



                        {/* Action Buttons */}
                        <div className="form-actions">
                            <button
                                className="btn-generate"
                                onClick={handleGenerate}
                                disabled={!outlineFile || isProcessing || !isAuthenticated}
                            >
                                {isProcessing ? (
                                    <>
                                        <span className="spinner"></span>
                                        Procesando...
                                    </>
                                ) : (
                                    <>
                                        🚀 Generar Contenido
                                    </>
                                )}
                            </button>
                        </div>

                        {/* Status Messages */}
                        {statusMessage && (
                            <div className="alert alert-info">
                                {statusMessage}
                            </div>
                        )}

                        {errorMessage && (
                            <div className="alert alert-error">
                                <strong>❌ Error:</strong> {errorMessage}
                            </div>
                        )}

                        {successMessage && (
                            <div className="alert alert-success">
                                <strong>{successMessage}</strong>
                                <p style={{ marginTop: '0.5rem' }}>
                                    Su requerimiento está siendo procesado para generar el contenido teórico y la guía de laboratorios del curso completo.
                                    Usted recibirá una notificación a su correo electrónico una vez el proceso haya finalizado.
                                </p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

export default GeneradorCursos;
