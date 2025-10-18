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
    sector: "",
    enfoque: "",
  });

  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({
    curso: "",
    asesor: "",
    tecnologia: "",
  });
  const [menuActivo, setMenuActivo] = useState(null);

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
      const response = await fetch(
        "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/PruebadeTEMAR",
        {
          method: "POST",
          mode: "cors",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(params),
        }
      );

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
        autor: "anette.flores@netec.com.mx",
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

      const sortedData = data.sort(
        (a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion)
      );

      setVersiones(sortedData);
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
    }
  };

  const handleActualizarVersiones = () => {
    handleListarVersiones();
  };

  const handleCargarVersion = (version) => {
    setMostrarModal(false);
    setTimeout(() => setTemarioGenerado(version.contenido), 300);
  };

  const handleExportar = (version, tipo) => {
    setMostrarModal(false);
    setTimeout(() => {
      setTemarioGenerado(version.contenido);
      if (tipo === "pdf") {
        setTimeout(() => document.querySelector(".btn-secundario:nth-child(3)")?.click(), 500);
      } else {
        setTimeout(() => document.querySelector(".btn-secundario:nth-child(3)")?.click(), 500);
      }
    }, 300);
  };

  const handleFiltroChange = (e) => {
    const { name, value } = e.target;
    setFiltros((prev) => ({ ...prev, [name]: value }));
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
        <h2>Generador de Temarios a la Medida</h2>
        <p>Introduce los detalles para generar una propuesta de temario con Inteligencia Artificial.</p>

        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado</label>
            <input name="nombre_preventa" value={params.nombre_preventa} onChange={handleParamChange} />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial Asociado</label>
            <select name="asesor_comercial" value={params.asesor_comercial} onChange={handleParamChange}>
              <option value="">Selecciona un asesor(a)</option>
              {asesoresComerciales.map((a) => (
                <option key={a}>{a}</option>
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
              <input type="range" min="1" max="7" name="numero_sesiones_por_semana" value={params.numero_sesiones_por_semana} onChange={handleSliderChange} />
              <span>{params.numero_sesiones_por_semana} sesión</span>
            </div>
          </div>

          <div className="form-group">
            <label>Horas por Sesión (4-12)</label>
            <div className="slider-container">
              <input type="range" min="4" max="12" name="horas_por_sesion" value={params.horas_por_sesion} onChange={handleSliderChange} />
              <span>{params.horas_por_sesion} horas</span>
            </div>
          </div>
        </div>

        <div className="form-group-radio">
          <label>Tipo de Objetivo</label>
          <div>
            <label>
              <input type="radio" name="objetivo_tipo" value="saber_hacer" checked={params.objetivo_tipo === "saber_hacer"} onChange={handleParamChange} /> Saber Hacer
            </label>
            <label>
              <input type="radio" name="objetivo_tipo" value="certificacion" checked={params.objetivo_tipo === "certificacion"} onChange={handleParamChange} /> Certificación
            </label>
          </div>
        </div>

        <div className="botones">
          <button className="btn-generar" onClick={handleGenerar} disabled={isLoading}>
            {isLoading ? "Generando..." : "Generar Propuesta de Temario"}
          </button>
          <button className="btn-versiones" onClick={handleListarVersiones}>
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
              <div className="modal-actions">
                <button className="refresh-btn" onClick={handleActualizarVersiones}>🔄</button>
                <button className="close-btn" onClick={() => setMostrarModal(false)}>✕</button>
              </div>
            </div>

            {/* Filtros */}
            <div className="filtros-versiones">
              <input type="text" name="curso" placeholder="Buscar curso..." value={filtros.curso} onChange={handleFiltroChange} />
              <select name="asesor" value={filtros.asesor} onChange={handleFiltroChange}>
                <option value="">Todos los asesores</option>
                {asesoresComerciales.map((a) => (
                  <option key={a}>{a}</option>
                ))}
              </select>
              <input type="text" name="tecnologia" placeholder="Ej: AWS, React..." value={filtros.tecnologia} onChange={handleFiltroChange} />
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
                    <td className="acciones-cell">
                      <button
                        className="menu-btn"
                        onClick={() => setMenuActivo(menuActivo === i ? null : i)}
                      >
                        ⋮
                      </button>
                      {menuActivo === i && (
                        <div className="menu-opciones">
                          <button onClick={() => handleCargarVersion(v)}>✏️ Editar</button>
                          <button onClick={() => handleExportar(v, "pdf")}>📄 Exportar PDF</button>
                          <button onClick={() => handleExportar(v, "excel")}>📊 Exportar Excel</button>
                        </div>
                      )}
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





