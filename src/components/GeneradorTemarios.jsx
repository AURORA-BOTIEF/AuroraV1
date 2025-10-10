// src/components/GeneradorTemarios.jsx
import React, { useState } from 'react';
import EditorDeTemario from './EditorDeTemario'; 
import './GeneradorTemarios.css';

const asesoresComerciales = [
  "Alejandra Galvez", "Ana Aragón", "Arely Alvarez", "Benjamin Araya",
  "Carolina Aguilar", "Cristian Centeno", "Elizabeth Navia", "Eonice Garfías",
  "Guadalupe Agiz", "Jazmin Soriano", "Lezly Durán", "Lusdey Trujillo",
  "Natalia García", "Natalia Gomez", "Vianey Miranda",
].sort();

function GeneradorTemarios() {
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const [params, setParams] = useState({
    nombre_preventa: '',
    asesor_comercial: '',
    tecnologia: '',
    tema_curso: '',
    nivel_dificultad: 'basico',
    sector: '',
    enfoque: '',
    horas_por_sesion: 7,
    numero_sesiones_por_semana: 1,
    objetivo_tipo: 'saber_hacer',
    codigo_certificacion: ''
  });

  const apiUrl = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

  const handleParamChange = (e) => {
    const { name, value } = e.target;
    let valorFinal = value;
    if (name === 'horas_por_sesion' || name === 'numero_sesiones_por_semana') {
      valorFinal = parseInt(value, 10);
    }
    setParams(prev => ({ ...prev, [name]: valorFinal }));
  };

  const handleGenerar = async (nuevosParams = params) => {
    if (!nuevosParams.nombre_preventa || !nuevosParams.asesor_comercial || 
        !nuevosParams.tema_curso || !nuevosParams.tecnologia || !nuevosParams.sector) {
      setError("Por favor completa todos los campos requeridos: Preventa, Asesor, Tecnología, Tema del Curso y Sector/Audiencia.");
      return;
    }

    setIsLoading(true);
    setError('');
    setTemarioGenerado(null);

    try {
      const payload = { ...nuevosParams };
      if (payload.objetivo_tipo !== 'certificacion') delete payload.codigo_certificacion;

      const token = localStorage.getItem("id_token");
      const response = await fetch("https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/PruebadeTEMAR", {
        method: "POST",
        mode: "cors",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Error al generar el temario.");

      const temarioCompleto = { ...data, ...nuevosParams };
      setTemarioGenerado(temarioCompleto);

    } catch (err) {
      console.error("Error al generar el temario:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // ✅ SOLO ESTA PARTE ESTÁ MEJORADA (todo lo demás es igual que el original)
  const handleSave = async (temarioParaGuardar) => {
    console.log("Guardando esta versión del temario:", temarioParaGuardar);

    try {
      const token = localStorage.getItem("id_token");

      const bodyData = {
        cursoId: temarioParaGuardar.tema_curso || params.tema_curso || "SinNombre",
        contenido: temarioParaGuardar,
        autor: token ? "anette.flores@netec.com.mx" : "Anónimo",
        asesor_comercial: params.asesor_comercial || "No asignado",
        nombre_preventa: params.nombre_preventa || "No especificado",
        nombre_curso: params.tema_curso || "Sin nombre",
        tecnologia: params.tecnologia || "No especificada",
        nota_version: `Guardado el ${new Date().toLocaleString()}`,
        fecha_creacion: new Date().toISOString(),
        s3_path: `s3://temarios/${(params.tema_curso || "SinNombre").replace(/\s+/g, "_")}_${new Date().toISOString()}.json`
      };

      const response = await fetch(apiUrl, {
        method: "POST",
        mode: "cors",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(bodyData)
      });

      const data = await response.json();
      console.log("✅ Respuesta de la API:", data);

      if (!response.ok || !data.success) {
        console.error("❌ Error en la respuesta de la API:", data);
        throw new Error(data.error || "Error al guardar la versión del temario.");
      }

      alert(`✅ Versión guardada correctamente\nVersion ID: ${data.versionId}`);
    } catch (error) {
      console.error("Error al guardar el temario:", error);
      alert("❌ No se pudo guardar el temario. Revisa la consola.");
    }
  };

  const handleListarVersiones = async () => {
    try {
      const token = localStorage.getItem("id_token");
      const response = await fetch(apiUrl, {
        method: "GET",
        mode: "cors",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        }
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Error al obtener versiones.");

      console.log("📦 Versiones guardadas:", data);
      alert(`Se encontraron ${data.length} versiones (ver consola).`);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
      alert("❌ No se pudieron obtener las versiones. Revisa la consola.");
    }
  };

  return (
    <div className="generador-temarios-container">
      <h2>Generador de Temarios a la Medida</h2>
      <p>Introduce los detalles para generar una propuesta de temario con Inteligencia Artificial.</p>

      <div className="formulario-inicial">
        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado</label>
            <input name="nombre_preventa" value={params.nombre_preventa} onChange={handleParamChange} />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial Asociado</label>
            <select name="asesor_comercial" value={params.asesor_comercial} onChange={handleParamChange}>
              <option value="">Selecciona un asesor(a)</option>
              {asesoresComerciales.map(nombre => (
                <option key={nombre} value={nombre}>{nombre}</option>
              ))}
            </select>
          </div>

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
            <label>Número de Sesiones (1-7)</label>
            <div className="slider-container">
              <input name="numero_sesiones_por_semana" type="range" min="1" max="7" value={params.numero_sesiones_por_semana} onChange={handleParamChange} />
              <span>{params.numero_sesiones_por_semana} {params.numero_sesiones_por_semana > 1 ? 'sesiones' : 'sesión'}</span>
            </div>
          </div>

          <div className="form-group">
            <label>Horas por Sesión (4-12)</label>
            <div className="slider-container">
              <input name="horas_por_sesion" type="range" min="4" max="12" value={params.horas_por_sesion} onChange={handleParamChange} />
              <span>{params.horas_por_sesion} horas</span>
            </div>
          </div>
        </div>

        <div className="form-group">
          <label>Sector / Audiencia</label>
          <textarea name="sector" value={params.sector} onChange={handleParamChange} placeholder="Ej: Sector financiero, desarrolladores con 1 año de experiencia..." />
        </div>

        <div className="form-group">
          <label>Enfoque Adicional (Opcional)</label>
          <textarea name="enfoque" value={params.enfoque} onChange={handleParamChange} placeholder="Ej: Orientado a patrones de diseño, con énfasis en casos prácticos" />
        </div>

        <div style={{ display: "flex", gap: "1rem" }}>
          <button className="btn-generar-principal" onClick={() => handleGenerar(params)} disabled={isLoading}>
            {isLoading ? 'Generando...' : 'Generar Propuesta de Temario'}
          </button>

          <button className="btn-generar-principal" style={{ backgroundColor: "#45ab9f" }} onClick={handleListarVersiones}>
            Ver Versiones Guardadas
          </button>
        </div>
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



