// Examen.jsx
import React, { useState } from 'react';
import './Examen.css';

function Examen() {
  const [curso, setCurso] = useState('Python');
  const [topico, setTopico] = useState('');
  const [examen, setExamen] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleGenerarExamen = async () => {
    if (!topico.trim()) {
      setError('Por favor ingresa un tópico válido.');
      return;
    }

    setLoading(true);
    setError('');
    setExamen(null);

    try {
      const response = await fetch('https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/examen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ curso, topico })
      });

      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }

      setExamen(data);
    } catch (err) {
      setError('Error al generar el examen: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="examen-container">
      <h1 className="titulo-examen">🧪 Generador de Exámenes</h1>
      <p className="descripcion-examen">Selecciona el curso y un tema para generar preguntas de práctica.</p>

      <div className="formulario-examen">
        <select value={curso} onChange={(e) => setCurso(e.target.value)} className="dropdown-curso">
          <option value="Python">Python</option>
          <option value="AWS">AWS</option>
          <option value="Azure">Azure</option>
          <option value="IA">IA</option>
        </select>

        <input
          type="text"
          placeholder="Tópico (ej: IAM, funciones Lambda...)"
          value={topico}
          onChange={(e) => setTopico(e.target.value)}
          className="input-topico"
        />

        <button className="btn-generar" onClick={handleGenerarExamen} disabled={loading}>
          {loading ? 'Generando...' : 'Generar examen'}
        </button>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {examen && (
        <div className="examen-preview">
          <h2>📝 {examen.tema}</h2>
          <h4>📌 Tipos de respuesta</h4>
          <ul>
            <li>✔️ Opción múltiple: una respuesta correcta y tres distractores.</li>
            <li>✔️ Respuesta múltiple: dos o más respuestas correctas entre varias opciones.</li>
          </ul>

          {examen.preguntas?.map((p, idx) => (
            <div key={idx} className="pregunta">
              <h3>{idx + 1}. {p.enunciado}</h3>
              <ul className="opciones">
                {Object.entries(p.opciones).map(([letra, texto]) => (
                  <li key={letra}><strong>{letra}:</strong> {texto}</li>
                ))}
              </ul>
              <p><strong>✅ Respuesta correcta:</strong> {p.respuestaCorrecta}</p>
              <p><em>🧠 Justificación:</em> {p.justificacion}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Examen;
