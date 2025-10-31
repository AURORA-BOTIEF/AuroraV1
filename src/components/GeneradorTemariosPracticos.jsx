import React, { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css"; // Asegúrate que este CSS sea el del generador 'Practicos'
import { exportarPDF } from "./EditorDeTemario";

const asesoresComerciales = [
  "Alejandra Galvez", "Ana Aragón", "Arely Alvarez", "Benjamin Araya",
  "Carolina Aguilar", "Cristian Centeno", "Elizabeth Navia", "Eonice Garfías",
  "Guadalupe Agiz", "Jazmin Soriano", "Lezly Durán", "Lusdey Trujillo",
  "Natalia García", "Natalia Gomez", "Vianey Miranda",
].sort();

// === COMPONENTE: GeneradorTemariosPracticos ===
function GeneradorTemariosPracticos() {
  const [params, setParams] = useState({
    nombre_preventa: "",
    asesor_comercial: "",
    tecnologia: "",
    tema_curso: "",
    nivel_dificultad: "basico",
    numero_sesiones_por_semana: 1,
    horas_por_sesion: 7,
    objetivo_tipo: "saber_hacer",
    sector: "",
    enfoque: "", // se forzará a "practico" en el payload si viene vacío
    codigo_certificacion: "",
    syllabus_text: "",
  });

  const [userEmail, setUserEmail] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mostrandoModalThor, setMostrandoModalThor] = useState(false);
  const [error, setError] = useState("");
  const [errorDetails, setErrorDetails] = useState(null); // para 422 de Lambda PRÁCTICOS
  const [validationWarnings, setValidationWarnings] = useState([]);
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({ curso: "", asesor: "", tecnologia: "" });
  const [menuActivo, setMenuActivo] = useState(null);

  // Endpoints (mismos que el generador original; esta UI está alineada a la Lambda PRÁCTICOS)
  const generarApiUrl = "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/tem_practico_openai";
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

    if (name === "objetivo_tipo") {
      let codigoCert = params.codigo_certificacion;
      if (value === "saber_hacer") {
        codigoCert = "";
      }
      setParams((prev) => ({
        ...prev,
        [name]: value,
        codigo_certificacion: codigoCert,
      }));
      return;
    }

    if (name === "horas_por_sesion" || name === "numero_sesiones_por_semana") {
      setParams((prev) => ({ ...prev, [name]: parseInt(value, 10) }));
      return;
    }

    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value, 10) }));
  };

  const validarReglasPracticosCliente = () => {
    // Validaciones rápidas en cliente para alinear expectativas con Lambda PRÁCTICOS
    const total = params.horas_por_sesion * params.numero_sesiones_por_semana;
    if (total < 7 || total > 40) {
      return `La duración total del curso debe estar entre 7 y 40 horas. Actual: ${total} horas.`;
    }
    if (params.horas_por_sesion < 4 || params.horas_por_sesion > 12) {
      return `Horas por sesión fuera de rango (4-12). Actual: ${params.horas_por_sesion} horas.`;
    }
    if (params.numero_sesiones_por_semana < 1 || params.numero_sesiones_por_semana > 7) {
      return `Número de sesiones fuera de rango (1-7). Actual: ${params.numero_sesiones_por_semana}.`;
    }
    return null;
  };

  const handleGenerar = async () => {
    setError("");
    setErrorDetails(null);
    setValidationWarnings([]);

    if (!params.tecnologia || !params.tema_curso || !params.sector) {
      setError("Completa todos los campos requeridos: Tecnología, Tema del Curso y Sector/Audiencia.");
      return;
    }

    if (params.objetivo_tipo === "certificacion" && !params.codigo_certificacion) {
      setError("Para certificación, debes especificar el código de certificación.");
      return;
    }

    const errorCliente = validarReglasPracticosCliente();
    if (errorCliente) {
      setError(errorCliente);
      return;
    }

    const horasTotales = params.horas_por_sesion * params.numero_sesiones_por_semana;

    setIsLoading(true);
    setMostrandoModalThor(true);
    // Ocultar automáticamente después de 2:40
    setTimeout(() => setMostrandoModalThor(false), 160000);

    try {
      const payload = {
        ...params,
        horas_totales: horasTotales,
        // Asegurar enfoque práctico si viene vacío
        enfoque: params.enfoque?.trim() || "practico",
      };

      if (payload.objetivo_tipo !== "certificacion") {
        delete payload.codigo_certificacion;
      }

      const token = localStorage.getItem("id_token");

      const response = await fetch(generarApiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const raw = await response.json();
      const data = typeof raw === "string" ? JSON.parse(raw) : raw;

      if (!response.ok) {
        // La Lambda PRÁCTICOS devuelve { error: { message, errors[], warnings[] ... } }
        const errObj = data?.error || data;
        setError(
          typeof errObj === "object"
            ? errObj?.message || "Ocurrió un error en el servidor."
            : String(errObj || "Ocurrió un error en el servidor.")
        );
        if (typeof errObj === "object") {
          setErrorDetails(errObj);
        }
        return;
      }

      // Éxito
      const temarioCompleto = {
        ...data,
        nombre_preventa: params.nombre_preventa,
        asesor_comercial: params.asesor_comercial,
        horas_totales: horasTotales,
        enfoque: params.enfoque?.trim() || "practico",
        tecnologia: params.tecnologia,
        tema_curso: params.tema_curso,
      };

      if (Array.isArray(data?._validation_warnings)) {
        setValidationWarnings(data._validation_warnings);
      }

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
        enfoque: params.enfoque?.trim() || "practico",
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
      if (!res.ok) {
        throw new Error(data.error || "Error al guardar versión");
      }
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

  // Exportar PDF (Lambda Temario_PDF)
  const handleExportarPDF = async (version) => {
    try {
      setIsLoading(true);
      setError("");
      setErrorDetails(null);

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

      if (!response.ok) {
        throw new Error(`Error al obtener datos del temario: ${response.status}`);
      }

      const data = await response.json();
      exportarPDF(data);
    } catch (err) {
      console.error("❌ Error exportando PDF:", err);
      setError("No se pudo generar el PDF. Intenta nuevamente.");
    } finally {
      setIsLoading(false);
    }
  };

  // Acción "Ver" — vista rápida simple
  const handleVerVersion = (v) => {
    try {
      const contenido = v?.contenido || v;
      alert(JSON.stringify(contenido, null, 2));
    } catch (e) {
      console.error(e);
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
          <h2>Generador de Temarios PRÁCTICOS (100% Hands-on)</h2>
        </div>
        <p className="descripcion-practico" style={{ marginTop: "0px" }}>
          Introduce los detalles para generar una propuesta de temario 100% práctica con Inteligencia Artificial.
        </p>

        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado (Opcional)</label>
            <input name="nombre_preventa" value={params.nombre_preventa} onChange={handleParamChange} disabled={isLoading} />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial (Opcional)</label>
            <select name="asesor_comercial" value={params.asesor_comercial} onChange={handleParamChange} disabled={isLoading}>
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
              placeholder="Ej: AWS, React, Python"
            />
          </div>

          <div className="form-group">
            <label>Tema Principal del Curso *</label>
            <input
              name="tema_curso"
              value={params.tema_curso}
              onChange={handleParamChange}
              disabled={isLoading}
              placeholder="Ej: Arquitecturas Serverless"
            />
          </div>

          <div className="form-group">
            <label>Nivel de Dificultad</label>
            <select name="nivel_dificultad" value={params.nivel_dificultad} onChange={handleParamChange} disabled={isLoading}>
              <option value="basico">Básico</option>
              <option value="intermedio">Intermedio</option>
              <option value="avanzado">Avanzado</option>
            </select>
          </div>

          <div className="form-group">
            <label>Número de Sesiones (1-7)</label>
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
                {params.numero_sesiones_por_semana} {params.numero_sesiones_por_semana > 1 ? "sesiones" : "sesión"}
              </span>
            </div>
          </div>

          <div className="form-group">
            <label>Horas por Sesión (4-12)</label>
            <div className="slider-container">
              <input
                type="range"
                min="4"
                max="12"
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
            <div className="total-badge">{params.horas_por_sesion * params.numero_sesiones_por_semana} horas</div>
          </div>
        </div>

        <div className="form-group-radio">
          <label>Tipo de Objetivo</label>
          <div className="radio-group">
            <label className="radio-label">
              <input
                type="radio"
                name="objetivo_tipo"
                value="saber_hacer"
                checked={params.objetivo_tipo === "saber_hacer"}
                onChange={handleParamChange}
                disabled={isLoading}
              />
              <span>Saber Hacer (Enfocado en habilidades)</span>
            </label>
            <label className="radio-label">
              <input
                type="radio"
                name="objetivo_tipo"
                value="certificacion"
                checked={params.objetivo_tipo === "certificacion"}
                onChange={handleParamChange}
                disabled={isLoading}
              />
              <span>Certificación (Enfocado en examen)</span>
            </label>
          </div>
        </div>

        {params.objetivo_tipo === "certificacion" && (
          <div className="form-group certificacion-field">
            <label>Código de Certificación *</label>
            <input
              name="codigo_certificacion"
              value={params.codigo_certificacion}
              onChange={handleParamChange}
              disabled={isLoading}
              placeholder="Ej: AWS CLF-C02, AZ-900"
            />
          </div>
        )}

        <div className="form-group">
          <label>Sector / Audiencia *</label>
          <textarea
            name="sector"
            value={params.sector}
            onChange={handleParamChange}
            disabled={isLoading}
            rows="3"
            placeholder="Ej: Sector financiero, Desarrolladores con 1 año de experiencia..."
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
            placeholder="Ej: Orientado a patrones de diseño, con énfasis en casos prácticos"
          />
          <small className="hint">💡 Si lo dejas vacío se enviará automáticamente como "practico".</small>
        </div>

        <div className="form-group">
          <label>Syllabus Base (Opcional)</label>
          <textarea
            name="syllabus_text"
            value={params.syllabus_text || ""}
            onChange={handleParamChange}
            disabled={isLoading}
            rows="6"
            placeholder="Copia y pega aquí el contenido del syllabus o temario base (texto plano, sin formato)..."
          />
          <small className="hint">💡 Ayuda a alinear la propuesta con un temario base.</small>
        </div>

        <div className="botones">
          <button className="btn-generar" onClick={handleGenerar} disabled={isLoading}>
            {isLoading ? "Generando..." : "Generar Propuesta de Temario"}
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

        {errorDetails?.errors?.length ? (
          <div className="error-block">
            <h4>Detalles de validación</h4>
            <ul>
              {errorDetails.errors.map((er, idx) => (
                <li key={idx}>• {er}</li>
              ))}
            </ul>
            {errorDetails.warnings?.length ? (
              <>
                <h5>Advertencias</h5>
                <ul>
                  {errorDetails.warnings.map((w, i) => (
                    <li key={`w-${i}`}>• {w}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        ) : null}

        {validationWarnings?.length ? (
          <div className="warning-block">
            <h4>Advertencias del generador</h4>
            <ul>
              {validationWarnings.map((w, i) => (
                <li key={`valw-${i}`}>• {w}</li>
              ))}
            </ul>
          </div>
        ) : null}
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
              <button className="modal-close" onClick={() => setMostrarModal(false)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div className="filtros-versiones">
                <input type="text" placeholder="Filtrar por curso" name="curso" value={filtros.curso} onChange={handleFiltroChange} />
                <select name="asesor" value={filtros.asesor} onChange={handleFiltroChange}>
                  <option value="">Todos los asesores</option>
                  {asesoresComerciales.map((a) => (
                    <option key={a}>{a}</option>
                  ))}
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
                          <button className="menu-btn" onClick={() => setMenuActivo(menuActivo === i ? null : i)}>
                            ⋮
                          </button>
                          {menuActivo === i && (
                            <div className="menu-opciones">
                              <button onClick={() => handleCargarVersion(v)}>✏️ Editar</button>
                              <button onClick={() => handleExportarPDF(v.contenido)}>📄 Exportar PDF</button>
                              <button onClick={() => handleVerVersion(v)}>👁️ Ver</button>
                            </div>
                          )}
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
            <h2>⚙️ THOR está generando tu temario práctico...</h2>
            <p>
              Mientras se crea el contenido, recuerda que está siendo generado con inteligencia artificial y está pensado como una propuesta base
              para ayudarte a estructurar tus ideas.
            </p>
            <ul>
              <li>✅ Verifica la información antes de compartirla con el equipo de Preventa.</li>
              <li>✏️ Edita y adapta los temas según tus objetivos, el nivel del grupo y el contexto específico.</li>
              <li>🌍 Revisa y asegúrate de que el contenido sea inclusivo y respetuoso.</li>
              <li>🔐 Evita ingresar datos personales o sensibles en la plataforma.</li>
              <li>🧠 Utiliza el contenido como apoyo, no como sustituto de tu criterio pedagógico.</li>
            </ul>
            <p className="nota-thor">
              La IA es una herramienta poderosa, pero requiere tu supervisión como Instructor experto para garantizar calidad, precisión y relevancia educativa.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default GeneradorTemariosPracticos;
