import React, { useState } from "react";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css";

const API_BASE = import.meta.env.VITE_TEMARIOS_API || "";

function GeneradorTemarios() {
  const [temario, setTemario] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [params, setParams] = useState({
    tecnologia: "",
    tema_curso: "",
    nivel_dificultad: "basico",
    numero_sesiones: 1,
    horas_por_sesion: 7,
    objetivo_tipo: "saber_hacer",
    sector: "",
    enfoque: "",
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value, 10) }));
  };

  const handleGenerate = async () => {
    setIsLoading(true);
    setTemario(null);
    try {
      const token = localStorage.getItem("id_token");
      const res = await fetch(`${API_BASE}/temarios/generar`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(params),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || "Error al generar temario");
      setTemario(data);
    } catch (error) {
      console.error("Error:", error);
      alert("❌ Error al generar el temario.");
    } finally {
      setIsLoading(false);
    }
  };

  // --- función auxiliar para decodificar el token JWT de Cognito ---
  function parseJwt(token) {
    try {
      const base64Url = token.split(".")[1];
      const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split("")
          .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
          .join("")
      );
      return JSON.parse(jsonPayload);
    } catch (e) {
      console.error("Error al decodificar token:", e);
      return null;
    }
  }

  // --- función para guardar la versión del temario ---
  const handleGuardarVersion = async (temarioParaGuardar) => {
    try {
      const token = localStorage.getItem("id_token");

      // ✅ Decodificar el token para obtener el email del usuario logueado
      const decoded = parseJwt(token);
      const autorEmail = decoded?.email || "autor_desconocido@netec.com";

      const bodyData = {
        cursoId: params.tema_curso,
        contenido: temarioParaGuardar,
        autor: autorEmail, // <-- ahora dinámico
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
          mode: "cors",
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
      return true; // ✅ evita el error "Respuesta vacía del onSave"
    } catch (error) {
      console.error(error);
      alert("❌ Error al guardar la versión");
      return false; // ✅ garantiza retorno en caso de error
    }
  };

  return (
    <div className="generador-container">
      <h2>Generador de Temarios Inteligente</h2>

      <div className="form-group">
        <label>Tecnología</label>
        <input
          name="tecnologia"
          value={params.tecnologia}
          onChange={handleChange}
          placeholder="Ej: Azure, AWS, Scrum..."
          disabled={isLoading}
        />
      </div>

      <div className="form-group">
        <label>Tema del Curso</label>
        <input
          name="tema_curso"
          value={params.tema_curso}
          onChange={handleChange}
          placeholder="Ej: Fundamentos de Scrum"
          disabled={isLoading}
        />
      </div>

      <div className="form-group">
        <label>Nivel de Dificultad</label>
        <select
          name="nivel_dificultad"
          value={params.nivel_dificultad}
          onChange={handleChange}
          disabled={isLoading}
        >
          <option value="basico">Básico</option>
          <option value="intermedio">Intermedio</option>
          <option value="avanzado">Avanzado</option>
        </select>
      </div>

      <div className="form-group">
        <label>Número de Sesiones (1-7)</label>
        <input
          type="range"
          name="numero_sesiones"
          min="1"
          max="7"
          value={params.numero_sesiones}
          onChange={handleSliderChange}
          disabled={isLoading}
        />
        <span>{params.numero_sesiones} sesión(es)</span>
      </div>

      <div className="form-group">
        <label>Horas por Sesión (4-12)</label>
        <input
          type="range"
          name="horas_por_sesion"
          min="4"
          max="12"
          value={params.horas_por_sesion}
          onChange={handleSliderChange}
          disabled={isLoading}
        />
        <span>{params.horas_por_sesion} horas</span>
      </div>

      <div className="form-group">
        <label>Tipo de Objetivo</label>
        <div className="radio-group">
          <label>
            <input
              type="radio"
              name="objetivo_tipo"
              value="saber_hacer"
              checked={params.objetivo_tipo === "saber_hacer"}
              onChange={handleChange}
              disabled={isLoading}
            />
            Saber Hacer (enfocado en habilidades)
          </label>
          <label>
            <input
              type="radio"
              name="objetivo_tipo"
              value="certificacion"
              checked={params.objetivo_tipo === "certificacion"}
              onChange={handleChange}
              disabled={isLoading}
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
          onChange={handleChange}
          placeholder="Ej: Profesionales del sector financiero que buscan aplicar Scrum..."
          disabled={isLoading}
        />
      </div>

      <div className="form-group">
        <label>Enfoque Adicional (Opcional)</label>
        <textarea
          name="enfoque"
          value={params.enfoque}
          onChange={handleChange}
          placeholder="Ej: Orientado a patrones de diseño..."
          disabled={isLoading}
        />
      </div>

      <div className="botones-container">
        <button
          className="btn-generar"
          onClick={handleGenerate}
          disabled={isLoading}
        >
          {isLoading ? "Generando..." : "Generar Propuesta de Temario"}
        </button>

        <button
          className="btn-versiones"
          onClick={() =>
            (window.location.href = "/versiones") // deja tu flujo actual
          }
          disabled={isLoading}
        >
          Ver Versiones Guardadas
        </button>
      </div>

      {temario && (
        <EditorDeTemario
          temarioInicial={temario}
          onSave={handleGuardarVersion}
          onRegenerate={handleGenerate}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}

export default GeneradorTemarios;



