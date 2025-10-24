// src/components/GeneradorTemarios_KNTR.jsx
import React, { useState } from "react";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css";

const API_URL_KNTR =
  "https://icskzsda7d.execute-api.us-east-1.amazonaws.com/default/Generador_Temario_Knowledge_Transfer";

const asesoresComerciales = [
  "Alejandra Galvez", "Ana Aragón", "Arely Alvarez", "Benjamin Araya",
  "Carolina Aguilar", "Cristian Centeno", "Elizabeth Navia", "Eonice Garfías",
  "Guadalupe Agiz", "Jazmin Soriano", "Lezly Durán", "Lusdey Trujillo",
  "Natalia García", "Natalia Gomez", "Vianey Miranda",
].sort();

function GeneradorTemarios_KNTR() {
  // Formulario
  const [form, setForm] = useState({
    nombre_preventa: "",
    asesor_comercial: "",
    tecnologia: "",
    tema_curso: "",
    nivel_dificultad: "basico",
    objetivo_tipo: "saber_hacer",
    codigo_certificacion: "",
    sector: "",
    enfoque: "teórico",
    horas_por_sesion: 3,
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [versiones, setVersiones] = useState([]);

  // Control de cambios
  const handleChange = (e) => {
    const { name, value } = e.target;
    const numeric = name === "horas_por_sesion" ? parseFloat(value) : value;
    setForm((prev) => ({ ...prev, [name]: numeric }));
  };

  // Validación
  const validate = () => {
    if (
      !form.nombre_preventa.trim() ||
      !form.asesor_comercial.trim() ||
      !form.tema_curso.trim() ||
      !form.tecnologia.trim() ||
      !form.sector.trim()
    ) {
      return "Completa todos los campos obligatorios.";
    }
    return "";
  };

  // Payload para Lambda
  const buildPayload = () => {
    const payload = {
      tecnologia: form.tecnologia.trim(),
      tema_curso: form.tema_curso.trim(),
      nivel_dificultad: form.nivel_dificultad,
      objetivo_tipo: form.objetivo_tipo,
      sector: form.sector.trim(),
      enfoque: "teórico",
      durationHours: form.horas_por_sesion,
      nombre_preventa: form.nombre_preventa,
      asesor_comercial: form.asesor_comercial,
      rules: {
        outlineUnits: "topics_and_subtopics_only",
        requireDepth: form.nivel_dificultad,
        fitTimeWithinMinutesTolerance: 5,
        concludeOnTimeSufficiency: true,
      },
    };

    if (form.objetivo_tipo === "certificacion" && form.codigo_certificacion) {
      payload.codigo_certificacion = form.codigo_certificacion.trim();
    }

    return payload;
  };

  // Adaptar respuesta → EditorDeTemario
  const toEditorSchema = (data) => {
    const temarioCapitulos = (data?.outline || []).map((it) => ({
      capitulo: it.topic,
      subcapitulos: Array.isArray(it.subtopics) ? it.subtopics : [],
    }));

    const descripcion =
      data?.notes ||
      (data?.assessment?.reason
        ? `Nivel sugerido: ${data.depth || form.nivel_dificultad}. ${data.assessment.reason}`
        : `Knowledge transfer de ${form.horas_por_sesion} horas. Nivel ${form.nivel_dificultad}.`);

    return {
      nombre_curso: `Knowledge transfer: ${form.tema_curso}`,
      descripcion_general: descripcion,
      audiencia: form.sector,
      prerrequisitos: [],
      objetivos: [],
      nivel_dificultad: form.nivel_dificultad,
      numero_sesiones: 1,
      temario: temarioCapitulos,
    };
  };

  // Enviar datos → API Gateway → Lambda
  const handleGenerate = async () => {
    const v = validate();
    if (v) {
      setError(v);
      return;
    }

    setIsLoading(true);
    setError("");
    setTemarioGenerado(null);

    try {
      const payload = buildPayload();
      const token = localStorage.getItem("id_token");

      const res = await fetch(API_URL_KNTR, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Error al generar el temario.");

      const editorObj = toEditorSchema(data);
      setTemarioGenerado(editorObj);
    } catch (e) {
      console.error("Error al generar knowledge transfer:", e);
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Guardar versiones (placeholder)
  const handleGuardarVersion = async (temarioParaGuardar) => {
    console.log("Guardar versión (simulado):", temarioParaGuardar);
    alert("Funcionalidad de guardado en desarrollo.");
  };

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Temarios - Knowledge transfer</h2>
        <p>Genera una propuesta de knowledge transfer con inteligencia artificial.</p>

        {/* Campos principales */}
        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado *</label>
            <input
              name="nombre_preventa"
              value={form.nombre_preventa}
              onChange={handleChange}
              placeholder="Ej: Juan Pérez"
            />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial Asociado *</label>
            <select
              name="asesor_comercial"
              value={form.asesor_comercial}
              onChange={handleChange}
            >
              <option value="">Selecciona un asesor(a)</option>
              {asesoresComerciales.map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Tecnología *</label>
            <input
              name="tecnologia"
              value={form.tecnologia}
              onChange={handleChange}
              placeholder="Ej: Power BI, AWS, Python"
            />
          </div>

          <div className="form-group">
            <label>Tema principal del knowledge transfer *</label>
            <input
              name="tema_curso"
              value={form.tema_curso}
              onChange={handleChange}
              placeholder="Ej: Arquitecturas Serverless, Storytelling con Datos"
            />
          </div>

          <div className="form-group">
            <label>Nivel *</label>
            <select
              name="nivel_dificultad"
              value={form.nivel_dificultad}
              onChange={handleChange}
            >
              <option value="basico">Básico</option>
              <option value="intermedio">Intermedio</option>
              <option value="avanzado">Avanzado</option>
            </select>
          </div>

          <div className="form-group">
            <label>Duración por sesión del knowledge transfer (1–7 horas) *</label>
            <div className="slider-container">
              <input
                type="range"
                min="1"
                max="7"
                step="0.5"
                name="horas_por_sesion"
                value={form.horas_por_sesion}
                onChange={handleChange}
              />
              <span>{form.horas_por_sesion} h</span>
            </div>
          </div>
        </div>

        {/* Tipo de Objetivo */}
        <div className="form-group-radio">
          <label>Tipo de Objetivo *</label>
          <p></p>
          <div>
            <label>
              <input
                type="radio"
                name="objetivo_tipo"
                value="saber_hacer"
                checked={form.objetivo_tipo === "saber_hacer"}
                onChange={handleChange}
              />{" "}
              Saber Hacer (enfocado en habilidades)
            </label>
            <label>
              <input
                type="radio"
                name="objetivo_tipo"
                value="certificacion"
                checked={form.objetivo_tipo === "certificacion"}
                onChange={handleChange}
              />{" "}
              Certificación (enfocado en examen)
            </label>
          </div>
        </div>
        <p></p>

        {form.objetivo_tipo === "certificacion" && (
          <div className="form-group">
            <label>Código de Certificación</label>
            <input
              name="codigo_certificacion"
              value={form.codigo_certificacion}
              onChange={handleChange}
              placeholder="Ej: AZ-900, AWS CLF-C02"
            />
          </div>
        )}
        <p></p>

        <div className="form-group">
          <label>Sector / Audiencia *</label>
          <textarea
            name="sector"
            value={form.sector}
            onChange={handleChange}
            placeholder="Ej: Sector financiero, docentes universitarios..."
          />
        </div>

        <div className="form-group">
          <label>Enfoque Adicional (opcional)</label>
          <textarea
            name="enfoque"
            value={form.enfoque}
            onChange={handleChange}
            placeholder="Ej: Orientado a casos prácticos o talleres participativos."
          />
        </div>

        {/* Botones */}
        <div className="botones">
          <button
            className="btn-generar"
            onClick={handleGenerate}
            disabled={isLoading}
          >
            {isLoading ? "Generando..." : "Generar Propuesta de knowledge transfer"}
          </button>
          <button
            className="btn-versiones"
            onClick={handleListarVersiones}
          >
            Ver Versiones Guardadas
          </button>
        </div>

        {error && <p className="error">{error}</p>}
      </div>

      {/* Resultado */}
      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}
          onRegenerate={handleGenerate}
          onSave={handleGuardarVersion}
          isLoading={isLoading}
        />
      )}

      {/* Modal de versiones */}
      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="close-btn" onClick={() => setMostrarModal(false)}>
                ✕
              </button>
            </div>
            <table className="tabla-versiones">
              <thead>
                <tr>
                  <th>Curso</th>
                  <th>Tecnología</th>
                  <th>Asesor</th>
                  <th>Fecha</th>
                  <th>Autor</th>
                </tr>
              </thead>
              <tbody>
                {versiones.map((v, i) => (
                  <tr key={i}>
                    <td>{v.nombre_curso}</td>
                    <td>{v.tecnologia}</td>
                    <td>{v.asesor_comercial}</td>
                    <td>{new Date(v.fecha_creacion).toLocaleString()}</td>
                    <td>{v.autor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default GeneradorTemarios_KNTR;