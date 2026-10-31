// src/components/SetupGuidePage.jsx
// Genera y descarga la Setup Guide consolidada (SUG) de un curso.
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './SetupGuidePage.css';
import { API_BASE } from '../utils/apiConfig';

function SetupGuidePage() {
    const navigate = useNavigate();
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [generating, setGenerating] = useState(null);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        const controller = new AbortController();
        const timer = setTimeout(() => loadProjects(searchTerm, controller.signal), searchTerm ? 300 : 0);
        return () => {
            clearTimeout(timer);
            controller.abort();
        };
    }, [searchTerm]);

    const loadProjects = async (search = '', signal) => {
        try {
            setLoading(true);
            let url = `${API_BASE}/list-projects?page=1&limit=50`;
            if (search) url += `&search=${encodeURIComponent(search)}`;
            const response = await fetch(url, { method: 'GET', headers: { 'Content-Type': 'application/json' }, signal });
            if (!response.ok) throw new Error(`No se pudieron cargar los proyectos (${response.status})`);
            const data = await response.json();
            setProjects(data.projects || []);
        } catch (err) {
            if (err.name === 'AbortError') return;
            console.error('Error loading projects:', err);
            setError(err.message);
        } finally {
            if (!signal?.aborted) setLoading(false);
        }
    };

    const generateSetupGuide = async (projectFolder) => {
        setGenerating(projectFolder);
        setResult(null);
        setError('');
        try {
            const response = await fetch(`${API_BASE}/generate-setup-guide`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_folder: projectFolder }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`);
            setResult({ ...data, project_folder: projectFolder });
        } catch (err) {
            console.error('Error generating setup guide:', err);
            setError(err.message);
        } finally {
            setGenerating(null);
        }
    };

    return (
        <div className="setup-guide-page">
            <div className="sg-header">
                <button className="sg-back" onClick={() => navigate('/generador-contenidos')}>← Menú</button>
                <div>
                    <h1>Setup Guide</h1>
                    <p>Documento maestro del curso: prerrequisitos, infraestructura, software, configuración, accesos, validaciones y matriz de prácticas.</p>
                </div>
            </div>

            <input
                type="text"
                className="sg-search"
                placeholder="Buscar curso por nombre o carpeta..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
            />

            {error && <div className="sg-error">{error}</div>}
            {result && (
                <div className="sg-result">
                    <strong>Setup Guide generada:</strong> {result.course_title} ({result.course_key} · {result.version})
                    <br />
                    Laboratorios: {result.lab_count} · Componentes de software: {result.software_count} · Marcadores pendientes: {result.placeholders_count}
                    <div className="sg-result-actions">
                        {result.download_url && (
                            <a href={result.download_url} target="_blank" rel="noopener noreferrer">Descargar PDF</a>
                        )}
                    </div>
                </div>
            )}

            {loading ? (
                <p className="sg-muted">Cargando proyectos…</p>
            ) : (
                <div className="sg-grid">
                    {projects.map((project) => (
                        <div className="sg-card" key={project.folder || project.name}>
                            <h3>{project.name || project.folder}</h3>
                            <p className="sg-folder">{project.folder}</p>
                            <button
                                className="sg-generate"
                                disabled={generating === project.folder}
                                onClick={() => generateSetupGuide(project.folder)}
                            >
                                {generating === project.folder ? 'Generando…' : 'Generar Setup Guide'}
                            </button>
                        </div>
                    ))}
                    {projects.length === 0 && <p className="sg-muted">No se encontraron proyectos.</p>}
                </div>
            )}
        </div>
    );
}

export default SetupGuidePage;
