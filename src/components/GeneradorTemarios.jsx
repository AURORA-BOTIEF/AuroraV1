import React, { useState } from "react";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css";

const asesoresComerciales = [
  "Alejandra Galvez", "Ana Aragón", "Arely Alvarez", "Benjamin Araya",
  "Carolina Aguilar", "Cristian Centeno", "Elizabeth Navia", "Eonice Garfías",
  "Guadalupe Agiz", "Jazmin Soriano", "Lezly Durán", "Lusdey Trujillo",
  "Natalia García", "Natalia Gomez", "Vianey Miranda",
].sort();

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
    codigo_certificacion: "",
    sector: "",
    enfoque: "",
  });

  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtro, setFiltro] = useState("");
  const [busqueda, setBusqueda] = useState("");

  // 🔥 URL FIJA para evitar errores 404
  const API_BASE = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/dev2";

  // 🔍 Obtener el correo real del usuario autenticado en Cognito
  const getUsuarioActual = () => {
    try {
      const token = localStorage.getItem("id_token");
      if (!token) return "desconocido@netec.com";
      const payload = JSON.parse(atob(token.split(".")[1]));
      return payload.email || payload["cognito:username"] || "desconocido@netec.com";
    } catch {
      return "desconocido@netec.com";
    }
  };

  const handleParamChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
  };

  const handleGenerar = async () => {
    if (
      !params.nombre_preventa ||
      !params.asesor_comercial ||
      !params.tecnologia ||
      !params.tema_curso
    ) {
      setError("Completa todos los campos requeridos antes de continuar.");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const token = localStorage.getItem("id_token");
      const response = await fetch(`${API_BASE}/PruebadeTEMAR`, {
        method: "POST",
        mode: "cors",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(params),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Error al generar temario");

      setTemarioGenerado({ ...data, ...params });
    } catch (err) {
      console.error(err);
      setError("No se pudo generar el temario. Intenta nuevamente.");
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
        autor: getUsuarioActual(),
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
          mode: "cors",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );
      const data = await res.json();
      // Ordenar por fecha de creación (más reciente primero)
      const ordenadas = [...data].sort(
        (a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion)
      );
      setVersiones(ordenadas);
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
    }
  };

  const handleCargarVersion = (version) => {
    setMostrarModal(false);
    setTimeout(() => setTemarioGenerado(version.contenido), 300);
  };

  const limpiarFiltros = () => {
    setFiltro("");
    setBusqueda("");
  };

  const versionesFiltradas = versiones.filter((v) => {
    return (
      (!filtro || v.tecnologia?.toLowerCase().includes(filtro.toLowerCase())) &&
      (!busqueda ||
        v.nombre_curso?.toLowerCase().includes(busqueda.toLowerCase()) ||
        v.asesor_comercial?.toLowerCase().includes(busqueda.toLowerCase()))
    );
  });

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Temarios a la Medida</h2>
        <p>Introduce los detalles para generar una propuesta de temario con Inteligencia Artificial.</p>

        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado</label>
            <input
              name="nombre_preventa"
              value={params.nombre_preventa}
              onChange={handleParamChange}
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial Asociado</label>
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
            <label>Tecnología</label>
            <input
              name="tecnologia"
              value={params.tecnologia}
              onChange={handleParamChange}
              placeholder="Ej: AWS, React, Python"
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label>Tema Principal del Curso</label>
            <input
              name="tema_curso"
              value={params.tema_curso}
              onChange={handleParamChange}
              placeholder="Ej: Arquitecturas Serverless"
              disabled={isLoading}
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
              <span>{params.numero_sesiones_por_semana} sesión</span>
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
                disabled={isLoading}
              />{" "}
              Saber Hacer (enfocado en habilidades)
            </label>
            <label>
              <input
                type="radio"
                name="objetivo_tipo"
                value="certificacion"
                checked={params.objetivo_tipo === "certificacion"}
                onChange={handleParamChange}
                disabled={isLoading}
              />{" "}
              Certificación (enfocado en examen)
            </label>
          </div>
        </div>

        {params.objetivo_tipo === "certificacion" && (
          <div className="form-group">
            <label>Código de Certificación</label>
            <input
              name="codigo_certificacion"
              value={params.codigo_certificacion}
              onChange={handleParamChange}
              placeholder="Ej: AZ-104, SAA-C03, DP-100..."
              disabled={isLoading}
            />
          </div>
        )}

        <div className="form-group">
          <label>Sector / Audiencia</label>
          <textarea
            name="sector"
            value={params.sector}
            onChange={handleParamChange}
            placeholder="Ej: Sector financiero, desarrolladores con 1 año de experiencia..."
            disabled={isLoading}
          />
        </div>

        <div className="form-group">
          <label>Enfoque Adicional (Opcional)</label>
          <textarea
            name="enfoque"
            value={params.enfoque}
            onChange={handleParamChange}
            placeholder="Ej: Orientado a patrones de diseño..."
            disabled={isLoading}
          />
        </div>

        <div className="botones">
          <button
            className="btn-generar"
            onClick={handleGenerar}
            disabled={isLoading}
          >
            {isLoading ? "Generando..." : "Generar Propuesta de Temario"}
          </button>
          <button
            className="btn-versiones"
            onClick={handleListarVersiones}
            disabled={isLoading}
          >
            Ver Versiones Guardadas
          </button>
        </div>

        {error && <p className="error">{error}</p>}
      </div>

      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}
          onRegenerate={handleGenerar}
          onSave={handleGuardarVersion}
          isLoading={isLoading}
        />
      )}

      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="close-btn" onClick={() => setMostrarModal(false)}>
                ✕
              </button>
            </div>

            <div className="filtros-versiones">
              <input
                type="text"
                placeholder="Buscar por curso o asesor..."
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
              />
              <input
                type="text"
                placeholder="Filtrar por tecnología..."
                value={filtro}
                onChange={(e) => setFiltro(e.target.value)}
              />
              <button className="btn-limpiar" onClick={limpiarFiltros}>🧹 Limpiar</button>
            </div>

            <table className="tabla-versiones">
              <thead>
                <tr>
                  <th>Curso</th>
                  <th>Tecnología</th>
                  <th>Asesor</th>
                  <th>Fecha</th>
                  <th>Autor</th>
                  <th>Acción</th>
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
                    <td>
                      <div className="menu-acciones">
                        <button
                          className="btn-acciones"
                          title="Opciones"
                        >
                          ⋮
                        </button>
                        <div className="menu-opciones">
                          <button onClick={() => handleCargarVersion(v)}>📂 Ver</button>
                          <button onClick={() => alert("🚧 Editar en desarrollo")}>✏️ Editar</button>
                          <button onClick={() => alert("📄 Exportar PDF pronto disponible")}>📄 PDF</button>
                          <button onClick={() => alert("📊 Exportar Excel pronto disponible")}>📊 Excel</button>
                        </div>
                      </div>
                    </td>
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

export default GeneradorTemarios;
