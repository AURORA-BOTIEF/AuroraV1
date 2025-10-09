// Generador de temarios para KNOWLEDGE TRANSFER (KNTR)
// Prueba David ...

import React, { useState } from 'react';
import EditorDeTemario from './EditorDeTemario'; 
import './GeneradorTemarios.css';

function GeneradorTemarios() {
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const [params, setParams] = useState({
    tecnologia: '',
    tema_curso: '',
    nivel_dificultad: 'basico',
    sector: '',
    enfoque: '',
    horas_por_sesion: 4,
    numero_sesiones_por_semana: 1,
    objetivo_tipo: 'saber_hacer',
    codigo_certificacion: ''
  });

  // API nueva -> Incorpora OpenAi.
  const apiUrl = "https://hknb9c5f8a.execute-api.us-east-1.amazonaws.com/default/tem_knowledge_transfer_openai";

// CÓDIGO CORREGIDO
const handleParamChange = (e) => {
    const { name, value } = e.target;

    // Esta es la clave: si el campo es uno de los sliders, lo convertimos a número.
    let valorFinal = value;
    if (name === 'horas_por_sesion' || name === 'numero_sesiones_por_semana') {
        valorFinal = parseInt(value, 10);
    }
    
    setParams(prev => ({ ...prev, [name]: valorFinal }));
};

  const handleGenerar = async (nuevosParams = params) => {
    if (!nuevosParams.tema_curso || !nuevosParams.tecnologia || !nuevosParams.sector) {
      setError("Por favor, completa Tecnología, Tema del Curso y Sector/Audiencia.");
      return;
    }
    setIsLoading(true);
    setError('');
    setTemarioGenerado(null);

    try {
      const payload = { ...nuevosParams };

      if (payload.objetivo_tipo !== 'certificacion') {
        delete payload.codigo_certificacion;
      }

      const token = localStorage.getItem("id_token");
      const response = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });
      
      const data = await response.json();

      if (!response.ok) {
        const errorMessage = typeof data.error === 'object' ? JSON.stringify(data.error) : data.error;
        throw new Error(errorMessage || "Ocurrió un error en el servidor.");
      }
      
      const temarioCompleto = { ...data, ...nuevosParams };
      setTemarioGenerado(temarioCompleto);
      
    } catch (err) {
      console.error("Error al generar el temario:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (temarioParaGuardar) => {
    console.log("Guardando esta versión del temario:", temarioParaGuardar);
    alert("Funcionalidad de guardado en desarrollo.");
  };

  return (
    <div className="generador-temarios-container">
      <h2>Generador de Temarios a la Medida</h2>
      <p>Introduce los detalles para generar una propuesta de temario con Inteligencia artificial.</p>

      <div className="formulario-inicial">
        <div className="form-grid">
          <div className="form-group">
            <label>Tecnología</label>
            <input name="tecnologia" value={params.tecnologia} onChange={handleParamChange} placeholder="Ej: AWS, React, Python" />
          </div>
          <div className="form-group">
            <label>Tema Principal del Curso</label>
            <input name="tema_curso" value={params.tema_curso} onChange={handleParamChange} placeholder="Ej: Arquitecturas Serverless" />
          </div>
          <div className="form-group">
            <label>Nivel de Dificultad</label>
            <select name="nivel_dificultad" value={params.nivel_dificultad} onChange={handleParamChange}>
              <option value="basico">Básico</option>
              <option value="intermedio">Intermedio</option>
              <option value="avanzado">Avanzado</option>
            </select>
          </div>
          <div className="form-group">
            <label>Número de Sesiones (1-3)</label> 
            <div className='slider-container'>
              <input name="numero_sesiones_por_semana" type="range" min="1" max="3" value={params.numero_sesiones_por_semana} onChange={handleParamChange} />
              <span>{params.numero_sesiones_por_semana} {params.numero_sesiones_por_semana > 1 ? 'sesiones' : 'sesión'}</span>
            </div>
          </div>
          <div className="form-group">
            <label>Horas por Sesión (3-7)</label> 
            <div className='slider-container'>
              <input name="horas_por_sesion" type="range" min="3" max="7" value={params.horas_por_sesion} onChange={handleParamChange} />
              <span>{params.horas_por_sesion} horas</span>
            </div>
          </div>
        </div>
        <div className="form-group">
            <label>Tipo de Objetivo</label>
            <div className="radio-group">
                <label>
                    <input type="radio" name="objetivo_tipo" value="saber_hacer" checked={params.objetivo_tipo === 'saber_hacer'} onChange={handleParamChange} />
                    Saber Hacer (Enfocado en habilidades)
                </label>
                <label>
                    <input type="radio" name="objetivo_tipo" value="certificacion" checked={params.objetivo_tipo === 'certificacion'} onChange={handleParamChange} />
                    Certificación (Enfocado en examen)
                </label>
            </div>
        </div>

        {params.objetivo_tipo === 'certificacion' && (
            <div className="form-group">
                <label>Código de Certificación</label>
                <input name="codigo_certificacion" value={params.codigo_certificacion} onChange={handleParamChange} placeholder="Ej: AWS CLF-C02, AZ-900" />
            </div>
        )}

        <div className="form-group">
          <label>Sector / Audiencia</label>
          <textarea name="sector" value={params.sector} onChange={handleParamChange} placeholder="Ej: Sector financiero, Desarrolladores con 1 año de experiencia..." />
        </div>
        <div className="form-group">
          <label>Enfoque Adicional (Opcional)</label>
          <textarea name="enfoque" value={params.enfoque} onChange={handleParamChange} placeholder="Ej: Orientado a patrones de diseño, con énfasis en casos prácticos" />
        </div>
        
        <button className="btn-generar-principal" onClick={() => handleGenerar(params)} disabled={isLoading}>
          {isLoading ? 'Generando...' : 'Generar Propuesta de Temario'}
        </button>
      </div>

      {error && <div className="error-mensaje">{error}</div>}

      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}
          onRegenerate={handleGenerar}
          onSave={handleSave}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}

export default GeneradorTemarios;