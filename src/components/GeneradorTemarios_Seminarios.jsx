// src/components/GeneradorTemarios_Seminarios.jsx
import React, { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import { useNavigate } from "react-router-dom";
import jsPDF from "jspdf"; // para exportar desde historial
import EditorDeTemario_seminario from "./EditorDeTemario_seminario";
import "./GeneradorTemarios.css";

// === URLs de tus APIs ===
const generarApiUrl =
  "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/temario_seminario";
const guardarApiUrl =
  "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

// === Asesores Comerciales ===
const asesoresComerciales = [
  "Alejandra Galvez", "Ana Aragón", "Arely Alvarez", "Benjamin Araya",
  "Carolina Aguilar", "Cristian Centeno", "Elizabeth Navia", "Eonice Garfías",
  "Guadalupe Agiz", "Jazmin Soriano", "Lezly Durán", "Lusdey Trujillo",
  "Natalia García", "Natalia Gomez", "Vianey Miranda",
].sort();

export default function GeneradorTemarios_Seminarios() {
  const [params, setParams] = useState({
    nombre_preventa: "",
    asesor_comercial: "",
    tecnologia: "",
    tema_curso: "",
    nivel_dificultad: "basico",
    objetivo_tipo: "saber_hacer",
    codigo_certificacion: "",
    sector: "",
    enfoque: "",
    horas_por_sesion: 2,
  });

  const [userEmail, setUserEmail] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);

  const navigate = useNavigate(); // ✅ Para redirigir al editor

  // === Obtener email del usuario autenticado ===
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

  // === Manejo de cambios del formulario ===
  const handleChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({
      ...prev,
      [name]: name === "horas_por_sesion" ? parseFloat(value) : value,
    }));
  };

  // === Validación básica ===
  const validate = () => {
    const required = ["tecnologia", "tema_curso", "sector"];
    const missing = required.filter((f) => !params[f]?.trim());
    if (missing.length) return `Completa: ${missing.join(", ")}.`;
    if (params.objetivo_tipo === "certificacion" && !params.codigo_certificacion.trim())
      return "Debes indicar el código de certificación.";
    return "";
  };

  // === Generar seminario (Lambda IA) ===
  const handleGenerar = async () => {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const payload = {
        tecnologia: params.tecnologia.trim(),
        tema_curso: params.tema_curso.trim(),
        nivel_dificultad: params.nivel_dificultad,
        objetivo_tipo: params.objetivo_tipo,
        sector: params.sector.trim(),
        enfoque: params.enfoque.trim(),
        duracion_total_horas: params.horas_por_sesion,
        nombre_preventa: params.nombre_preventa.trim(),
        asesor_comercial: params.asesor_comercial.trim(),
      };

      const res = await fetch(generarApiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error al generar el seminario.");

      const temarioCompleto = {
        nombre_curso: data.nombre_curso || "Seminario sin título",
        descripcion_general: data.descripcion_general || "Sin descripción generada",
        objetivos_generales: Array.isArray(data.objetivos_generales)
          ? data.objetivos_generales
          : [],
        temario: Array.isArray(data.temario) ? data.temario : [],
        _metadata: data._metadata || {},
        nombre_preventa: params.nombre_preventa,
        asesor_comercial: params.asesor_comercial,
        horas_totales: params.horas_por_sesion,
        tecnologia: params.tecnologia,
        tema_curso: params.tema_curso,
      };

      setTemarioGenerado(temarioCompleto);
    } catch (err) {
      console.error("❌ Error:", err);
      setError(err.message || "No se pudo generar el temario.");
    } finally {
      setIsLoading(false);
    }
  };

  // === Guardar versión (DynamoDB) ===
  const handleGuardarVersion = async (temarioParaGuardar, nota) => {
    try {
      const body = {
        cursoId: params.tema_curso.trim().toLowerCase().replace(/\s+/g, "_"),
        contenido: temarioParaGuardar,
        nota_version: nota || `Guardado el ${new Date().toLocaleString()}`,
        autor: userEmail || "Desconocido",
        asesor_comercial: params.asesor_comercial || "No asignado",
        nombre_preventa: params.nombre_preventa || "No especificado",
        nombre_curso: params.tema_curso || "Sin título",
        tecnologia: params.tecnologia || "No especificada",
        fecha_creacion: new Date().toISOString(),
      };

      const res = await fetch(guardarApiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error al guardar versión");

      alert(`✅ Versión guardada (ID: ${data.versionId})`);
    } catch (err) {
      console.error(err);
      alert("❌ " + err.message);
    }
  };

  // === Listar versiones (modal) ===
  const handleListarVersiones = async () => {
    try {
      const res = await fetch(guardarApiUrl);
      const data = await res.json();
      const sorted = data.sort(
        (a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion)
      );
      setVersiones(sorted);
      setMostrarModal(true);
    } catch (err) {
      console.error("Error al listar versiones:", err);
    }
  };

  // ✅ Editar versión existente
  const handleEditarVersion = (v) => {
    navigate(`/editor-seminario/${v.cursoId}/${v.versionId}`);
  };

  // ✅ Exportar PDF directo desde historial
  const handleExportarDesdeHistorial = async (v) => {
    try {
      const res = await fetch(
        `https://tu-api-get-version.amazonaws.com/dev/get?id=${v.cursoId}&version=${v.versionId}`
      );
      const data = await res.json();
      const temario = data.contenido;

      const doc = new jsPDF();
      doc.setFont("helvetica", "normal");
      doc.text(temario.nombre_curso || "Seminario", 15, 20);
      doc.text(
        "Documento generado mediante tecnología de IA bajo la supervisión de Netec.",
        15,
        280
      );
      doc.save(`${temario.nombre_curso || "seminario"}.pdf`);
    } catch (err) {
      console.error("Error exportando PDF:", err);
    }
  };

  return (
    <div className="contenedor-generador">
      <div className="card-generador">
        <h2>Generador de Temarios - Seminarios</h2>
        <p>Genera un temario profesional con IA.</p>

        {/* formulario */}
        {/* ... todo tu formulario original ... */}

        <div className="botones">
          <button className="btn-generar" onClick={handleGenerar} disabled={isLoading}>
            {isLoading ? "Generando..." : "Generar Propuesta"}
          </button>
          <button className="btn-versiones" onClick={handleListarVersiones}>
            Ver Versiones Guardadas
          </button>
        </div>
      </div>

      {/* Editor de temario */}
      {temarioGenerado && (
        <EditorDeTemario_seminario
          temarioInicial={temarioGenerado}
          onSave={handleGuardarVersion}
          isLoading={isLoading}
        />
      )}

      {/* Modal versiones */}
      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setMostrarModal(false)}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              {versiones.length === 0 ? (
                <p>No hay versiones guardadas.</p>
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
                    {versiones.map((v, i) => (
                      <tr key={i}>
                        <td>{v.nombre_curso}</td>
                        <td>{v.tecnologia}</td>
                        <td>{v.asesor_comercial}</td>
                        <td>{new Date(v.fecha_creacion).toLocaleString()}</td>
                        <td>{v.autor}</td>
                        <td>
                          <button onClick={() => handleEditarVersion(v)}>📝</button>
                          <button onClick={() => handleExportarDesdeHistorial(v)}>📄</button>
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
