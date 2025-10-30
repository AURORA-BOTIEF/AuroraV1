import React, { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css"; // Asegúrate que este CSS sea el del generador 'Practicos'

const asesoresComerciales = [
  "Alejandra Galvez", "Ana Aragón", "Arely Alvarez", "Benjamin Araya",
  "Carolina Aguilar", "Cristian Centeno", "Elizabeth Navia", "Eonice Garfías",
  "Guadalupe Agiz", "Jazmin Soriano", "Lezly Durán", "Lusdey Trujillo",
  "Natalia García", "Natalia Gomez", "Vianey Miranda",
].sort();

// --- AJUSTE 1: Se renombra el componente ---
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
    codigo_certificacion: "",
    syllabus_text: "", // Inicializa el campo syllabus_text
  });

  const [userEmail, setUserEmail] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({ curso: "", asesor: "", tecnologia: "" });
  const [menuActivo, setMenuActivo] = useState(null);

  const generarApiUrl = "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/PruebadeTEMAR";
  const guardarApiUrl = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

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
      let codigoCert = params.codigo_certificacion;
      if (value === "saber_hacer") {
        codigoCert = "";
      }
      setParams((prev) => ({ 
        ...prev, 
        [name]: value, 
        codigo_certificacion: codigoCert 
      }));
      return;
    }

    if (name === 'horas_por_sesion' || name === 'numero_sesiones_por_semana') {
      setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
      return;
    }
    
    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSliderChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: parseInt(value) }));
  };

  const handleGenerar = async () => {
    if (!params.tecnologia || !params.tema_curso || !params.sector) {
      setError("Completa todos los campos requeridos: Tecnología, Tema del Curso y Sector/Audiencia.");
      return;
    }

    if (params.objetivo_tipo === "certificacion" && !params.codigo_certificacion) {
      setError("Para certificación, debes especificar el código de certificación.");
      return;
    }

    const horasTotales = params.horas_por_sesion * params.numero_sesiones_por_semana;
    setIsLoading(true);
    setError("");

    try {
      const payload = {
        ...params,
        horas_totales: horasTotales, 
      };

      if (payload.objetivo_tipo !== 'certificacion') {
        delete payload.codigo_certificacion;
      }

      console.log("Enviando payload:", payload);

      const token = localStorage.getItem("id_token");
      const response = await fetch(generarApiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        const errorMessage = typeof data.error === 'object' ? JSON.stringify(data.error) : data.error;
        throw new Error(errorMessage || "Ocurrió un error en el servidor.");
      }
      console.log("✅ Respuesta recibida:", data);

      const temarioCompleto = {
        ...data,
        nombre_preventa: params.nombre_preventa,
        asesor_comercial: params.asesor_comercial,
        horas_totales: horasTotales,
        enfoque: params.enfoque,
        tecnologia: params.tecnologia,
        tema_curso: params.tema_curso,
      };
      setTemarioGenerado(temarioCompleto);

    } catch (err) {
      console.error("❌ Error:", err);
      setError(err.message || "No se pudo generar el temario. Intenta nuevamente.");
    } finally {
      setIsLoading(false);
    }
  };

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

      return { success: true, message: `Versión guardada ✔ (versionId: ${data.versionId})` };
    } catch (error) {
      console.error(error);
      return { success: false, message: error.message };
    }
  };

  const handleListarVersiones = async () => {
    try {
      const token = localStorage.getItem("id_token");
      const res = await fetch(guardarApiUrl, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json();
      const sortedData = data.sort((a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion));
      setVersiones(sortedData);
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
    }
  };

  const handleCargarVersion = (version) => {
    setMostrarModal(false);
    setParams(prev => ({
        ...prev,
        nombre_preventa: version.nombre_preventa || "",
        asesor_comercial: version.asesor_comercial || "",
        tecnologia: version.tecnologia || "",
        tema_curso: version.nombre_curso || "",
        enfoque: version.enfoque || "",
        nivel_dificultad: version.contenido?.nivel_dificultad || 'basico',
        sector: version.contenido?.sector || '',
    }));
    setTimeout(() => setTemarioGenerado(version.contenido), 300);
  };

  // ✅ CORREGIDO: Exportar PDF sin romper flujo
  const handleExportarPDF = async (version) => {
    try {
      setIsLoading(true);
      setError("");
      const token = localStorage.getItem("id_token");

      const apiUrl = `https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/Temario_PDF?id=${encodeURIComponent(
        version.nombre_curso
      )}&version=${encodeURIComponent(version.versionId)}`;

      console.log("📡 Solicitando datos a:", apiUrl);
      const response = await fetch(apiUrl, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error(`Error al obtener datos del temario: ${response.status}`);

      const data = await response.json();
      console.log("✅ Datos recibidos desde Lambda:", data);

      if (typeof window.exportarPDF === "function") {
        window.exportarPDF(data);
      } else {
        console.warn("⚠️ exportarPDF no disponible. Mostrando JSON...");
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
      }
    } catch (err) {
      console.error("❌ Error exportando PDF:", err);
      setError("No se pudo generar el PDF. Intenta nuevamente.");
    } finally {
      setIsLoading(false);
    }
  };

  // ✅ NUEVO BLOQUE: prevenir error "handleVerVersion is not defined"
  const handleVerVersion = (version) => {
    console.log("👁️ Vista previa de versión:", version);
    alert(`Vista previa del curso: ${version.nombre_curso}\nVersión: ${version.versionId}`);
  };

  const handleFiltroChange = (e) => {
    const { name, value } = e.target;
    setFiltros((prev) => ({ ...prev, [name]: value }));
  };

  const limpiarFiltros = () => setFiltros({ curso: "", asesor: "", tecnologia: "" });

  const versionesFiltradas = versiones.filter((v) => {
    const nombreCurso = v.nombre_curso || '';
    const tecnologia = v.tecnologia || '';
    const asesor = v.asesor_comercial || '';

    return (
      nombreCurso.toLowerCase().includes(filtros.curso.toLowerCase()) &&
      (filtros.asesor ? asesor === filtros.asesor : true) &&
      tecnologia.toLowerCase().includes(filtros.tecnologia.toLowerCase())
    );
  });

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        {/* ✅ TODO TU FORMULARIO ORIGINAL AQUÍ SIN CAMBIOS */}
        {/* ... */}
      </div>

      {temarioGenerado && (
        <EditorDeTemario 
          temarioInicial={temarioGenerado} 
          onSave={handleGuardarVersion} 
          onRegenerate={handleGenerar}
          isLoading={isLoading}
        />
      )}

      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setMostrarModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              {/* 🔹 Tu tabla original sin tocar */}
              {/* ... */}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default GeneradorTemarios;
