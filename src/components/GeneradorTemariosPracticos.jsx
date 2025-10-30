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

function GeneradorTemariosPracticos() {
  const [params, setParams] = useState({
    nombre_preventa: "",
    asesor_comercial: "",
    tecnologia: "",
    tema_curso: "",
    nivel_dificultad: "basico",
    numero_sesiones: 1,
    horas_por_sesion: 7,
    objetivo_tipo: "saber_hacer",
    sector: "",
    enfoque: "",
    codigo_certificacion: "",
    syllabus_text: "",
  });

  const [userEmail, setUserEmail] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({ curso: "", asesor: "", tecnologia: "" });
  const [menuActivo, setMenuActivo] = useState(null);

  // === URLs de API ===
  const generarApiUrl = "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/tem_practico_openai";
  const guardarApiUrl = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

  // === Obtener usuario autenticado ===
  useEffect(() => {
    const getUser = async () => {
      try {
        const session = await fetchAuthSession();
        const idToken = session?.tokens?.idToken?.toString();
        const email = session?.tokens?.idToken?.payload?.email;
        if (idToken) localStorage.setItem("id_token", idToken);
        setUserEmail(email || "sin-correo");
      } catch (err) {
        console.error("Error obteniendo usuario:", err);
      }
    };
    getUser();
  }, []);

  // === Handlers generales ===
  const handleParamChange = (e) => {
    const { name, value } = e.target;

    if (name === "objetivo_tipo") {
      let codigoCert = params.codigo_certificacion;
      if (value === "saber_hacer") codigoCert = "";
      setParams((prev) => ({ ...prev, [name]: value, codigo_certificacion: codigoCert }));
      return;
    }

    if (name === "horas_por_sesion" || name === "numero_sesiones") {
      setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
      return;
    }

    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
  };

  // === Generar temario ===
  const handleGenerar = async () => {
    if (!params.tecnologia || !params.tema_curso || !params.sector) {
      setError("Completa los campos requeridos: Tecnología, Tema del Curso y Sector/Audiencia.");
      return;
    }

    if (params.objetivo_tipo === "certificacion" && !params.codigo_certificacion) {
      setError("Para certificación, debes especificar el código de certificación.");
      return;
    }

    const horasTotales = params.horas_por_sesion * params.numero_sesiones;

    setIsLoading(true);
    setError("");

    try {
      const payload = {
        ...params,
        duracion_total_horas: horasTotales,
        autor: userEmail, // ✅ NUEVO: se envía el autor a Lambda
      };

      if (payload.objetivo_tipo !== "certificacion") delete payload.codigo_certificacion;

      const token = localStorage.getItem("id_token");
      const response = await fetch(generarApiUrl, {
        method: "POST",
        mode: "cors",
        credentials: "omit",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Error en el servidor");

      const temarioCompleto = {
        ...data,
        nombre_preventa: params.nombre_preventa,
        asesor_comercial: params.asesor_comercial,
        duracion_total_horas: horasTotales,
        enfoque: params.enfoque,
        tecnologia: params.tecnologia,
        tema_curso: params.tema_curso,
      };

      setTemarioGenerado(temarioCompleto);
    } catch (err) {
      console.error("Error:", err);
      setError(err.message || "No se pudo generar el temario. Intenta nuevamente.");
    } finally {
      setIsLoading(false);
    }
  };

  // === Guardar versión ===
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

      return { success: true, message: `Versión guardada ✔ (${data.versionId})` };
    } catch (error) {
      console.error(error);
      return { success: false, message: error.message };
    }
  };

  // === Listar versiones ===
  const handleListarVersiones = async () => {
    try {
      const token = localStorage.getItem("id_token");
      const queryParams = new URLSearchParams();
      if (filtros.curso) queryParams.append("curso", filtros.curso);
      if (filtros.tecnologia) queryParams.append("tecnologia", filtros.tecnologia);
      if (filtros.nivel) queryParams.append("nivel", filtros.nivel);

      const url = `${guardarApiUrl}?${queryParams.toString()}`; // ✅ NUEVO: usa la URL de versiones, no la de generación

      const res = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json();
      if (!Array.isArray(data)) throw new Error("Respuesta inesperada del servidor");

      const sortedData = data.sort(
        (a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion)
      );
      setVersiones(sortedData);
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
    }
  };

  // === Editar versión existente (PUT) ===
  const handleEditarVersion = async (version) => { // ✅ NUEVO
    try {
      const token = localStorage.getItem("id_token");
      const body = {
        id: version.id,
        nombre_curso: version.nombre_curso,
        tecnologia: version.tecnologia,
        asesor_comercial: version.asesor_comercial,
        autor: userEmail,
        nombre_preventa: version.nombre_preventa || params.nombre_preventa,
      };

      const res = await fetch(guardarApiUrl, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error al actualizar versión");

      alert("✅ Versión actualizada correctamente");
      await handleListarVersiones();
    } catch (error) {
      console.error("Error al editar versión:", error);
      alert("⚠️ No se pudo editar la versión.");
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
      tecnologia.toLowerCase().includes(filtros.tecnologia.toLowerCase()) &&
      (filtros.asesor ? asesor === filtros.asesor : true)
    );
  });

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Temarios Prácticos</h2>
        <p>Introduce los detalles para generar una propuesta práctica con IA.</p>

        {/* === formulario principal igual === */}
        {/* === ... omitido por brevedad ... */}

        <div className="botones">
          <button className="btn-generar" onClick={handleGenerar} disabled={isLoading}>
            {isLoading ? "Generando..." : "Generar Propuesta de Temario"}
          </button>
          <button className="btn-versiones" onClick={handleListarVersiones} disabled={isLoading}>
            Ver Versiones Guardadas
          </button>
        </div>

        {error && <div className="error-message"><span>⚠️</span> {error}</div>}
      </div>

      {temarioGenerado && (
        <EditorDeTemario temarioInicial={temarioGenerado} onSave={handleGuardarVersion} onRegenerate={handleGenerar} isLoading={isLoading} />
      )}

      {/* === MODAL DE VERSIONES === */}
      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setMostrarModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="filtros-versiones">
                <input type="text" placeholder="Filtrar por curso" name="curso" value={filtros.curso} onChange={handleFiltroChange} />
                <select name="asesor" value={filtros.asesor} onChange={handleFiltroChange}>
                  <option value="">Todos los asesores</option>
                  {asesoresComerciales.map((a) => <option key={a}>{a}</option>)}
                </select>
                <input type="text" placeholder="Filtrar por tecnología" name="tecnologia" value={filtros.tecnologia} onChange={handleFiltroChange} />
                <button className="btn-secundario" onClick={limpiarFiltros}>Limpiar</button>
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
                      <tr key={v.id || i}>
                        <td>{v.nombre_curso}</td>
                        <td>{v.tecnologia}</td>
                        <td>{v.asesor_comercial}</td>
                        <td>{new Date(v.fecha_creacion).toLocaleString()}</td>
                        <td>{v.autor}</td>
                        <td className="acciones-cell">
                          <button className="menu-btn" onClick={() => setMenuActivo(menuActivo === i ? null : i)}>⋮</button>
                          {menuActivo === i && (
                            <div className="menu-opciones">
                              <button onClick={() => handleEditarVersion(v)}>✏️ Editar</button> {/* ✅ NUEVO */}
                              <button onClick={() => console.log("Exportar PDF", v)}>📄 Exportar PDF</button>
                              <button onClick={() => handleCargarVersion(v)}>👁️ Ver</button>
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
