// src/components/GeneradorTemarios.jsx
import React, { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css";
import { exportarPDF } from "./EditorDeTemario";
import { useNavigate } from "react-router-dom";

const asesoresComerciales = [
  "Alejandra Galvez",
  "Ana Aragón",
  "Arely Alvarez",
  "Benjamin Araya",
  "Carolina Aguilar",
  "Cristian Centeno",
  "Elizabeth Navia",
  "Eonice Garfías",
  "Guadalupe Agiz",
  "Jazmin Soriano",
  "Lezly Durán",
  "Lusdey Trujillo",
  "Natalia García",
  "Natalia Gomez",
  "Vianey Miranda",
].sort();

// ✅ Unifica el algoritmo de cursoId (USAR SIEMPRE ESTE)
const makeCursoId = (tema = "") =>
  tema
    .trim()
    .toLowerCase()
    .replace(/[^\w]+/g, "_")
    .replace(/^_+|_+$/g, "");

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
    syllabus_text: "",
  });

  const navigate = useNavigate();
  const [userEmail, setUserEmail] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mostrandoModalThor, setMostrandoModalThor] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);

  // ✅ incluye filtro por nota
  const [filtros, setFiltros] = useState({
    curso: "",
    asesor: "",
    tecnologia: "",
    nota: "",
  });

  // --- URLs ---
  // (Dejo tus URLs como estaban, SOLO corrijo la de LISTAR porque /list NO existe)
  const generarApiUrl =
    "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/PruebadeTEMAR";

  // ✅ TU API real: stage = versiones, resource = /versiones
  // POST: /versiones/versiones
  const guardarApiUrl =
    "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

  // ✅ FIX: NO existe /list → listar debe ser GET al mismo recurso /versiones
  const listarApiUrl =
    "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

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

  // ✅ Token helper (Amplify -> fallback storage)
  const getBearerToken = async () => {
    try {
      const session = await fetchAuthSession();
      const t = session?.tokens?.idToken?.toString();
      if (t) return t;
    } catch (e) {
      console.warn("No se pudo obtener token desde Amplify:", e);
    }

    return (
      sessionStorage.getItem("id_token") ||
      localStorage.getItem("id_token") ||
      sessionStorage.getItem("idToken") ||
      localStorage.getItem("idToken") ||
      ""
    );
  };

  const handleParamChange = (e) => {
    const { name, value } = e.target;

    if (name === "objetivo_tipo") {
      let codigoCert = params.codigo_certificacion;
      if (value === "saber_hacer") codigoCert = "";
      setParams((prev) => ({
        ...prev,
        [name]: value,
        codigo_certificacion: codigoCert,
      }));
      return;
    }

    if (name === "horas_por_sesion" || name === "numero_sesiones_por_semana") {
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
      setError(
        "Completa todos los campos requeridos: Tecnología, Tema del Curso y Sector/Audiencia."
      );
      return;
    }

    if (params.objetivo_tipo === "certificacion" && !params.codigo_certificacion) {
      setError("Para certificación, debes especificar el código de certificación.");
      return;
    }

    const horasTotales = params.horas_por_sesion * params.numero_sesiones_por_semana;

    setIsLoading(true);
    setError("");
    setMostrandoModalThor(true);
    setTimeout(() => setMostrandoModalThor(false), 160000);

    try {
      const payload = { ...params, horas_totales: horasTotales };

      if (payload.objetivo_tipo !== "certificacion") delete payload.codigo_certificacion;

      const token = await getBearerToken();

      const response = await fetch(generarApiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        const errorMessage =
          typeof data.error === "object" ? JSON.stringify(data.error) : data.error;
        throw new Error(errorMessage || "Ocurrió un error en el servidor.");
      }

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
      setMostrandoModalThor(false);
    }
  };

  // ✅ Guardar versión (incluye cursoId + nota_version)
  const handleGuardarVersion = async (temarioParaGuardar, nota) => {
    try {
      const token = await getBearerToken();
      const cursoId = makeCursoId(params.tema_curso || "");

      const bodyData = {
        cursoId,
        contenido: temarioParaGuardar,
        nota_usuario: nota || "",
        nota_version: nota || `Guardado el ${new Date().toLocaleString()}`,
        autor: userEmail || "sin-correo",
        asesor_comercial: params.asesor_comercial || "",
        nombre_preventa: params.nombre_preventa || "",
        nombre_curso: params.tema_curso || "",
        tecnologia: params.tecnologia || "",
        enfoque: params.enfoque || "",
        fecha_creacion: new Date().toISOString(),
      };

      const res = await fetch(guardarApiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(bodyData),
      });

      const text = await res.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch {
        data = { raw: text };
      }

      if (!res.ok) {
        console.error("Guardar versión ->", res.status, data);
        throw new Error(data?.error || `Error HTTP ${res.status}`);
      }

      // ✅ refresca lista si modal está abierto
      if (mostrarModal) await handleListarVersiones();

      return {
        success: true,
        message: `Versión guardada ✔ (versionId: ${data.versionId || "ok"})`,
      };
    } catch (error) {
      console.error(error);
      return { success: false, message: error.message };
    }
  };

  // ✅ Listar versiones (GET al recurso /versiones, NO /list)
  const handleListarVersiones = async () => {
    try {
      setIsLoading(true);

      const token = await getBearerToken();

      if (!token) {
        console.error("⚠️ No hay token. Revisa Amplify o storage.");
        setVersiones([]);
        setMostrarModal(true);
        return;
      }

      const res = await fetch(listarApiUrl, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      const text = await res.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch {
        data = { raw: text };
      }

      if (!res.ok) {
        console.error("Listar versiones ->", res.status, data);
        throw new Error(data?.error || `HTTP ${res.status}`);
      }

      const items = Array.isArray(data) ? data : [];

      const sortedData = items.sort(
        (a, b) =>
          new Date(b.fecha_guardado || b.fecha_creacion || 0) -
          new Date(a.fecha_guardado || a.fecha_creacion || 0)
      );

      setVersiones(sortedData);
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
      setVersiones([]);
      setMostrarModal(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEditarVersion = (v) => {
    const id = v.versionId || v.version_id || v.id;
    const curso = v.cursoId || makeCursoId(v.nombre_curso || "") || "sin-id";

    if (!id) {
      console.error("⚠️ No se encontró versionId en:", v);
      return;
    }

    setMostrarModal(false);
    navigate(`/editor-temario/${curso}/${id}`);
  };

  const handleExportarPDF = async (version) => {
    try {
      setIsLoading(true);
      setError("");

      const token = await getBearerToken();
      const cursoId = version.cursoId || makeCursoId(version.nombre_curso || "");

      const apiUrl = `https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/Temario_PDF?id=${encodeURIComponent(
        cursoId
      )}&version=${encodeURIComponent(version.versionId)}`;

      const response = await fetch(apiUrl, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (!response.ok) {
        throw new Error(`Error al obtener datos del temario: ${response.status}`);
      }

      const data = await response.json();
      exportarPDF(data);
    } catch (err) {
      console.error("❌ Error exportando PDF:", err);
      setError("No se pudo generar el PDF. Intenta nuevamente.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFiltroChange = (e) => {
    const { name, value } = e.target;
    setFiltros((prev) => ({ ...prev, [name]: value }));
  };

  const limpiarFiltros = () => {
    setFiltros({ curso: "", asesor: "", tecnologia: "", nota: "" });
  };

  const versionesFiltradas = versiones.filter((v) => {
    const nombreCurso = (v.nombre_curso || "").toLowerCase();
    const tecnologia = (v.tecnologia || "").toLowerCase();
    const asesor = (v.asesor_comercial || "").toLowerCase();
    const nota = (v.nota_version || v.nota_usuario || v.nota || "").toLowerCase();

    return (
      nombreCurso.includes((filtros.curso || "").toLowerCase()) &&
      (filtros.asesor ? asesor === (filtros.asesor || "").toLowerCase() : true) &&
      tecnologia.includes((filtros.tecnologia || "").toLowerCase()) &&
      nota.includes((filtros.nota || "").toLowerCase())
    );
  });

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <div className="header-practico" style={{ marginBottom: "15px" }}>
          <h2>Generador de Temarios a la Medida</h2>
        </div>

        <p className="descripcion-practico" style={{ marginTop: "0px" }}>
          Introduce los detalles para generar una propuesta de temar
