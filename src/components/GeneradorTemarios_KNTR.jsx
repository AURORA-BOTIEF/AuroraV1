import React, { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css"; 
import { exportarPDF } from "./EditorDeTemario";

const asesoresComerciales = [
  "Alejandra Gálvez", "Ana Aragón", "Arely Álvarez", "Carolina Aguilar",
  "Christian Centeno", "Elizabeth Navia", "Eonice Garfias", "Gabriela Zumarán",
  "Gamaliel Hernández", "Guadalupe Agiz", "Ingrid Monroy", "Javier Unciti",
  "Jazmin Soriano", "Kelly Morales", "Lesly Vargas", "Lezly Durán",
  "Lourdes Iglesias", "Lusdey Trujillo", "Macarena Faúndez", "Mariana Rivera",
  "Mateo Zamora", "Natalia Gómez", "Nicolle Chaucanez", "Santiago Cueva",
  "Valeria Velásquez", "Vianey Miranda"
].sort();

function GeneradorTemarios_KNTR() {
  const [params, setParams] = useState({
    nombre_preventa: "",
    asesor_comercial: "",
    tecnologia: "",
    tema_curso: "",
    nivel_dificultad: "basico",
    numero_sesiones_por_semana: 1,
    horas_por_sesion: 4,
    sector: "",
    enfoque: "teorico",
    codigo_certificacion: "",
    syllabus_text: "",
  });

  const [userEmail, setUserEmail] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mostrandoModalThor, setMostrandoModalThor] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({ curso: "", asesor: "", tecnologia: "" });
  const [menuActivo, setMenuActivo] = useState(null);

  // === API ===
  const generarApiUrl = "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/Generador_Temario_Knowledge_Transfer";
  const guardarApiUrl = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

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

  const handleParamChange = (e) => {
    const { name, value } = e.target;

    if (name === "horas_por_sesion" || name === "numero_sesiones_por_semana") {
      setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
      return;
    }

    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
  };

  const handleGenerar = async () => {
    if (!params.tecnologia || !params.tema_curso || !params.sector) {
      setError("Completa todos los campos requeridos: Tecnología, Tema del Curso y Sector/Audiencia.");
      return;
    }

    const horasTotales = params.horas_por_sesion * params.numero_sesiones_por_semana;

    setIsLoading(true);
    setError("");
    setMostrandoModalThor(true);
    setTimeout(() => setMostrandoModalThor(false), 160000);

    try {
      const payload = { ...params, horas_totales: horasTotales };

      const token = localStorage.getItem("id_token");
      const response = await fetch(generarApiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        const errorMessage = typeof data.error === "object" ? JSON.stringify(data.error) : data.error;
        throw new Error(errorMessage || "Ocurrió un error en el servidor.");
      }

      const temarioCompleto = {
        ...data,
        nombre_preventa: params.nombre_preventa,
        asesor_comercial: params.asesor_comercial,
        horas_totales: horasTotales,
        enfoque: params.enfoque,
        tecnologia: params.tecnologia,
        tema_curso: params.tema_curso,
      };
      setTemarioGenerado(temarioCompleto);
    } catch (err) {
      console.error("❌ Error:", err);
      setError(err.message || "No se pudo generar el temario. Intenta nuevamente.");
    } finally {
      setIsLoading(false);
      setMostrandoModalThor(false);
    }
  };

  const handleGuardarVersion = async (temarioParaGuardar, nota) => {
    try {
      const token = localStorage.getItem("id_token");
      const bodyData = {
        contenido: temarioParaGuardar,
        nota: nota || `Guardado el ${new Date().toLocaleString()}`,
        autor: userEmail,
        asesor_comercial: params.asesor_comercial,
        nombre_preventa: params.nombre_preventa,
        nombre_curso: params.tema_curso,
        tecnologia: params.tecnologia,
        enfoque: params.enfoque,
        fecha_creacion: new Date().toISOString(),
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

      return { success: true, message: `Versión guardada ✔ (versionId: ${data.versionId})` };
    } catch (error) {
      console.error(error);
      return { success: false, message: error.message };
    }
  };

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
      const sortedData = data.sort((a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion));
      setVersiones(sortedData);
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
    }
  };

  const handleCargarVersion = (version) => {
    setMostrarModal(false);
    setParams((prev) => ({
      ...prev,
      nombre_preventa: version.nombre_preventa || "",
      asesor_comercial: version.asesor_comercial || "",
      tecnologia: version.tecnologia || "",
      tema_curso: version.nombre_curso || "",
      enfoque: version.enfoque || "",
      nivel_dificultad: version.contenido?.nivel_dificultad || "basico",
      sector: version.contenido?.sector || "",
    }));
    setTimeout(() => setTemarioGenerado(version.contenido), 300);
  };

  const handleExportarPDF = async (version) => {
    try {
      setIsLoading(true);
      setError("");
      const token = localStorage.getItem("id_token");
      const apiUrl = `https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/Temario_PDF?id=${encodeURIComponent(
        version.nombre_curso
      )}&version=${encodeURIComponent(version.versionId)}`;

      const response = await fetch(apiUrl, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error(`Error al obtener datos del temario: ${response.status}`);
      const data = await response.json();
      exportarPDF(data);
    } catch (err) {
      console.error("❌ Error exportando PDF:", err);
      setError("No se pudo generar el PDF. Intenta nuevamente.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFiltroChange = (e) => {
    const { name, value } = e.target;
    setFiltros((prev) => ({ ...prev, [name]: value }));
  };

  const limpiarFiltros = () => setFiltros({ curso: "", asesor: "", tecnologia: "" });

  const versionesFiltradas = versiones.filter((v) => {
    const nombreCurso = v.nombre_curso || "";
    const tecnologia = v.tecnologia || "";
    const asesor = v.asesor_comercial || "";

    return (
      nombreCurso.toLowerCase().includes(filtros.curso.toLowerCase()) &&
      (filtros.asesor ? asesor === filtros.asesor : true) &&
      tecnologia.toLowerCase().includes(filtros.tecnologia.toLowerCase())
    );
  });

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <div className="header-practico" style={{ marginBottom: "15px" }}>
          <h2>Generador de Temarios Teóricos (Knowledge Transfer)</h2>
        </div>
        <p className="descripcion-practico" style={{ marginTop: "0px" }}>
          Genera un temario teórico orientado a transferencia de conocimiento.
        </p>

        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado (Opcional)</label>
            <input
              name="nombre_preventa"
              value={params.nombre_preventa}
              onChange={handleParamChange}
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial (Opcional)</label>
            <select
              name="asesor_comercial"
              value={params.asesor_comercial}
              onChange={handleParamChange}
              disabled={isLoading}
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
              value={params.tecnologia}
              onChange={handleParamChange}
              disabled={isLoading}
              placeholder="Ej: ITIL, ISO 27001, Gestión del Conocimiento"
            />
          </div>

          <div className="form-group">
            <label>Tema Principal del Curso *</label>
            <input
              name="tema_curso"
              value={params.tema_curso}
              onChange={handleParamChange}
              disabled={isLoading}
              placeholder="Ej: Fundamentos de Knowledge Transfer"
            />
          </div>

          <div className="form-group">
            <label>Nivel de Dificultad</label>
            <select
              name="nivel_dificultad"
              value={params.nivel_dificultad}
              onChange={handleParamChange}
              disabled={isLoading}
            >
              <option value="basico">Básico</option>
              <option value="intermedio">Intermedio</option>
              <option value="avanzado">Avanzado</option>
            </select>
          </div>

          <div className="form-group">
            <label>Número de Sesiones (1–7)</label>
            <div className="slider-container">
              <input
                type="range"
                min="1"
                max="7"
                name="numero_sesiones_por_semana"
                value={params.numero_sesiones_por_semana}
                onChange={handleSliderChange}
                disabled={isLoading}
              />
              <span className="slider-value">
                {params.numero_sesiones_por_semana}{" "}
                {params.numero_sesiones_por_semana > 1 ? "sesiones" : "sesión"}
              </span>
            </div>
          </div>

          <div className="form-group">
            <label>Horas por Sesión (1–8)</label>
            <div className="slider-container">
              <input
                type="range"
                min="1"
                max="8"
                name="horas_por_sesion"
                value={params.horas_por_sesion}
                onChange={handleSliderChange}
                disabled={isLoading}
              />
              <span className="slider-value">{params.horas_por_sesion} horas</span>
            </div>
          </div>

          <div className="form-group total-horas">
            <label>Total del Curso</label>
            <div className="total-badge">
              {params.horas_por_sesion * params.numero_sesiones_por_semana} horas
            </div>
          </div>
        </div>

        <div className="form-group">
          <label>Sector* / Audiencia*</label>
          <textarea
            name="sector"
            value={params.sector}
            onChange={handleParamChange}
            disabled={isLoading}
            rows="3"
            placeholder="Ej: Sector financiero / equipos de gestión, instructores internos..."
          />
        </div>

        <div className="form-group">
          <label>Enfoque Adicional (Opcional)</label>
          <textarea
            name="enfoque"
            value={params.enfoque}
            onChange={handleParamChange}
            disabled={isLoading}
            rows="3"
            placeholder="Ej: Orientado a análisis conceptual, transferencia de conocimiento organizacional..."
          />
        </div>

        <div className="form-group">
          <label>Syllabus Base (Opcional)</label>
          <textarea
            name="syllabus_text"
            value={params.syllabus_text || ""}
            onChange={handleParamChange}
            disabled={isLoading}
            rows="6"
            placeholder="Copia aquí el contenido del syllabus o programa base (texto plano)..."
          />
          <small className="hint">
            💡 Este campo es opcional, pero puede ayudar a la IA a generar un temario más alineado al original.
          </small>
        </div>

        <div className="botones">
          <button className="btn-generar" onClick={handleGenerar} disabled={isLoading}>
            {isLoading ? "Generando..." : "Generar Temario Teórico"}
          </button>
          <button className="btn-versiones" onClick={handleListarVersiones} disabled={isLoading}>
            Ver Versiones Guardadas
          </button>
        </div>

        {error && (
          <div className="error-message">
            <span>⚠️</span> {error}
          </div>
        )}
      </div>

      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}
          onSave={handleGuardarVersion}
          onRegenerate={handleGenerar}
          isLoading={isLoading}
        />
      )}

      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setMostrarModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="filtros-versiones">
                <input
                  type="text"
                  placeholder="Filtrar por curso"
                  name="curso"
                  value={filtros.curso}
                  onChange={handleFiltroChange}
                />
                <select
                  name="asesor"
                  value={filtros.asesor}
                  onChange={handleFiltroChange}
                >
                  <option value="">Todos los asesores</option>
                  {asesoresComerciales.map((a) => <option key={a}>{a}</option>)}
                </select>
                <input
                  type="text"
                  placeholder="Filtrar por tecnología"
                  name="tecnologia"
                  value={filtros.tecnologia}
                  onChange={handleFiltroChange}
                />
                <button className="btn-secundario" onClick={limpiarFiltros}>
                  Limpiar
                </button>
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
                      <th>Acciones</th>
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
                        <td className="acciones-cell">
                          <button
                            className="menu-btn"
                            title = "Editar versión"
                            onClick={() => handleCargarVersion(v)}>
                            ✏️
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {mostrandoModalThor && (
        <div className="modal-overlay-thor">
          <div className="modal-thor">
            <h2>THOR está generando tu temario teórico...</h2>
            <p>
              Mientras se crea el contenido, recuerda que está siendo generado con inteligencia artificial y
              está pensado como una propuesta base.
            </p>
            <ul>
              <li>✅ Verifica la información antes de compartirla con el equipo.</li>
              <li>✏️ Adapta los temas según tu contexto y nivel del grupo.</li>
              <li>🌍 Revisa que el contenido sea inclusivo y respetuoso.</li>
              <li>🔐 No ingreses datos personales o sensibles.</li>
              <li>🧠 Usa la IA como apoyo, no como sustituto del criterio pedagógico.</li>
            </ul>
            <p className="nota-thor">
              La IA es una herramienta poderosa, pero requiere tu supervisión
              como Instructor experto para garantizar calidad, precisión y
              relevancia educativa.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default GeneradorTemarios_KNTR;
