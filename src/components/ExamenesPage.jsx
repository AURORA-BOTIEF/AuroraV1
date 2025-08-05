import React, { useState } from "react";
import "./ExamenesPage.css";

function ExamenesPage() {
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("REEMPLAZA_CON_ID_AWS");
  const [topico, setTopico] = useState("modulo 1");
  const [examen, setExamen] = useState(null);
  const [error, setError] = useState("");

  const handleGenerarExamen = async () => {
    setError("");
    setExamen(null);

    const token = localStorage.getItem("id_token");
    if (!token) {
      setError("No se encontró el token de autenticación.");
      return;
    }

    try {
      const response = await fetch("https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/generar-examen", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": token,
        },
        body: JSON.stringify({ knowledgeBaseId, topico }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Error ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      const parsed = JSON.parse(data.body);
      setExamen(parsed);
    } catch (err) {
      console.error("Error al generar el examen:", err);
      setError("Error al generar el examen: " + err.message);
    }
  };

  return (
    <div className="examenes-container">
      <h2>🧪 Generador de Exámenes</h2>
      <p>Selecciona el curso y un tema para generar preguntas de práctica.</p>

      <select value={knowledgeBaseId} onChange={(e) => setKnowledgeBaseId(e.target.value)}>
        <option value="REEMPLAZA_CON_ID_AWS">AWS</option>
        <option value="REEMPLAZA_CON_ID_AZURE">Azure</option>
      </select>

      <input
        type="text"
        value={topico}
        onChange={(e) => setTopico(e.target.value)}
        placeholder="Ingresa el módulo o tema"
      />

      <button onClick={handleGenerarExamen}>Generar examen</button>

      {error && <p className="error">{error}</p>}

      {examen && (
        <div className="resultado">
          <h3>Tema: {examen.tema}</h3>
          {examen.preguntas.map((pregunta, index) => (
            <div key={index}>
              <p><strong>{pregunta.enunciado}</strong></p>
              <ul>
                {Object.entries(pregunta.opciones).map(([key, value]) => (
                  <li key={key}><strong>{key}:</strong> {value}</li>
                ))}
              </ul>
              <p><strong>Respuestas correctas:</strong> {pregunta.respuestasCorrectas.join(", ")}</p>
              <p><strong>Justificación:</strong> {pregunta.justificacion}</p>
              <hr />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ExamenesPage;
