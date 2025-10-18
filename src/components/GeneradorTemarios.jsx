// src/components/GeneradorTemarios.jsx (VERSIÓN FINAL CON MODAL DE VERSIONES)
import React, { useState, useEffect } from "react";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css";

function GeneradorTemarios() {
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
    enfoque: "",
  });

  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [usuarioEmail, setUsuarioEmail] = useState("");
  const [modalVersiones, setModalVersiones] = useState(false);
  const [versiones, setVersiones] = useState([]);
  const [cargandoVersiones, setCargandoVersiones] = useState(false);

  // Obtener correo desde Cognito
  useEffect(() => {
    try {
      const token = localStorage.getItem("id_token");
      if (token) {
        const payload = JSON.parse(atob(token.split(".")[1]));
        setUsuarioEmail(payload.email || payload.username || "anonimo@netec.com");
      }
    } catch (err) {
      console.error("Error leyendo token:", err);
    }
  }, []);

  const handleParamChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
  };

  const handleGenerar = async () => {
    if (!params.tema_curso || !params.tecnologia || !params.asesor_comercial) {
      setError("Por favor completa los campos requeridos.");
      return;
    }

    setError("");
    setIsLoading(true);

    try {
      const token = localStorage.getItem("id_token");
      const res = await fetch(
        "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/PruebadeTEMAR",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(params),
        }
      );

      const data = await res.json();
      let parsed = typeof data.body === "string" ? JSON.parse(data.body) : data.body || data;

      if (parsed.temario) {
        setTemarioGenerado(parsed);
      } else {
        setError("No se encontró contenido del temario.");
      }
    } catch (error) {
      console.error("Error al generar temario:", error);
      setError("Error al generar temario.");
    } finally {
      setIsLoading(false);
    }
  };

  // Guardar versión (EditorDeTemario lo llama)
  const handleSaveVersion = async (temario, nota) => {
    try {
      const token = localStorage.getItem("id_token");
      const response = await fetch(`${import.meta.env.VITE_TEMARIOS_API}/guardar-version`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          autor: usuarioEmail,
          nota,
          fecha_guardado: new Date().toISOString(),
          contenido: temario,
        }),
      });

      const data = await response.json();
      if (response.ok) {
        return { success: true, message: "Versión guardada correctamente" };
      } else {
        return { success: false, message: data.error || "Error al guardar versión" };
      }
    } catch (error) {
      console.error("Error al guardar versión:", error);
      return { success: false, message: "No se pudo guardar la versión" };
    }
  };

  // 🆕 Nueva función: obtener versiones guardadas
  const cargarVersiones = async () => {
    setCargandoVersiones(true);
    try {
      const token = localStorage.getItem("id_token");
      const response = await fetch(`${import.meta.env.VITE_TEMARIOS_API}/obtener-versiones?autor=${usuarioEmail}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      setVersiones(Array.isArray(data.body) ? data.body : JSON.parse(data.body || "[]"));
    } catch (error) {
      console.error("Error al cargar versiones:", error);
    } finally {
      setCargandoVersiones(false);
    }
  };

  const handleVerVersiones = () => {
    setModalVersiones(true);
    cargarVersiones();
  };

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Temarios a la Medida</h2>

        <div className="form-grid">
          <div className="form-group">
            <label>Nombre de Preventa</label>
            <input
              name="nombre_preventa"
              value={params.nombre_preventa}
              onChange={handleParamChange}
              placeholder="Ejemplo: Luis Martínez"
            />
          </div>

          <div className="form-group">
            <label>Asesor Comercial</label>
            <select
              name="asesor_comercial"
              value={params.asesor_comercial}
              onChange={handleParamChange}
            >
              <option value="">Selecciona un asesor</option>
              <option value="Natalia García">Natalia García</option>
              <option value="Mariana López">Mariana López</option>
              <option value="Fernando Castro">Fernando Castro</option>
              <option value="Carla Méndez">Carla Méndez</option>
              <option value="Julio Paredes">Julio Paredes</option>
              <option value="Andrea Molina">Andrea Molina</option>
              <option value="Otro">Otro</option>
            </select>
          </div>

          <div className="form-group">
            <label>Tecnología</label>
            <input
              name="tecnologia"
              value={params.tecnologia}
              onChange={handleParamChange}
              placeholder="Ejemplo: AWS, Azure, Python..."
            />
          </div>

          <div className="form-group">
            <label>Tema del Curso</label>
            <input
              name="tema_curso"
              value={params.tema_curso}
              onChange={handleParamChange}
              placeholder="Ejemplo: Azure Functions"
            />
          </div>

          <div className="form-group">
            <label>Nivel de Dificultad</label>
            <select
              name="nivel_dificultad"
              value={params.nivel_dificultad}
              onChange={handleParamChange}
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
              />
              <span>{params.numero_sesiones_por_semana} sesión</span>
            </div>
          </div>

          <div className="form-group">
            <label>Horas por Sesión (4–12)</label>
            <div className="slider-container">
              <input
                type="range"
                min="4"
                max="12"
                name="horas_por_sesion"
                value={params.horas_por_sesion}
                onChange={handleSliderChange}
              />
              <span>{params.horas_por_sesion} horas</span>
            </div>
          </div>
        </div>

        <div className="form-group-radio">
          <label>Tipo de Objetivo</label>
          <div>
            <label>
              <input
                type="radio"
                name="objetivo_tipo"
                value="saber_hacer"
                checked={params.objetivo_tipo === "saber_hacer"}
                onChange={handleParamChange}
              />
              Saber Hacer (enfocado en habilidades)
            </label>
            <label>
              <input
                type="radio"
                name="objetivo_tipo"
                value="certificacion"
                checked={params.objetivo_tipo === "certificacion"}
                onChange={handleParamChange}
              />
              Certificación (enfocado en examen)
            </label>
          </div>
        </div>

        <div className="form-group">
          <label>Sector / Audiencia</label>
          <textarea
            name="sector"
            value={params.sector}
            onChange={handleParamChange}
            placeholder="Ejemplo: sector financiero, educativo, etc."
          />
        </div>

        <div className="form-group">
          <label>Enfoque Adicional (Opcional)</label>
          <textarea
            name="enfoque"
            value={params.enfoque}
            onChange={handleParamChange}
            placeholder="Ejemplo: casos de uso, proyectos reales, etc."
          />
        </div>

        <div className="botones">
          <button className="btn-generar" onClick={handleGenerar} disabled={isLoading}>
            {isLoading ? "Generando..." : "Generar Propuesta de Temario"}
          </button>
          <button className="btn-versiones" onClick={handleVerVersiones}>
            Ver Versiones Guardadas
          </button>
        </div>

        {error && <p className="error">{error}</p>}
      </div>

      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}
          isLoading={isLoading}
          onSave={handleSaveVersion}
          onRegenerate={(nuevosParams) => {
            setParams((prev) => ({ ...prev, ...nuevosParams }));
            handleGenerar();
          }}
        />
      )}

      {/* 🆕 Modal de versiones */}
      {modalVersiones && (
        <div className="modal-overlay" onClick={() => setModalVersiones(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setModalVersiones(false)}>✕</button>
            </div>
            <div className="modal-body">
              {cargandoVersiones ? (
                <p>Cargando versiones...</p>
              ) : versiones.length === 0 ? (
                <p>No hay versiones guardadas.</p>
              ) : (
                <div className="tabla-versiones-scroll">
                  <table className="versiones-table">
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Nota</th>
                        <th>Autor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {versiones.map((v, i) => (
                        <tr key={i}>
                          <td>{new Date(v.fecha_guardado).toLocaleString()}</td>
                          <td>{v.nota}</td>
                          <td>{v.autor}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default GeneradorTemarios;






