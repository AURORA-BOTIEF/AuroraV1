// src/components/GeneradorTemarios_Seminarios.jsx
import React, { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css";

// === URLs de tus APIs ===
const generarApiUrl = "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/temario_seminario";
const guardarApiUrl = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

// === Asesores Comerciales ===
const asesoresComerciales = [
  "Alejandra Galvez", "Ana Aragón", "Arely Alvarez", "Benjamin Araya",
  "Carolina Aguilar", "Cristian Centeno", "Elizabeth Navia", "Eonice Garfías",
  "Guadalupe Agiz", "Jazmin Soriano", "Lezly Durán", "Lusdey Trujillo",
  "Natalia García", "Natalia Gomez", "Vianey Miranda",
].sort();

export default function GeneradorTemarios_Seminarios() {  
  const [form, setForm] = useState({
    nombre_preventa: "",
    asesor_comercial: "",
    tecnologia: "",
    tema_curso: "",
    nivel_dificultad: "basico",
    objetivo_tipo: "saber_hacer",
    codigo_certificacion: "",
    sector: "",
    enfoque: "",
    horas_por_sesion: 2,
  });

  const [userEmail, setUserEmail] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({ curso: "", asesor: "", tecnologia: "" });
  const [menuActivo, setMenuActivo] = useState(null);

  // === Obtener email del usuario autenticado ===
  useEffect(() => {
    const getUser = async () => {
      try {
        const session = await fetchAuthSession();
        const email = session?.tokens?.idToken?.payload?.email;
        setUserEmail(email || "sin-correo");
      } catch (err) {
        console.error("⚠️ Error obteniendo usuario:", err);
      }
    };
    getUser();
  }, []);

  // === Manejo de cambios en el formulario ===
  const handleChange = (e) => {
    const { name, value } = e.target;
    const numeric = name === "horas_por_sesion" ? parseFloat(value) : value;
    setForm((prev) => ({ ...prev, [name]: numeric }));
  };

  // === Validación antes de enviar ===
  const validate = () => {
    const requiredFields = ["nombre_preventa", "asesor_comercial", "tecnologia", "tema_curso", "sector"];
    const missing = requiredFields.filter((f) => !form[f].trim());
    if (missing.length > 0)
      return `Completa los siguientes campos: ${missing.join(", ")}`;
    if (form.objetivo_tipo === "certificacion" && !form.codigo_certificacion.trim())
      return "Debes especificar el código de certificación.";
    return "";
  };

  // === Generar seminario vía Lambda ===
  const handleGenerate = async () => {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const payload = {
        tecnologia: form.tecnologia.trim(),
        tema_curso: form.tema_curso.trim(),
        nivel_dificultad: form.nivel_dificultad,
        objetivo_tipo: form.objetivo_tipo,
        sector: form.sector.trim(),
        enfoque: form.enfoque.trim(),
        duracion_total_horas: form.horas_por_sesion,
        nombre_preventa: form.nombre_preventa.trim(),
        asesor_comercial: form.asesor_comercial.trim(),
      };

      const token = localStorage.getItem("id_token");

      const res = await fetch(generarApiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error al generar el seminario.");

      setTemarioGenerado({
        ...data,
        metadata: {
          nombre_preventa: form.nombre_preventa,
          asesor_comercial: form.asesor_comercial,
          horas_totales: form.horas_por_sesion,
          autor: userEmail,
        },
      });
    } catch (e) {
      console.error("❌ Error:", e);
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  // === Guardar versión en DynamoDB ===
  const handleGuardarVersion = async (temarioParaGuardar, nota) => {
    try {
      const token = localStorage.getItem("id_token");
      const bodyData = {
        cursoId: form.tema_curso.trim().toLowerCase().replace(/\s+/g, "_"), // clave de partición DynamoDB
        contenido: temarioParaGuardar,
        nota_version: nota || `Guardado el ${new Date().toLocaleString()}`,
        autor: userEmail || "Desconocido",
        asesor_comercial: form.asesor_comercial || "No asignado",
        nombre_preventa: form.nombre_preventa || "No especificado",
        nombre_curso: form.tema_curso || "Sin título",
        tecnologia: form.tecnologia || "No especificada",
        enfoque: form.enfoque || "General",
        fecha_creacion: new Date().toISOString(),
        s3_path: "sin_ruta",
      };

      const res = await fetch(guardarApiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(bodyData),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error al guardar versión");

      return { success: true, message: `✔ Versión guardada (ID: ${data.versionId})` };
    } catch (error) {
      console.error(error);
      return { success: false, message: error.message };
    }
  };

  // === Listar versiones desde DynamoDB ===
  const handleListarVersiones = async () => {
    try {
      const token = localStorage.getItem("id_token");
      const res = await fetch(guardarApiUrl, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error al listar versiones.");

      const sorted = data.sort((a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion));
      setVersiones(sorted);
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al listar versiones:", error);
    }
  };

  // === Filtrado de versiones ===
  const handleFiltroChange = (e) => {
    const { name, value } = e.target;
    setFiltros((prev) => ({ ...prev, [name]: value }));
  };

  const limpiarFiltros = () => setFiltros({ curso: "", asesor: "", tecnologia: "" });

  const versionesFiltradas = versiones.filter((v) => {
    const curso = v.nombre_curso?.toLowerCase() || "";
    const asesor = v.asesor_comercial?.toLowerCase() || "";
    const tecnologia = v.tecnologia?.toLowerCase() || "";
    return (
      curso.includes(filtros.curso.toLowerCase()) &&
      (filtros.asesor ? asesor === filtros.asesor.toLowerCase() : true) &&
      tecnologia.includes(filtros.tecnologia.toLowerCase())
    );
  });

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Seminarios Ejecutivos</h2>
        <p>Genera, guarda y gestiona seminarios de hasta 4 horas con IA.</p>

        {/* === FORMULARIO === */}
        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa *</label>
            <input name="nombre_preventa" value={form.nombre_preventa} onChange={handleChange} />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial *</label>
            <select name="asesor_comercial" value={form.asesor_comercial} onChange={handleChange}>
              <option value="">Selecciona un asesor(a)</option>
              {asesoresComerciales.map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Tecnología *</label>
            <input name="tecnologia" value={form.tecnologia} onChange={handleChange} />
          </div>

          <div className="form-group">
            <label>Tema del Seminario *</label>
            <input name="tema_curso" value={form.tema_curso} onChange={handleChange} />
          </div>

          <div className="form-group">
            <label>Nivel *</label>
            <select name="nivel_dificultad" value={form.nivel_dificultad} onChange={handleChange}>
              <option value="basico">Básico</option>
              <option value="intermedio">Intermedio</option>
              <option value="avanzado">Avanzado</option>
            </select>
          </div>

          <div className="form-group">
            <label>Duración (1–4 horas)</label>
            <div className="slider-container">
              <input
                type="range"
                min="1"
                max="4"
                step="0.5"
                name="horas_por_sesion"
                value={form.horas_por_sesion}
                onChange={handleChange}
              />
              <span>{form.horas_por_sesion} h</span>
            </div>
          </div>
        </div>

        {/* === Tipo de objetivo === */}
        <div className="form-group-radio">
          <label>Tipo de Objetivo *</label>          
          <div>
            <label>
              <input
                type="radio"
                name="objetivo_tipo"
                value="saber_hacer"
                checked={form.objetivo_tipo === "saber_hacer"}
                onChange={handleChange}
              />
              Saber Hacer
            </label>
            <label>
              <input
                type="radio"
                name="objetivo_tipo"
                value="certificacion"
                checked={form.objetivo_tipo === "certificacion"}
                onChange={handleChange}
              />
              Certificación
            </label>
          </div>
        </div>        

        {form.objetivo_tipo === "certificacion" && (
          <div className="form-group">
            <label>Código de Certificación *</label>
            <input name="codigo_certificacion" value={form.codigo_certificacion} onChange={handleChange} />
          </div>
        )}      

        <div className="form-group">
          <label>Sector / Audiencia *</label>
          <textarea name="sector" value={form.sector} onChange={handleChange} rows="2" />
        </div>

        <div className="form-group">
          <label>Enfoque (opcional)</label>
          <textarea name="enfoque" value={form.enfoque} onChange={handleChange} rows="2" />
        </div>

        {/* === BOTONES === */}
        <div className="botones">
          <button className="btn-generar" onClick={handleGenerate} disabled={isLoading}>
            {isLoading ? "Generando..." : "Generar Seminario"}
          </button>
          <button className="btn-versiones" onClick={handleListarVersiones} disabled={isLoading}>
            Ver Versiones Guardadas
          </button>
        </div>

        {error && <p className="error-message">⚠️ {error}</p>}
      </div>

      {/* === RESULTADO === */}
      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}          
          onSave={handleGuardarVersion}
          onRegenerate={handleGenerate}        
          isLoading={isLoading}
        />
      )}

      {/* === MODAL VERSIONES === */}
      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setMostrarModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="filtros-versiones">
                <input type="text" name="curso" placeholder="Curso" value={filtros.curso} onChange={handleFiltroChange} />
                <select name="asesor" value={filtros.asesor} onChange={handleFiltroChange}>
                  <option value="">Todos los asesores</option>
                  {asesoresComerciales.map((a) => <option key={a}>{a}</option>)}
                </select>
                <input
                  type="text"
                  name="tecnologia"
                  placeholder="Tecnología"
                  value={filtros.tecnologia}
                  onChange={handleFiltroChange}
                />
                <button className="btn-secundario" onClick={limpiarFiltros}>Limpiar</button>
              </div>

              {versionesFiltradas.length === 0 ? (
                <p className="no-versiones">No hay versiones guardadas.</p>
              ) : (
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
                    {versionesFiltradas.map((v, i) => (
                      <tr key={v.versionId || i}>
                        <td>{v.nombre_curso}</td>
                        <td>{v.tecnologia}</td>
                        <td>{v.asesor_comercial}</td>
                        <td>{new Date(v.fecha_creacion).toLocaleString()}</td>
                        <td>{v.autor}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
