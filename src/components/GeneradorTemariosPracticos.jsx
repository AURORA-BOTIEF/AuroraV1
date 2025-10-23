import React, { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
// import { post } from "aws-amplify/api"; // No necesario - usando fetch directo
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css";

const asesoresComerciales = [
  "Alejandra Galvez", "Ana Aragón", "Arely Alvarez", "Benjamin Araya",
  "Carolina Aguilar", "Cristian Centeno", "Elizabeth Navia", "Eonice Garfías",
  "Guadalupe Agiz", "Jazmin Soriano", "Lezly Durán", "Lusdey Trujillo",
  "Natalia García", "Natalia Gomez", "Vianey Miranda",
].sort();

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
    enfoque: "practico",
    codigo_certificacion: "",
  });

  const [userEmail, setUserEmail] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({ curso: "", asesor: "", tecnologia: "" });
  const [menuActivo, setMenuActivo] = useState(null);

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
      let enfoqueAuto = "practico";
      let codigoCert = params.codigo_certificacion;
      
      if (value === "saber_hacer") {
        codigoCert = "";
      }
      
      setParams((prev) => ({ 
        ...prev, 
        [name]: value, 
        enfoque: enfoqueAuto,
        codigo_certificacion: codigoCert 
      }));
      return;
    }
    
    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
  };

  const handleGenerar = async () => {
    // Validaciones
    if (!params.nombre_preventa || !params.asesor_comercial || 
        !params.tecnologia || !params.tema_curso || !params.sector) {
      setError("Completa todos los campos requeridos (incluye Sector/Audiencia).");
      return;
    }

    if (params.objetivo_tipo === "certificacion" && !params.codigo_certificacion) {
      setError("Para certificación, debes especificar el código de certificación.");
      return;
    }

    const horasTotales = params.horas_por_sesion * params.numero_sesiones_por_semana;
    if (horasTotales > 40) {
      setError("La duración total no puede superar 40 horas (5 días de 8h).");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      // Preparar payload según especificaciones de la Lambda
      const payload = {
        tecnologia: params.tecnologia,
        tema_curso: params.tema_curso,
        nivel_dificultad: params.nivel_dificultad,
        sector: params.sector,
        horas_totales: horasTotales,
        enfoque: "practico", // Siempre práctico
        objetivo_tipo: params.objetivo_tipo,
        codigo_certificacion: params.codigo_certificacion || "",
        horas_por_sesion: params.horas_por_sesion,
        numero_sesiones_por_semana: params.numero_sesiones_por_semana,
      };

      console.log("📤 Enviando payload:", payload);

      // Llamar a la API de Lambda usando fetch directo
      const token = localStorage.getItem("id_token");
      const response = await fetch(
        "https://8iklrx7rl4.execute-api.us-east-1.amazonaws.com/default/tem_practico_openai",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Error al generar temario");
      }

      console.log("✅ Respuesta recibida:", data);

      // Agregar metadatos del formulario al temario generado
      const temarioCompleto = {
        ...data,
        nombre_preventa: params.nombre_preventa,
        asesor_comercial: params.asesor_comercial,
        horas_totales: horasTotales,
      };

      setTemarioGenerado(temarioCompleto);

    } catch (err) {
      console.error("❌ Error:", err);
      setError(err.message || "No se pudo generar el temario. Intenta nuevamente.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGuardarVersion = async (temarioParaGuardar) => {
    try {
      const token = localStorage.getItem("id_token");
      const bodyData = {
        cursoId: params.tema_curso,
        contenido: temarioParaGuardar,
        autor: userEmail,
        asesor_comercial: params.asesor_comercial,
        nombre_preventa: params.nombre_preventa,
        nombre_curso: params.tema_curso,
        tecnologia: params.tecnologia,
        nota_version: `Guardado el ${new Date().toLocaleString()}`,
        fecha_creacion: new Date().toISOString(),
      };

      const res = await fetch(
        "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(bodyData),
        }
      );

      const data = await res.json();
      if (!res.ok || !data.success)
        throw new Error(data.error || "Error al guardar versión");

      alert("✅ Versión guardada correctamente");
    } catch (error) {
      console.error(error);
      alert("❌ Error al guardar la versión");
    }
  };

  const handleListarVersiones = async () => {
    try {
      const token = localStorage.getItem("id_token");
      const res = await fetch(
        "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones",
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const data = await res.json();
      const sortedData = data.sort(
        (a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion)
      );
      setVersiones(sortedData);
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
    }
  };

  const handleCargarVersion = (version) => {
    setMostrarModal(false);
    setTimeout(() => setTemarioGenerado(version.contenido), 300);
  };

  const handleFiltroChange = (e) => {
    const { name, value } = e.target;
    setFiltros((prev) => ({ ...prev, [name]: value }));
  };

  const limpiarFiltros = () => {
    setFiltros({ curso: "", asesor: "", tecnologia: "" });
  };

  const versionesFiltradas = versiones.filter((v) => {
    return (
      v.nombre_curso.toLowerCase().includes(filtros.curso.toLowerCase()) &&
      (filtros.asesor ? v.asesor_comercial === filtros.asesor : true) &&
      v.tecnologia.toLowerCase().includes(filtros.tecnologia.toLowerCase())
    );
  });

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <div className="header-practico">
          <h2>🚀 Generador de Temarios 100% Prácticos</h2>
          <span className="badge-practico">HANDS-ON TRAINING</span>
        </div>
        <p className="descripcion-practico">
          Genera temarios enfocados en laboratorios, proyectos y actividades prácticas.
          <strong> Sin teoría, solo desarrollo de habilidades.</strong>
        </p>

        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado *</label>
            <input 
              name="nombre_preventa" 
              value={params.nombre_preventa} 
              onChange={handleParamChange} 
              disabled={isLoading}
              placeholder="Ej: Preventa Banco XYZ - Q4 2024"
            />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial *</label>
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
              placeholder="Ej: AWS, React, Python, Kubernetes"
            />
          </div>

          <div className="form-group">
            <label>Tema Principal del Curso *</label>
            <input 
              name="tema_curso" 
              value={params.tema_curso} 
              onChange={handleParamChange} 
              disabled={isLoading} 
              placeholder="Ej: Desarrollo de APIs REST con FastAPI"
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
              <option value="basico">Básico (Fundamentos prácticos)</option>
              <option value="intermedio">Intermedio (Proyectos completos)</option>
              <option value="avanzado">Avanzado (Arquitecturas complejas)</option>
            </select>
          </div>

          <div className="form-group">
            <label>Número de Sesiones (1-7 días)</label>
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
                {params.numero_sesiones_por_semana} día{params.numero_sesiones_por_semana > 1 ? 's' : ''}
              </span>
            </div>
          </div>

          <div className="form-group">
            <label>Horas por Sesión (7-8h)</label>
            <div className="slider-container">
              <input 
                type="range" 
                min="7" 
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
              <span>🎯 Saber Hacer (Habilidades prácticas)</span>
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
              <span>🏆 Certificación (Preparación para examen)</span>
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
              placeholder="Ej: AWS-SAA-C03, CKA, AZ-900"
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
            placeholder="Describe el sector y la audiencia objetivo. Ej: Desarrolladores del sector financiero que necesitan implementar microservicios seguros"
          />
        </div>

        <div className="botones">
          <button 
            className="btn-generar" 
            onClick={handleGenerar} 
            disabled={isLoading}
          >
            {isLoading ? "⏳ Generando..." : "🚀 Generar Temario Práctico"}
          </button>
          <button 
            className="btn-versiones" 
            onClick={handleListarVersiones} 
            disabled={isLoading}
          >
            📚 Ver Versiones Guardadas
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
          isLoading={isLoading}
        />
      )}

      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📚 Versiones Guardadas</h3>
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
                      <tr key={i}>
                        <td>{v.nombre_curso}</td>
                        <td>{v.tecnologia}</td>
                        <td>{v.asesor_comercial}</td>
                        <td>{new Date(v.fecha_creacion).toLocaleString()}</td>
                        <td>{v.autor}</td>
                        <td className="acciones-cell">
                          <button 
                            className="menu-btn" 
                            onClick={() => setMenuActivo(menuActivo === i ? null : i)}
                          >
                            ⋮
                          </button>
                          {menuActivo === i && (
                            <div className="menu-opciones">
                              <button onClick={() => handleCargarVersion(v)}>
                                Editar
                              </button>
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
    </div>
  );
}

export default GeneradorTemariosPracticos;