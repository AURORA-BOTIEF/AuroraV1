// src/components/GeneradorTemarios.jsx (VERSIÓN RESTAURADA Y FUNCIONAL)
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

  // Leer correo del usuario logueado
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
      let parsed;
      if (typeof data.body === "string") parsed = JSON.parse(data.body);
      else parsed = data.body || data;

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
        console.log("✅ Versión guardada:", data);
        return { success: true, message: "Versión guardada correctamente" };
      } else {
        return { success: false, message: data.error || "Error al guardar versión" };
      }
    } catch (error) {
      console.error("Error al guardar versión:", error);
      return { success: false, message: "No se pudo guardar la versión" };
    }
  };

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Temarios a la Medida</h2>

        <div className="form-grid">
          <div className="form-group">
            <label>Asesor Comercial</label>
            <input
              name="asesor_comercial"
              value={params.asesor_comercial}
              onChange={handleParamChange}
              placeholder="Ejemplo: Juan Pérez"
            />
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
          <button className="btn-versiones">Ver Versiones Guardadas</button>
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
    </div>
  );
}

export default GeneradorTemarios;





