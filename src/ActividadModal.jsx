import './ActividadModal.css';
import { useState } from 'react';

function ActividadModal({ visible, onClose, token }) {
  const [tema, setTema] = useState('');
  const [modulo, setModulo] = useState('');
  const [tipo, setTipo] = useState('fill');
  const [resultado, setResultado] = useState('');

  if (!visible) return null;

  const generarActividad = async () => {
    setResultado("⏳ Generando actividad...");
    try {
      const res = await fetch("https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/generarActividad", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": token
        },
        body: JSON.stringify({ tema, modulo, tipo })
      });
      const data = await res.json();
      if (!data.preguntas) throw new Error("Sin preguntas generadas.");
      const html = data.preguntas.map(p => `<div class="actividad-item">${p.texto}</div>`).join('');
      setResultado(html);
    } catch (err) {
      setResultado("❌ Error: " + err.message);
    }
  };

  return (
    <div className="modal-actividad-backdrop">
      <div className="modal-actividad">
        <header>
          <h2>🎯 Generador de Actividades</h2>
          <button className="cerrar" onClick={onClose}>✖</button>
        </header>

        <div className="formulario">
          <input value={tema} onChange={e => setTema(e.target.value)} placeholder="Tema (ej. arquitectura)" />
          <input value={modulo} onChange={e => setModulo(e.target.value)} placeholder="Archivo .txt (ej. modulo1.txt)" />
          <select value={tipo} onChange={e => setTipo(e.target.value)}>
            <option value="fill">Frases con espacios en blanco</option>
            <option value="quiz">Opción múltiple</option>
          </select>
          <button onClick={generarActividad}>Generar</button>
        </div>

        <div className="resultado" dangerouslySetInnerHTML={{ __html: resultado }} />
      </div>
    </div>
  );
}

export default ActividadModal;
