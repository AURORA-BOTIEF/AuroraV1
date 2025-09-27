// Configuration - runtime config is loaded into window.__FRONTEND_CONFIG by index.html
const cfg = window.__FRONTEND_CONFIG || {};
const PRESIGN_ENDPOINT = cfg.presignEndpoint || '/presign';
const START_JOB_ENDPOINT = cfg.startJobEndpoint || '/start-job';
const EXEC_STATUS_ENDPOINT = cfg.execStatusEndpoint || '/exec-status';

const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadStatus = document.getElementById('uploadStatus');
const startBtn = document.getElementById('startBtn');
const startStatus = document.getElementById('startStatus');
const execStatus = document.getElementById('execStatus');
const modelProviderSelect = document.getElementById('modelProvider');
const execArnEl = document.getElementById('execArn');
const execStateEl = document.getElementById('execState');
const promptsList = document.getElementById('promptsList');
const imagesContainer = document.getElementById('imagesContainer');

let uploadedKey = null;
let executionArn = null;

uploadBtn.onclick = async () => {
    const f = fileInput.files[0];
    if (!f) return alert('Choose a file first');
    uploadStatus.textContent = 'Requesting presigned URL...';

    // Request presigned URL from backend
    try {
        console.log('Presign endpoint:', PRESIGN_ENDPOINT);
        const resp = await fetch(PRESIGN_ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: f.name }) });
        if (!resp.ok) {
            const txt = await resp.text().catch(() => '');
            console.error('Presign failed', resp.status, txt);
            return uploadStatus.textContent = `Failed to get presign URL (${resp.status})`;
        }
        const data = await resp.json();
        const key = data.key;
        // Support both `put_url` (this project) and older `url` field names
        const put_url = data.put_url || data.url;
        const post = data.post;
        uploadStatus.textContent = 'Uploading...';

        // If presign returned a POST form, use that (more robust for browsers)
        if (post && post.url && post.fields) {
            const form = new FormData();
            Object.entries(post.fields).forEach(([k, v]) => form.append(k, v));
            form.append('file', f);
            const putResp = await fetch(post.url, { method: 'POST', body: form });
            if (!putResp.ok) {
                const txt = await putResp.text().catch(() => '');
                console.error('S3 POST failed', putResp.status, txt);
                return uploadStatus.textContent = 'Upload failed (POST)';
            }
        } else if (put_url) {
            // Otherwise fall back to simple PUT to the presigned URL
            const putResp = await fetch(put_url, { method: 'PUT', headers: { 'Content-Type': 'application/x-yaml' }, body: f });
            if (!putResp.ok) {
                const txt = await putResp.text().catch(() => '');
                console.error('S3 PUT failed', putResp.status, txt);
                return uploadStatus.textContent = 'Upload failed (PUT)';
            }
        } else {
            console.error('Presign returned unexpected payload', data);
            return uploadStatus.textContent = 'Presign returned no upload info';
        }

        uploadedKey = key;
        uploadStatus.textContent = 'Uploaded: ' + key;
    } catch (e) {
        console.error('Presign/upload error', e);
        uploadStatus.textContent = 'Error during upload: ' + e;
    }
};

startBtn.onclick = async () => {
    const course_bucket = document.getElementById('courseBucket').value;
    const project_folder = document.getElementById('projectFolder').value;
    const module_to_generate = parseInt(document.getElementById('moduleNum').value, 10);
    const lesson_to_generate = parseInt(document.getElementById('lessonNum').value, 10);
    const max_images = parseInt(document.getElementById('maxImages').value, 10) || 0;
    if (!uploadedKey) return alert('Please upload an outline first');
    startStatus.textContent = 'Starting execution...';
    const model_provider = (modelProviderSelect && modelProviderSelect.value) || 'openai';
    const body = { course_bucket, outline_s3_key: uploadedKey, project_folder, module_to_generate, lesson_to_generate, model_provider, max_images };
    const resp = await fetch(START_JOB_ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!resp.ok) {
        startStatus.textContent = 'Failed to start execution';
        return;
    }
    const data = await resp.json();
    executionArn = data.executionArn || data.executionArn;
    execArnEl.textContent = executionArn || '-';
    startStatus.textContent = 'Execution started';
    execStateEl.textContent = 'STARTED';
    execStatus.textContent = 'Polling for status...';
    promptsList.innerHTML = '';
    imagesContainer.innerHTML = '';
    pollStatus();
};

async function pollStatus() {
    if (!executionArn) return;
    try {
        const resp = await fetch(EXEC_STATUS_ENDPOINT + '?arn=' + encodeURIComponent(executionArn));
        if (!resp.ok) throw new Error('status failed');
        const j = await resp.json();
        // Update state display
        execStateEl.textContent = j.status || '-';
        // Show basic status info
        execStatus.textContent = JSON.stringify(j, null, 2);

        // If the state machine finished and returned output, try to parse generated prompts/images
        if (j.status === 'SUCCEEDED' && j.output) {
            // j.output might be an object or a JSON string depending on backend
            let out = j.output;
            if (typeof out === 'string') {
                try { out = JSON.parse(out); } catch (e) { /* leave as-is */ }
            }
            // Drill into AWS Lambda proxy payload shapes if present
            if (out && out.Payload) out = out.Payload;

            // Look for generated_prompts (from visual planner) or generated_images (from images lambda)
            const prompts = out && (out.generated_prompts || out.generatedPrompts || out.prompts || out.generated_prompts);
            const images = out && (out.generated_images || out.generatedImages || out.images || out.generated_images);

            if (Array.isArray(prompts)) {
                promptsList.innerHTML = '';
                prompts.forEach(p => {
                    const li = document.createElement('li');
                    const text = (typeof p === 'string') ? p : (p.prompt || p.id || JSON.stringify(p));
                    li.textContent = text;
                    promptsList.appendChild(li);
                });
            }

            if (Array.isArray(images)) {
                imagesContainer.innerHTML = '';
                images.forEach(img => {
                    const url = img.s3_key ? ('https://s3.amazonaws.com/' + (document.getElementById('courseBucket').value || '') + '/' + img.s3_key) : img.url || null;
                    const wrap = document.createElement('div');
                    wrap.style.margin = '6px';
                    if (url) {
                        const a = document.createElement('a');
                        a.href = url;
                        a.target = '_blank';
                        const im = document.createElement('img');
                        im.src = url;
                        im.style.maxWidth = '300px';
                        im.style.display = 'block';
                        a.appendChild(im);
                        wrap.appendChild(a);
                        const caption = document.createElement('div');
                        caption.textContent = img.filename || img.id || img.s3_key || '';
                        wrap.appendChild(caption);
                    } else {
                        wrap.textContent = JSON.stringify(img);
                    }
                    imagesContainer.appendChild(wrap);
                });
            }
        }

        // Keep polling while running
        if (j.status === 'RUNNING' || j.status === 'STARTED') {
            setTimeout(pollStatus, 3000);
        }
    } catch (e) {
        execStatus.textContent = 'Error polling status: ' + e;
    }
}
