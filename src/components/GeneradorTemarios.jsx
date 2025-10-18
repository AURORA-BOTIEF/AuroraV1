import React, { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
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

  const [userEmail, setUserEmail] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({ curso: "", asesor: "", tecnologia: "" });
  const [menuActivo, setMenuActivo] = useState(null);

  // 🔹 Obtener correo del usuario autenticado
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
      const enfoqueAuto =
        value === "saber_hacer"
          ? "Enfocado en el desarrollo de habilidades prácticas y resolución de problemas reales."
          : "Enfocado en la preparación para aprobar un examen de certificación.";
      setParams((prev) => ({ ...prev, [name]: value, enfoque: enfoqueAuto }));
      return;
    }
    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
  };

  // 🔹 Generar temario IA
  const handleGenerar = async () => {
    if (!params.nombre_preventa || !params.asesor_comercial || !params.tecnologia || !params.tema_curso || !params.sector) {
      setError("Completa todos los campos requeridos antes de continuar (incluye Sector/Audiencia).");
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

  // 🔹 Guardar versión
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

  // 🔹 Listar versiones guardadas
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

  // ===================================================
  // ======    INTERFAZ PRINCIPAL DEL GENERADOR    =====
  // ===================================================
  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Temarios a la Medida</h2>
        <p>Introduce los detalles para generar una propuesta de temario con Inteligencia Artificial.</p>

        {/* === FORMULARIO PRINCIPAL === */}
        <div className="form-grid">
          {/* Campos principales */}
          {[
            { label: "Nombre Preventa Asociado", name: "nombre_preventa" },
            { label: "Tecnología", name: "tecnologia", placeholder: "Ej: AWS, React, Python" },
            { label: "Tema Principal del Curso", name: "tema_curso", placeholder: "Ej: Arquitecturas Serverless" },
            { label: "Sector / Audiencia", name: "sector", type: "textarea", placeholder: "Ej: Personas del sector financiero..." },
          ].map((f) => (
            <div key={f.name} className="form-group">
              <label>{f.label}</label>
              {f.type === "textarea" ? (
                <textarea name={f.name} value={params[f.name]} onChange={handleParamChange} disabled={isLoading} placeholder={f.placeholder} />
              ) : (
                <input name={f.name} value={params[f.name]} onChange={handleParamChange} disabled={isLoading} placeholder={f.placeholder} />
              )}
            </div>
          ))}

          <div className="form-group">
            <label>Asesor(a) Comercial Asociado</label>
            <select name="asesor_comercial" value={params.asesor_comercial} onChange={handleParamChange} disabled={isLoading}>
              <option value="">Selecciona un asesor(a)</option>
              {asesoresComerciales.map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="botones">
          <button className="btn-generar" onClick={handleGenerar} disabled={isLoading}>
            {isLoading ? "Generando..." : "Generar Propuesta de Temario"}
          </button>
          <button className="btn-versiones" onClick={handleListarVersiones} disabled={isLoading}>
            Ver Versiones Guardadas
          </button>
        </div>

        {error && <p className="error">{error}</p>}
      </div>

      {/* === EDITOR === */}
      {temarioGenerado && (
        <EditorDeTemario temarioInicial={temarioGenerado} onSave={handleGuardarVersion} isLoading={isLoading} />
      )}

      {/* === MODAL DE VERSIONES === */}
      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="close-btn" onClick={() => setMostrarModal(false)}>✕</button>
            </div>
            <div className="filtros-versiones">
              <input type="text" name="curso" placeholder="Buscar curso..." value={filtros.curso} onChange={handleFiltroChange} />
              <select name="asesor" value={filtros.asesor} onChange={handleFiltroChange}>
                <option value="">Todos los asesores</option>
                {asesoresComerciales.map((a) => (
                  <option key={a}>{a}</option>
                ))}
              </select>
              <input type="text" name="tecnologia" placeholder="Ej: AWS, React..." value={filtros.tecnologia} onChange={handleFiltroChange} />
              <button className="btn-versiones" onClick={limpiarFiltros}>Limpiar</button>
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
                      <button className="menu-btn" onClick={() => setMenuActivo(menuActivo === i ? null : i)}>⋮</button>
                      {menuActivo === i && (
                        <div className="menu-opciones">
                          <button onClick={() => handleCargarVersion(v)}>✏️ Editar</button>
                          <button onClick={() => alert("📄 Exportar PDF pronto disponible")}>📄 Exportar PDF</button>
                          <button onClick={() => alert("📊 Exportar Excel pronto disponible")}>📊 Exportar Excel</button>
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




