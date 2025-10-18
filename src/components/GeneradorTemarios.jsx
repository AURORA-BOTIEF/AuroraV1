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

  const [userEmail, setUserEmail] = useState(""); // ✅ NUEVO
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({ curso: "", asesor: "", tecnologia: "" });
  const [menuActivo, setMenuActivo] = useState(null);

  // ✅ OBTENER EMAIL DEL USUARIO AUTENTICADO
  useEffect(() => {
    const getUser = async () => {
      try {
        const session = await fetchAuthSession();
        const email = session?.tokens?.idToken?.payload?.email;
        console.log("📧 Usuario autenticado:", email);
        setUserEmail(email || "sin-correo");
      } catch (err) {
        console.error("Error obteniendo usuario:", err);
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

  // ✅ GUARDA VERSIÓN CORRECTAMENTE CON userEmail
  const handleGuardarVersion = async (temarioParaGuardar) => {
    try {
      const token = localStorage.getItem("id_token");
      const bodyData = {
        cursoId: params.tema_curso,
        contenido: temarioParaGuardar,
        autor: userEmail, // ✅ CORREGIDO
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

  const handleActualizarVersiones = () => handleListarVersiones();

  const handleCargarVersion = (version) => {
    setMostrarModal(false);
    setTimeout(() => setTemarioGenerado(version.contenido), 300);
  };

  const handleExportar = (version, tipo) => {
    setMostrarModal(false);
    setTimeout(() => {
      setTemarioGenerado(version.contenido);
      setTimeout(() => {
        document.querySelector(".btn-secundario:nth-child(3)")?.click();
      }, 600);
    }, 300);
  };

  const handleFiltroChange = (e) => {
    const { name, value } = e.target;
    setFiltros((prev) => ({ ...prev, [name]: value }));
  };

  const limpiarFiltros = () => setFiltros({ curso: "", asesor: "", tecnologia: "" });

  const versionesFiltradas = versiones.filter((v) => (
    v.nombre_curso.toLowerCase().includes(filtros.curso.toLowerCase()) &&
    (filtros.asesor ? v.asesor_comercial === filtros.asesor : true) &&
    v.tecnologia.toLowerCase().includes(filtros.tecnologia.toLowerCase())
  ));

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Temarios a la Medida</h2>
        <p>Introduce los detalles para generar una propuesta de temario con Inteligencia Artificial.</p>

        {/* Formulario */}
        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado</label>
            <input name="nombre_preventa" value={params.nombre_preventa} onChange={handleParamChange} disabled={isLoading} />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial Asociado</label>
            <select name="asesor_comercial" value={params.asesor_comercial} onChange={handleParamChange} disabled={isLoading}>
              <option value="">Selecciona un asesor(a)</option>
              {asesoresComerciales.map((a) => <option key={a}>{a}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label>Tecnología</label>
            <input name="tecnologia" value={params.tecnologia} onChange={handleParamChange} disabled={isLoading} placeholder="Ej: AWS, React, Python" />
          </div>

          <div className="form-group">
            <label>Tema Principal del Curso</label>
            <input name="tema_curso" value={params.tema_curso} onChange={handleParamChange} disabled={isLoading} placeholder="Ej: Arquitecturas Serverless" />
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
            <label>Número de Sesiones (1–7)</label>
            <div className="slider-container">
              <input type="range" min="1" max="7" name="numero_sesiones_por_semana" value={params.numero_sesiones_por_semana} onChange={handleSliderChange} disabled={isLoading} />
              <span>{params.numero_sesiones_por_semana} sesión</span>
            </div>
          </div>

          <div className="form-group">
            <label>Horas por Sesión (4–12)</label>
            <div className="slider-container">
              <input type="range" min="4" max="12" name="horas_por_sesion" value={params.horas_por_sesion} onChange={handleSliderChange} disabled={isLoading} />
              <span>{params.horas_por_sesion} horas</span>
            </div>
          </div>
        </div>

        <div className="form-group-radio">
          <label>Tipo de Objetivo</label>
          <div>
            <label><input type="radio" name="objetivo_tipo" value="saber_hacer" checked={params.objetivo_tipo === "saber_hacer"} onChange={handleParamChange} disabled={isLoading} /> Saber Hacer</label>
            <label><input type="radio" name="objetivo_tipo" value="certificacion" checked={params.objetivo_tipo === "certificacion"} onChange={handleParamChange} disabled={isLoading} /> Certificación</label>
          </div>
        </div>

        <div className="form-group">
          <label>Sector / Audiencia</label>
          <textarea name="sector" value={params.sector} onChange={handleParamChange} disabled={isLoading} placeholder="Ej: Personas del sector financiero que quieren ocupar Kanban" />
        </div>

        <div className="form-group">
          <label>Enfoque Adicional (Opcional)</label>
          <textarea name="enfoque" value={params.enfoque} onChange={handleParamChange} disabled={isLoading} placeholder="Ej: Orientado a patrones de diseño..." />
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

      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}
          onRegenerate={handleGenerar}
          onSave={handleGuardarVersion}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}

export default GeneradorTemarios;


