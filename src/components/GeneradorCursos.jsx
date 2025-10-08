// src/components/GeneradorCursos.jsx
import React, { useState, useEffect } from 'react';
import { Auth } from 'aws-amplify';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { Upload } from '@aws-sdk/lib-storage';
import { API } from 'aws-amplify';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;
const PRESIGN_ENDPOINT = `${API_BASE}/presign`;
const START_JOB_ENDPOINT = `${API_BASE}/start-job`;
const EXEC_STATUS_ENDPOINT = `${API_BASE}/exec-status`;

// Amplify API configuration
const API_NAME = 'CourseGeneratorAPI'; // This matches the API name in amplify.js

function GeneradorCursos() {
    const [uploadedKey, setUploadedKey] = useState(null);
    const [executionArn, setExecutionArn] = useState(null);
    const [execState, setExecState] = useState('Not started');
    const [execStatus, setExecStatus] = useState('No execution yet');
    const [prompts, setPrompts] = useState([]);
    const [images, setImages] = useState([]);
    const [uploadStatus, setUploadStatus] = useState('');
    const [startStatus, setStartStatus] = useState('');
    const [courseBucket, setCourseBucket] = useState('crewai-course-artifacts');
    const [projectFolder, setProjectFolder] = useState('');
    const [moduleNum, setModuleNum] = useState(3);
    const [lessonNum, setLessonNum] = useState(1);
    const [modelProvider, setModelProvider] = useState('bedrock');
    const [isAuthenticated, setIsAuthenticated] = useState(false);

    // Check authentication status on mount
    useEffect(() => {
        const checkAuth = async () => {
            try {
                const user = await Auth.currentAuthenticatedUser();
                setIsAuthenticated(true);
                console.log('User is authenticated:', user.username);
            } catch (e) {
                setIsAuthenticated(false);
                console.log('User is not authenticated');
            }
        };
        checkAuth();
    }, []);

    // Helper function to make authenticated API requests using Amplify
    const makeApiRequest = async (path, options = {}) => {
        if (!isAuthenticated) {
            throw new Error('Authentication required');
        }

        // Log credentials to debug IAM signing
        try {
            const credentials = await Auth.currentCredentials();
            console.log('AWS Credentials:', {
                accessKeyId: credentials.accessKeyId ? '***' + credentials.accessKeyId.slice(-4) : 'missing',
                authenticated: credentials.authenticated,
                expiration: credentials.expiration,
            });
        } catch (credError) {
            console.error('Failed to get credentials:', credError);
        }

        const apiOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            body: options.body, // Amplify expects body as object, not stringified
        };

        console.log('Making API request:', {
            path,
            method: options.method || 'GET',
            headers: apiOptions.headers,
            body: apiOptions.body,
        });

        try {
            // Use Amplify API with explicit IAM signing
            let response;
            if (options.method === 'POST') {
                response = await API.post(API_NAME, path, {
                    body: apiOptions.body,
                    headers: apiOptions.headers,
                });
            } else {
                response = await API.get(API_NAME, path, {
                    headers: apiOptions.headers,
                });
            }
            console.log('API response:', response);
            // Amplify returns the response data directly on success
            return {
                ok: true,
                json: () => Promise.resolve(response),
                status: 200,
            };
        } catch (error) {
            console.error('API request failed:', error);
            console.error('Error response:', error.response);
            console.error('Error status:', error.response?.status);
            console.error('Error data:', error.response?.data);
            // Amplify throws exceptions on error
            return {
                ok: false,
                status: error.response?.status || 500,
                statusText: error.message || 'Request failed',
                json: () => Promise.resolve(error.response?.data || { error: error.message }),
            };
        }
    };

    useEffect(() => {
        if (executionArn && (execState === 'RUNNING' || execState === 'STARTED')) {
            const timer = setTimeout(pollStatus, 3000);
            return () => clearTimeout(timer);
        }
    }, [executionArn, execState]);

    const handleUpload = async () => {
        if (!isAuthenticated) {
            setUploadStatus('Error: You must be authenticated to upload files');
            return;
        }
        const fileInput = document.getElementById('fileInput');
        const f = fileInput.files[0];
        if (!f) return alert('Choose a file first');
        setUploadStatus('Getting credentials...');

        try {
            const credentials = await Auth.currentCredentials();
            const s3Client = new S3Client({
                region: 'us-east-1',
                credentials: {
                    accessKeyId: credentials.accessKeyId,
                    secretAccessKey: credentials.secretAccessKey,
                    sessionToken: credentials.sessionToken,
                },
            });

            setUploadStatus('Uploading...');
            const key = `uploads/${Date.now()}-${f.name}`;
            const upload = new Upload({
                client: s3Client,
                params: {
                    Bucket: courseBucket,
                    Key: key,
                    Body: f,
                    ContentType: 'application/x-yaml',
                },
            });

            await upload.done();
            setUploadedKey(key);
            setUploadStatus('Uploaded: ' + key);
        } catch (e) {
            console.error('Upload error', e);
            setUploadStatus('Error during upload: ' + e);
        }
    }; const handleStart = async () => {
        if (!isAuthenticated) {
            setStartStatus('Error: You must be authenticated to use this feature');
            return;
        }
        if (!uploadedKey) return alert('Please upload an outline first');
        setStartStatus('Starting execution...');
        const body = {
            course_bucket: courseBucket,
            outline_s3_key: uploadedKey,
            project_folder: projectFolder,
            module_to_generate: moduleNum,
            lesson_to_generate: lessonNum,
            model_provider: modelProvider
        };
        console.log('Sending request body:', JSON.stringify(body, null, 2));
        try {
            const resp = await makeApiRequest('/start-job', {
                method: 'POST',
                body: body  // Pass as object, not JSON string - Amplify will serialize it
            });
            if (!resp.ok) {
                const errorData = await resp.json();
                setStartStatus(`Failed to start execution: ${resp.status} ${resp.statusText} - ${JSON.stringify(errorData)}`);
                return;
            }
            const data = await resp.json();
            const arn = data.executionArn || data.execution_arn;
            setExecutionArn(arn);
            setStartStatus('Execution started');
            setExecState('STARTED');
            setExecStatus('Polling for status...');
            setPrompts([]);
            setImages([]);
        } catch (e) {
            setStartStatus('Error: ' + e);
        }
    };

    const pollStatus = async () => {
        if (!isAuthenticated) {
            setExecStatus('Error: Authentication required');
            return;
        }
        if (!executionArn) return;
        try {
            const resp = await makeApiRequest(`/exec-status/${encodeURIComponent(executionArn)}`);
            if (!resp.ok) {
                const errorData = await resp.json();
                throw new Error(`status failed: ${resp.status} ${resp.statusText} - ${JSON.stringify(errorData)}`);
            }
            const j = await resp.json();
            setExecState(j.status || '-');
            setExecStatus(JSON.stringify(j, null, 2));

            if (j.status === 'SUCCEEDED' && j.output) {
                let out = j.output;
                if (typeof out === 'string') {
                    try { out = JSON.parse(out); } catch (e) { /* leave as-is */ }
                }
                if (out && out.Payload) out = out.Payload;

                const promptsData = out && (out.generated_prompts || out.generatedPrompts || out.prompts);
                const imagesData = out && (out.generated_images || out.generatedImages || out.images);

                if (Array.isArray(promptsData)) {
                    setPrompts(promptsData);
                }

                if (Array.isArray(imagesData)) {
                    setImages(imagesData);
                }
            }

            if (j.status === 'RUNNING' || j.status === 'STARTED') {
                setTimeout(pollStatus, 3000);
            }
        } catch (e) {
            setExecStatus('Error polling status: ' + e);
        }
    };

    return (
        <main style={{ padding: '20px' }}>
            <h1>CrewAI: Upload outline & generate lesson</h1>

            {/* Authentication Status */}
            <div style={{ marginBottom: '20px', padding: '10px', backgroundColor: isAuthenticated ? '#d4edda' : '#f8d7da', border: '1px solid', borderColor: isAuthenticated ? '#c3e6cb' : '#f5c6cb', borderRadius: '4px' }}>
                <strong>Authentication Status:</strong> {isAuthenticated ? '✅ Authenticated' : '❌ Not Authenticated'}
                {!isAuthenticated && (
                    <div style={{ marginTop: '10px' }}>
                        <p>You need to be logged in to use this feature. Please go back to the main page and click "🚀 Comenzar Ahora" to authenticate.</p>
                        <button onClick={() => window.location.href = '/'} style={{ padding: '8px 16px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                            Go to Login
                        </button>
                    </div>
                )}
            </div>

            <section>
                <h2>1) Upload outline.yaml</h2>
                <input id="fileInput" type="file" accept=".yaml,.yml" disabled={!isAuthenticated} />
                <button onClick={handleUpload} disabled={!isAuthenticated}>Upload to S3</button>
                <div>{uploadStatus}</div>
            </section>

            <section>
                <h2>2) Generation settings</h2>
                <label>Course bucket: <input value={courseBucket} onChange={e => setCourseBucket(e.target.value)} disabled={!isAuthenticated} /></label>
                <br />
                <label>Project folder: <input value={projectFolder} onChange={e => setProjectFolder(e.target.value)} placeholder="e.g. 250916-kubernetes-for-devops-engineers-05" disabled={!isAuthenticated} /></label>
                <br />
                <label>Module #: <input type="number" value={moduleNum} onChange={e => setModuleNum(parseInt(e.target.value))} disabled={!isAuthenticated} /></label>
                <br />
                <label>Lesson #: <input type="number" value={lessonNum} onChange={e => setLessonNum(parseInt(e.target.value))} disabled={!isAuthenticated} /></label>
                <br />
                <label>Model provider:
                    <select value={modelProvider} onChange={e => setModelProvider(e.target.value)} disabled={!isAuthenticated}>
                        <option value="openai">OpenAI</option>
                        <option value="bedrock">Bedrock</option>
                    </select>
                </label>
                <br />
                <button onClick={handleStart} disabled={!isAuthenticated}>Start generation</button>
                <div>{startStatus}</div>
            </section>

            <section>
                <h2>3) Execution status</h2>
                <div>Execution ARN: <span>{executionArn || '-'}</span></div>
                <div>Status: <span>{execState}</span></div>
                <pre>{execStatus}</pre>
            </section>

            <section>
                <h2>4) Visual prompts</h2>
                <ul>
                    {prompts.map((p, i) => (
                        <li key={i}>{typeof p === 'string' ? p : (p.prompt || p.id || JSON.stringify(p))}</li>
                    ))}
                </ul>
            </section>

            <section>
                <h2>5) Generated images</h2>
                <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                    {images.map((img, i) => {
                        const url = img.s3_key ? `https://s3.amazonaws.com/${courseBucket}/${img.s3_key}` : img.url || null;
                        return (
                            <div key={i} style={{ margin: '6px' }}>
                                {url ? (
                                    <a href={url} target="_blank" rel="noopener noreferrer">
                                        <img src={url} style={{ maxWidth: '300px', display: 'block' }} alt="" />
                                    </a>
                                ) : (
                                    <div>{JSON.stringify(img)}</div>
                                )}
                                <div>{img.filename || img.id || img.s3_key || ''}</div>
                            </div>
                        );
                    })}
                </div>
            </section>
        </main>
    );
}

export default GeneradorCursos;