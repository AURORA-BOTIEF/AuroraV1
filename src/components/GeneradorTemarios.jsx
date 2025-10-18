import React, { useState, useEffect } from "react";
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
  const [usuarioEmail, setUsuarioEmail] = useState("");
  const [filtroCurso, setFiltroCurso] = useState("");
  const [filtroAsesor, setFiltroAsesor] = useState("");
  const [filtroTecnologia, setFiltroTecnologia] = useState("");
  const [menuAbierto, setMenuAbierto] = useState(null);

  // === Obtener correo del usuario autenticado ===
  useEffect(() => {
    try {
      const token = localStorage.getItem("id_token");
      if (token) {
        const payload = JSON.parse(atob(token.split(".")[1]));
        setUsuarioEmail(payload.email || payload.username || "desconocido@netec.com.mx");
      }
    } catch (err) {
      console.error("Error al obtener email del token:", err);
    }
  }, []);

  // === Filtros dinámicos ===
  const versionesFiltradas = versiones
    .filter((v) => {
      const matchCurso = v.nombre_curso?.toLowerCase().includes(filtroCurso.toLowerCase());
      const matchAsesor = !filtroAsesor || v.asesor_comercial === filtroAsesor;
      const matchTec = v.tecnologia?.toLowerCase().includes(filtroTecnologia.toLowerCase());
      return matchCurso && matchAsesor && matchTec;
    })
    .sort((a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion)); // más recientes primero

  const handleParamChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
  };

  // === Generar Temario ===
  const handleGenerar = async () => {
    if (!params.nombre_preventa || !params.asesor_comercial || !params.tecnologia || !params.tema_curso) {
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

      // ✅ Corrige la estructura del JSON de la Lambda
      let parsed;
      if (typeof data.body === "string") parsed = JSON.parse(data.body);
      else if (data.body) parsed = data.body;
      else parsed = data;

      if (parsed.temario) {
        console.log("✅ Temario generado:", parsed);
        setTemarioGenerado(parsed);
      } else {
        console.error("⚠️ Estructura no reconocida:", parsed);
        setError("La API respondió pero no se encontró el temario.");
      }
    } catch (err) {
      console.error("Error en generación:", err);
      setError("No se pudo generar el temario. Intenta nuevamente.");
    } finally {
      setIsLoading(false);
    }
  };

  // === Guardar versión ===
  const handleGuardarVersion = async (temarioParaGuardar) => {
    try {
      const token = localStorage.getItem("id_token");
      const bodyData = {
        cursoId: params.tema_curso,
        contenido: temarioParaGuardar,
        autor: usuarioEmail,
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
      if (!res.ok || !data.success) throw new Error(data.error || "Error al guardar versión");

      alert("✅ Versión guardada correctamente");
      await handleListarVersiones(); // 🔄 Refrescar lista
    } catch (error) {
      console.error(error);
      alert("❌ Error al guardar la versión");
    }
  };

  // === Listar versiones ===
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
      setVersiones(data.sort((a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion))); // más recientes
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
    }
  };

  // === Cargar versión seleccionada ===
  const handleCargarVersion = (version) => {
    setMostrarModal(false);
    setTimeout(() => setTemarioGenerado(version.contenido), 300);
  };

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Temarios a la Medida</h2>
        <p>Introduce los detalles para generar una propuesta de temario con Inteligencia Artificial.</p>

        {/* === FORMULARIO === */}
        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado</label>
            <input name="nombre_preventa" value={params.nombre_preventa} onChange={handleParamChange} />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial</label>
            <select name="asesor_comercial" value={params.asesor_comercial} onChange={handleParamChange}>
              <option value="">Selecciona un asesor</option>
              {asesoresComerciales.map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Tecnología</label>
            <input name="tecnologia" value={params.tecnologia} onChange={handleParamChange} placeholder="Ej: AWS, React" />
          </div>

          <div className="form-group">
            <label>Tema del Curso</label>
            <input name="tema_curso" value={params.tema_curso} onChange={handleParamChange} placeholder="Ej: Azure Functions" />
          </div>

          <div className="form-group">
            <label>Nivel</label>
            <select name="nivel_dificultad" value={params.nivel_dificultad} onChange={handleParamChange}>
              <option value="basico">Básico</option>
              <option value="intermedio">Intermedio</option>
              <option value="avanzado">Avanzado</option>
            </select>
          </div>

          <div className="form-group">
            <label>Sesiones (1-7)</label>
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

        <div className="form-group">
          <label>Sector / Audiencia</label>
          <textarea name="sector" value={params.sector} onChange={handleParamChange} placeholder="Ej: sector educativo, financiero..." />
        </div>

        <div className="form-group">
          <label>Enfoque Adicional</label>
          <textarea name="enfoque" value={params.enfoque} onChange={handleParamChange} placeholder="Ej: casos de uso, prácticas reales..." />
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

      {/* === Mostrar Temario === */}
      {temarioGenerado && <EditorDeTemario temario={temarioGenerado} onGuardar={() => handleGuardarVersion(temarioGenerado)} />}

      {/* === Modal Versiones === */}
      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="close-btn" onClick={() => setMostrarModal(false)}>✕</button>
            </div>

            <div className="filtros-versiones">
              <div className="filtro">
                <label>Curso</label>
                <input type="text" placeholder="Buscar curso..." value={filtroCurso} onChange={(e) => setFiltroCurso(e.target.value)} />
              </div>
              <div className="filtro">
                <label>Asesor</label>
                <select value={filtroAsesor} onChange={(e) => setFiltroAsesor(e.target.value)}>
                  <option value="">Todos</option>
                  {[...new Set(versiones.map((v) => v.asesor_comercial))].map((a, i) => (
                    <option key={i}>{a}</option>
                  ))}
                </select>
              </div>
              <div className="filtro">
                <label>Tecnología</label>
                <input type="text" placeholder="Ej: AWS, React..." value={filtroTecnologia} onChange={(e) => setFiltroTecnologia(e.target.value)} />
              </div>
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
                    <td className="menu-container">
                      <button className="menu-btn" onClick={() => setMenuAbierto(menuAbierto === i ? null : i)}>⋮</button>
                      {menuAbierto === i && (
                        <div className="menu-opciones">
                          <button onClick={() => handleCargarVersion(v)}>✏️ Editar</button>
                          <button onClick={() => alert("Exportar a PDF")}>📄 Exportar PDF</button>
                          <button onClick={() => alert("Exportar a Excel")}>📊 Exportar Excel</button>
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




