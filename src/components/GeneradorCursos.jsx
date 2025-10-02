// src/components/GeneradorCursos.jsx
import React, { useState, useEffect } from 'react';
import { Auth } from 'aws-amplify';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { Upload } from '@aws-sdk/lib-storage';

const API_BASE = 'https://z7z5albge3.execute-api.us-east-1.amazonaws.com/Prod';
const PRESIGN_ENDPOINT = `${API_BASE}/presign`;
const START_JOB_ENDPOINT = `${API_BASE}/start-job`;
const EXEC_STATUS_ENDPOINT = `${API_BASE}/exec-status`;

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
    const [maxImages, setMaxImages] = useState(3);
    const [modelProvider, setModelProvider] = useState('openai');

    useEffect(() => {
        if (executionArn && (execState === 'RUNNING' || execState === 'STARTED')) {
            const timer = setTimeout(pollStatus, 3000);
            return () => clearTimeout(timer);
        }
    }, [executionArn, execState]);

    const handleUpload = async () => {
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
        if (!uploadedKey) return alert('Please upload an outline first');
        setStartStatus('Starting execution...');
        const body = {
            course_bucket: courseBucket,
            outline_s3_key: uploadedKey,
            project_folder: projectFolder,
            module_to_generate: moduleNum,
            lesson_to_generate: lessonNum,
            model_provider: modelProvider,
            max_images: maxImages
        };
        try {
            const resp = await fetch(START_JOB_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (!resp.ok) {
                setStartStatus('Failed to start execution');
                return;
            }
            const data = await resp.json();
            const arn = data.executionArn;
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
        if (!executionArn) return;
        try {
            const resp = await fetch(EXEC_STATUS_ENDPOINT + '?arn=' + encodeURIComponent(executionArn));
            if (!resp.ok) throw new Error('status failed');
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

            <section>
                <h2>1) Upload outline.yaml</h2>
                <input id="fileInput" type="file" accept=".yaml,.yml" />
                <button onClick={handleUpload}>Upload to S3</button>
                <div>{uploadStatus}</div>
            </section>

            <section>
                <h2>2) Generation settings</h2>
                <label>Course bucket: <input value={courseBucket} onChange={e => setCourseBucket(e.target.value)} /></label>
                <br />
                <label>Project folder: <input value={projectFolder} onChange={e => setProjectFolder(e.target.value)} placeholder="e.g. 250916-kubernetes-for-devops-engineers-05" /></label>
                <br />
                <label>Module #: <input type="number" value={moduleNum} onChange={e => setModuleNum(parseInt(e.target.value))} /></label>
                <br />
                <label>Lesson #: <input type="number" value={lessonNum} onChange={e => setLessonNum(parseInt(e.target.value))} /></label>
                <br />
                <label>Max images: <input type="number" value={maxImages} onChange={e => setMaxImages(parseInt(e.target.value))} min="0" max="50" /></label>
                <br />
                <label>Model provider:
                    <select value={modelProvider} onChange={e => setModelProvider(e.target.value)}>
                        <option value="openai">OpenAI</option>
                        <option value="bedrock">Bedrock</option>
                    </select>
                </label>
                <br />
                <button onClick={handleStart}>Start generation</button>
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