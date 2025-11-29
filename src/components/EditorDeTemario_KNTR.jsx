import React, { useState, useEffect } from "react";
import jsPDF from "jspdf";
import { fetchAuthSession } from "aws-amplify/auth";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario_KNTR.css";
import { Plus, Trash2 } from "lucide-react";

// 🔹 Convierte minutos en formato legible (ej: "1 hr 6 min")
const formatDuration = (minutos) => {
  if (!minutos || minutos < 0) return "0 min";
  const horas = Math.floor(minutos / 60);
  const mins = minutos % 60;
  if (horas === 0) return `${mins} min`;
  if (mins === 0) return `${horas} hr`;
  return `${horas} hr ${mins} min`;
};

const toDataURL = async (url) => {
  const res = await fetch(url);
  const blob = await res.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
};

const slugify = (str = "") =>
  String(str)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "curso";

function EditorDeTemario_KNTR({ temarioInicial, onSave, isLoading }) {
  const [temario, setTemario] = useState(() => ({
    ...temarioInicial,
    temario: Array.isArray(temarioInicial?.temario)
      ? temarioInicial.temario
      : [],
  }));
  const [userEmail, setUserEmail] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: "", texto: "" });
  const [modalExportar, setModalExportar] = useState(false);
  const [exportTipo, setExportTipo] = useState("pdf");

  useEffect(() => {
    const getUser = async () => {
      try {
        const session = await fetchAuthSession();
        const email = session?.tokens?.idToken?.payload?.email;
        setUserEmail(email || "sin-correo");
      } catch (err) {
        console.error("Error obteniendo usuario:", err);
      }
    };
    getUser();
  }, []);

  useEffect(() => {
    setTemario({
      ...temarioInicial,
      temario: Array.isArray(temarioInicial?.temario)
        ? temarioInicial.temario
        : [],
    });
  }, [temarioInicial]);

  // ===== CAMBIO DE CAMPOS =====
  const handleFieldChange = (capIndex, subIndex, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) nuevo.temario = [];
    if (!nuevo.temario[capIndex]) return;

    if (subIndex === null) {
      // 🔹 Estamos modificando un campo del capítulo
      nuevo.temario[capIndex][field] = value;

      // 🔹 Si el usuario edita la duración total manualmente
      if (field === "tiempo_capitulo_min") {
        const nuevoTotal = parseInt(value, 10) || 0;
        nuevo.temario[capIndex].tiempo_capitulo_min = nuevoTotal;

        // 🟢 Repartir equitativamente entre subcapítulos existentes
        const subcaps = nuevo.temario[capIndex].subcapitulos || [];
        if (subcaps.length > 0) {
          const minutosPorSub = Math.floor(nuevoTotal / subcaps.length);
          const residuo = nuevoTotal % subcaps.length;

          subcaps.forEach((sub, idx) => {
            sub.tiempo_subcapitulo_min =
              minutosPorSub + (idx === 0 ? residuo : 0); // reparte residuo al primero
          });
        }
      } else {
        // 🔹 Si el usuario edita otro campo (nombre, objetivos, etc.)
        // recalculamos la duración total según los subcapítulos actuales
        nuevo.temario[capIndex].tiempo_capitulo_min = (
          nuevo.temario[capIndex].subcapitulos || []
        ).reduce(
          (sum, s) => sum + (parseInt(s.tiempo_subcapitulo_min) || 0),
          0
        );
      }
    } else {
      // 🔹 Estamos modificando un campo de un subcapítulo
      if (!Array.isArray(nuevo.temario[capIndex].subcapitulos))
        nuevo.temario[capIndex].subcapitulos = [];
      if (typeof nuevo.temario[capIndex].subcapitulos[subIndex] !== "object") {
        nuevo.temario[capIndex].subcapitulos[subIndex] = {
          nombre:
            String(nuevo.temario[capIndex].subcapitulos[subIndex]) || "Tema",
        };
      }

      nuevo.temario[capIndex].subcapitulos[subIndex][field] =
        field.includes("tiempo") || field === "sesion"
          ? parseInt(value, 10) || 0
          : value;

      // 🔹 Al cambiar un subcapítulo, recalculamos la duración total automáticamente
      nuevo.temario[capIndex].tiempo_capitulo_min = (
        nuevo.temario[capIndex].subcapitulos || []
      ).reduce(
        (sum, s) => sum + (parseInt(s.tiempo_subcapitulo_min) || 0),
        0
      );
    }

    setTemario(nuevo);
  };

  // ===== AGREGAR CAPÍTULO =====
  const agregarCapitulo = () => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) nuevo.temario = [];
    nuevo.temario.push({
      capitulo: `Nuevo capítulo ${nuevo.temario.length + 1}`,
      tiempo_capitulo_min: 0,
      objetivos_capitulo: "",
      subcapitulos: [
        { nombre: "Nuevo tema 1", tiempo_subcapitulo_min: 30, sesion: 1 },
      ],
    });
    setTemario(nuevo);
  };

  // ===== ELIMINAR CAPÍTULO =====
  const eliminarCapitulo = (capIndex) => {
    if (
      !window.confirm(
        `¿Seguro que deseas eliminar el capítulo ${capIndex + 1
        } y todos sus temas?`
      )
    )
      return;

    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.splice(capIndex, 1);
    // Renumera capítulos restantes
    nuevo.temario = nuevo.temario.map((c, i) => ({
      ...c,
      capitulo: c.capitulo || `Capítulo ${i + 1}`,
    }));
    setTemario(nuevo);
    setMensaje({ tipo: "ok", texto: "🗑️ Capítulo eliminado" });
  };

  // ===== AGREGAR TEMA =====
  const agregarTema = (capIndex) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) return;
    if (!Array.isArray(nuevo.temario[capIndex].subcapitulos))
      nuevo.temario[capIndex].subcapitulos = [];
    nuevo.temario[capIndex].subcapitulos.push({
      nombre: `Nuevo tema ${nuevo.temario[capIndex].subcapitulos.length + 1}`,
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevo);
  };

  // ===== ELIMINAR TEMA =====
  const eliminarTema = (capIndex, subIndex) => {
    if (!window.confirm("¿Seguro que deseas eliminar este tema?")) return;
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario[capIndex].subcapitulos.splice(subIndex, 1);
    setTemario(nuevo);
    setMensaje({ tipo: "ok", texto: "🗑️ Tema eliminado correctamente" });
  };


  // ===== AJUSTAR TIEMPOS =====
  const ajustarTiempos = () => {
    if (!Array.isArray(temario.temario) || temario.temario.length === 0) return;
    const horas = temario?.horas_por_sesion || 2;
    const minutosTotales = horas * 60;
    const totalTemas = temario.temario.reduce(
      (acc, cap) => acc + (cap.subcapitulos?.length || 0),
      0
    );
    if (totalTemas === 0) return;
    const minutosPorTema = Math.floor(minutosTotales / totalTemas);
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.forEach((cap) => {
      if (!Array.isArray(cap.subcapitulos)) cap.subcapitulos = [];
      cap.subcapitulos.forEach((sub) => {
        sub.tiempo_subcapitulo_min = minutosPorTema;
      });
      cap.tiempo_capitulo_min = cap.subcapitulos.reduce(
        (a, s) => a + (s.tiempo_subcapitulo_min || 0),
        0
      );
    });
    setTemario(nuevo);
    setMensaje({ tipo: "ok", texto: `⏱️ Tiempos ajustados a ${horas}h` });
  };

  // ===== GUARDAR ===== (corregido para evitar 400)
  const handleSaveClick = async () => {
    setGuardando(true);
    setMensaje({ tipo: "", texto: "" });

    const nota =
      window.prompt("Escribe una nota para esta versión (opcional):") || "";

    try {
      const token = localStorage.getItem("id_token");

      const bodyData = {
        cursoId:
          temario?.nombre_curso?.trim() ||
          temario?.tema_curso?.trim() ||
          `curso_${Date.now()}`,
        contenido: temario,
        autor: userEmail || "sin-correo",
        nombre_curso: temario?.nombre_curso || "",
        tecnologia: temario?.tecnologia || "",
        asesor_comercial: temario?.asesor_comercial || "",
        nombre_preventa: temario?.nombre_preventa || "",
        nota_version: nota,
        fecha_creacion: new Date().toISOString(),
      };

      const response = await fetch(
        "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-KNTR",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(bodyData),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success)
        throw new Error(data.error || "Error al guardar versión");

      setMensaje({ tipo: "ok", texto: "✅ Versión guardada correctamente" });
    } catch (err) {
      console.error("Error al guardar versión:", err);
      setMensaje({
        tipo: "error",
        texto: "❌ Error al guardar versión (ver consola)",
      });
    } finally {
      setGuardando(false);
      setTimeout(() => setMensaje({ tipo: "", texto: "" }), 4000);
    }
  };

  // ===== EXPORTAR PDF =====
  const exportarPDF = async () => {
    try {
      if (!Array.isArray(temario.temario) || temario.temario.length === 0) {
        setMensaje({ tipo: "error", texto: "No hay contenido para exportar." });
        return;
      }

      const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
      const azul = "#005A9C";
      const negro = "#000000";
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = { top: 230, bottom: 100, left: 60, right: 60 }; // ✅ más margen
      const contentWidth = pageWidth - margin.left - margin.right;
      const encabezado = await toDataURL(encabezadoImagen);
      const pie = await toDataURL(pieDePaginaImagen);
      let y = margin.top;

      const addPageIfNeeded = (extra = 40) => {
        if (y + extra > pageHeight - margin.bottom) {
          doc.addPage();
          y = margin.top;
        }
      };

      doc.setFont("helvetica", "bold");
      doc.setFontSize(22);
      doc.setTextColor(azul);
      const tituloCurso = temario?.nombre_curso || "Temario del Curso";
      const lineasCurso = doc.splitTextToSize(tituloCurso, contentWidth - 40);
      lineasCurso.forEach((linea) => {
        doc.text(linea, pageWidth / 2, y, { align: "center" });
        y += 18;
      });
      y += 20;
      // 🔹 Duración total del curso (estilo visual mejorado)
      doc.setFont("helvetica", "bolditalic"); // ✅ negrita y cursiva
      doc.setFontSize(12);
      doc.setTextColor(azul);
      const duracionTexto = `Duración total del curso: ${temario?.horas_total_curso || 0} horas`;
      doc.text(duracionTexto, pageWidth - margin.right, y + 10, { align: "right" }); // ✅ alineado derecha
      y += 30;
      // 🔹 Secciones generales
      const secciones = [
        { titulo: "Descripción General", texto: temario?.descripcion_general },
        { titulo: "Audiencia", texto: temario?.audiencia },
        { titulo: "Prerrequisitos", texto: temario?.prerrequisitos },
        { titulo: "Objetivos", texto: temario?.objetivos },
      ];

      secciones.forEach((s) => {
        if (!s.texto) return;
        addPageIfNeeded(60);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(14);
        doc.setTextColor(azul);
        doc.text(s.titulo, margin.left, y);
        y += 18;
        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        doc.setTextColor(negro);
        const lineas = doc.splitTextToSize(s.texto, contentWidth);
        lineas.forEach((linea) => {
          addPageIfNeeded(14);
          doc.text(linea, margin.left, y, { align: "justify" });
          y += 14;
        });
        y += 10;
      });

      // 🔹 Añadimos un espacio antes del divisor
      y += 10;

      // 🔹 Dibujamos una línea divisoria para separar secciones
      doc.setDrawColor(150, 150, 150); // gris claro
      doc.setLineWidth(0.8);
      doc.line(margin.left, y, pageWidth - margin.right, y);

      y += 25; // espacio después de la línea

      // 🔹 Agregamos el título "Temario"
      addPageIfNeeded(70);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azul);
      doc.text("Temario", margin.left, y);

      // 🔹 Espacio adicional antes del primer capítulo
      y += 35;

      temario.temario.forEach((cap, i) => {
        addPageIfNeeded(60);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        const tituloCap = `Capítulo ${i + 1}: ${cap.capitulo}`;
        const lineasCap = doc.splitTextToSize(tituloCap, contentWidth - 40);
        lineasCap.forEach((linea) => {
          doc.text(linea, margin.left, y);
          y += 14;
        });
        y += 6;

        doc.setFont("helvetica", "italic");
        doc.setFontSize(9);
        doc.setTextColor(negro);
        doc.text(`Duración total: ${cap.tiempo_capitulo_min || 0} min`, margin.left + 10, y);
        y += 14;

        if (cap.objetivos_capitulo) {
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          const objetivos = Array.isArray(cap.objetivos_capitulo)
            ? cap.objetivos_capitulo.join(" ")
            : cap.objetivos_capitulo;
          const lines = doc.splitTextToSize(`Objetivos: ${objetivos}`, contentWidth);
          lines.forEach((line) => {
            addPageIfNeeded(12);
            doc.text(line, margin.left + 15, y, { align: "justify" });
            y += 12;
          });
          y += 10;
        }

        cap.subcapitulos.forEach((sub, j) => {
          addPageIfNeeded(18);
          const subObj = typeof sub === "object" ? sub : { nombre: sub };
          const meta = `${subObj.tiempo_subcapitulo_min || 0} min • Sesión ${subObj.sesion || 1}`;
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          const subTitulo = `${i + 1}.${j + 1} ${subObj.nombre}`;
          const subLineas = doc.splitTextToSize(subTitulo, contentWidth - 120);
          subLineas.forEach((linea, idx) => {
            addPageIfNeeded(12);
            doc.text(linea, margin.left + 25, y);
            if (idx === 0) doc.text(meta, pageWidth - margin.right, y, { align: "right" });
            y += 12;
          });
        });
        y += 20;
      });

      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        const propsEnc = doc.getImageProperties(encabezado);
        const altoEnc = (propsEnc.height / propsEnc.width) * pageWidth;
        doc.addImage(encabezado, "PNG", 0, 0, pageWidth, altoEnc);
        const propsPie = doc.getImageProperties(pie);
        const altoPie = (propsPie.height / propsPie.width) * pageWidth;
        doc.addImage(pie, "PNG", 0, pageHeight - altoPie, pageWidth, altoPie);
        doc.setFontSize(8);
        doc.setTextColor("#666");
        doc.text(
          "Documento generado mediante tecnología de IA bajo la supervisión y aprobación de Netec.",
          margin.left,
          pageHeight - 70
        );
        doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageHeight - 55, {
          align: "center",
        });
      }

      doc.save(`Temario_${slugify(temario?.nombre_curso)}.pdf`);
      setMensaje({ tipo: "ok", texto: "✅ PDF exportado correctamente" });
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: "❌ Error al generar PDF" });
    }
  };

  const exportarExcel = () => {
    if (!Array.isArray(temario.temario) || temario.temario.length === 0) {
      setMensaje({ tipo: "error", texto: "No hay datos para exportar." });
      return;
    }
    downloadExcelTemario(temario);
    setMensaje({ tipo: "ok", texto: "✅ Excel exportado correctamente" });
  };

  // === RENDER ===
  return (
    <div className="kntr-editor-container">
      {mensaje.texto && <div className={`msg ${mensaje.tipo}`}>{mensaje.texto}</div>}

      <h3>Información general del curso</h3>
      {/* 🔹 Campo: Horas Totales del Curso */}
      <label>Duración total del curso (horas)</label>
      <input
        type="number"
        min="0"
        value={temario.horas_total_curso || 0}
        onChange={(e) =>
          setTemario({ ...temario, horas_total_curso: e.target.value })
        }
        className="input-capitulo"
        placeholder="Ej: 40"
      />

      {/* 🔴 CAMPO AÑADIDO: DESCRIPCIÓN GENERAL */}
      <label>Descripción General</label>
      <textarea
        value={temario.descripcion_general || ""}
        onChange={(e) =>
          setTemario({ ...temario, descripcion_general: e.target.value })
        }
        className="textarea-objetivos-capitulo"
        placeholder="Ej: Curso introductorio a Scrum, dirigido a desarrolladores con 1 año de experiencia..."
      />
      {/* 🔴 CAMPO AÑADIDO: AUDIENCIA */}
      <label>Audiencia</label>
      <textarea
        value={temario.audiencia || ""}
        onChange={(e) =>
          setTemario({ ...temario, audiencia: e.target.value })
        }
        className="textarea-objetivos-capitulo"
        placeholder="Ej: Desarrolladores, líderes de proyecto, gerentes de producto..."
      />

      {/* 🔴 CAMPO AÑADIDO: PRERREQUISITOS */}
      <label>Prerrequisitos</label>
      <textarea
        value={temario.prerrequisitos || ""}
        onChange={(e) =>
          setTemario({ ...temario, prerrequisitos: e.target.value })
        }
        className="textarea-objetivos-capitulo"
        placeholder="Ej: Conocimientos básicos de gestión de proyectos..."
      />
      {/* 🔹 CAMPO AÑADIDO: OBJETIVOS */}
      <label>Objetivos</label>
      <textarea
        value={temario.objetivos || ""}
        onChange={(e) =>
          setTemario({ ...temario, objetivos: e.target.value })
        }
        className="textarea-objetivos-capitulo"
        placeholder="Ej: Al finalizar el curso, los participantes podrán..."
      />
      <hr style={{ margin: "20px 0" }} />

      <h3>Temario Detallado</h3>
      {(temario.temario || []).map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <h4>Capítulo {i + 1}</h4>

          <input
            value={cap.capitulo || ""}
            onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
            className="input-capitulo"
            placeholder="Nombre del capítulo"
          />

          <div className="duracion-total">
            ⏱️ Duración total:&nbsp;
            <input
              type="number"
              min="0"
              value={cap.tiempo_capitulo_min || 0}
              onChange={(e) =>
                handleFieldChange(i, null, "tiempo_capitulo_min", e.target.value)
              }
              className="input-duracion"
              style={{ width: "80px", textAlign: "center" }}
            />
            <span style={{ marginLeft: "8px", color: "#035b6e", fontWeight: 600 }}>
              {formatDuration(cap.tiempo_capitulo_min || 0)}
            </span>
          </div>

          <label>Objetivos del Capítulo</label>
          <textarea
            value={
              Array.isArray(cap.objetivos_capitulo)
                ? cap.objetivos_capitulo.join("\n")
                : cap.objetivos_capitulo || ""
            }
            onChange={(e) =>
              handleFieldChange(i, null, "objetivos_capitulo", e.target.value.split("\n"))
            }
            className="textarea-objetivos-capitulo"
            placeholder="Un objetivo por línea"
          />

          {/* === SUBCAPÍTULOS === */}
          <ul>
            {(cap.subcapitulos || []).map((sub, j) => (
              <li key={j} className="subcapitulo-item">
                <span>
                  {i + 1}.{j + 1}
                </span>
                <input
                  value={sub.nombre || ""}
                  onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)}
                  type="text"
                  placeholder="Nombre del tema"
                />
                <input
                  type="number"
                  value={sub.tiempo_subcapitulo_min || 0}
                  onChange={(e) =>
                    handleFieldChange(i, j, "tiempo_subcapitulo_min", e.target.value)
                  }
                  placeholder="min"
                />
                <input
                  type="number"
                  value={sub.sesion || 1}
                  onChange={(e) =>
                    handleFieldChange(i, j, "sesion", e.target.value)
                  }
                  placeholder="sesión"
                  className="input-sesion"
                />

                <button
                  className="btn-eliminar-tema"
                  onClick={() => eliminarTema(i, j)}
                  title="Eliminar tema"
                >
                  <Trash2 size={18} strokeWidth={2} />
                  <span>Eliminar</span>
                </button>
              </li>
            ))}
          </ul>

          {/* 🔹 Acciones del capítulo */}
          <div className="acciones-capitulo">
            <button className="btn-agregar-tema" onClick={() => agregarTema(i)}>
              <Plus size={18} strokeWidth={2} />
              <span>Agregar Tema</span>
            </button>
            <button
              className="btn-eliminar-capitulo"
              onClick={() => eliminarCapitulo(i)}
              title="Eliminar este capítulo"
            >
              <Trash2 size={18} strokeWidth={2} />
              <span>Eliminar Capítulo</span>
            </button>
          </div>
        </div>
      ))}

      <div className="btn-agregar-capitulo-container">
        <button className="btn-agregar-capitulo" onClick={agregarCapitulo}>
          <Plus size={18} strokeWidth={2} />
          <span>Agregar Capítulo</span>
        </button>
      </div>

      {/* === Acciones finales === */}
      <div className="acciones-footer">
        <button className="btn-primario" onClick={ajustarTiempos}>
          Ajustar Tiempos
        </button>
        <button className="btn-secundario" onClick={handleSaveClick} disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>
        <button className="btn-secundario" onClick={() => setModalExportar(true)}>
          Exportar
        </button>
      </div>

      {modalExportar && (
        <div className="modal-overlay" onClick={() => setModalExportar(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Exportar</h3>
              <button className="modal-close" onClick={() => setModalExportar(false)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <label>
                <input
                  type="radio"
                  checked={exportTipo === "pdf"}
                  onChange={() => setExportTipo("pdf")}
                />{" "}
                PDF
              </label>
              <label>
                <input
                  type="radio"
                  checked={exportTipo === "excel"}
                  onChange={() => setExportTipo("excel")}
                />{" "}
                Excel
              </label>
            </div>
            <div className="modal-footer">
              <button
                onClick={() => {
                  exportTipo === "pdf" ? exportarPDF(temario) : exportarExcel();
                  setModalExportar(false);
                }}
                className="btn-guardar"
              >
                Exportar {exportTipo.toUpperCase()}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
// ✅ Exportar función exportarPDF para que GeneradorTemarios pueda usar la misma lógica
export const exportarPDF = async (temarioData) => {
  if (!temarioData || !Array.isArray(temarioData.temario)) {
    alert("No hay contenido válido para exportar.");
    return;
  }

  const { jsPDF } = await import("jspdf");
  const toDataURL = async (url) => {
    const res = await fetch(url);
    const blob = await res.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  };

  const encabezado = await toDataURL("/src/assets/encabezado.png");
  const pie = await toDataURL("/src/assets/pie_de_pagina.png");

  const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
  const azul = "#005A9C";
  const negro = "#000000";
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = { top: 220, bottom: 90, left: 50, right: 50 };
  const contentWidth = pageWidth - margin.left - margin.right;
  let y = margin.top;

  const addPageIfNeeded = (extra = 40) => {
    if (y + extra > pageHeight - margin.bottom) {
      doc.addPage();
      y = margin.top;
    }
  };

  // 🔹 Título
  doc.setFont("helvetica", "bold");
  doc.setFontSize(22);
  doc.setTextColor(azul);
  const tituloCurso = temarioData.nombre_curso || "Temario del Curso";
  const lineasCurso = doc.splitTextToSize(tituloCurso, contentWidth - 40);
  lineasCurso.forEach((linea) => {
    doc.text(linea, pageWidth / 2, y, { align: "center" });
    y += 18;
  });
  y += 20;
  doc.text(`Duración total del curso: ${temarioData.horas_total_curso || 0} horas`, margin.left, y);
  y += 14;
  // 🔹 Secciones generales
  const secciones = [
    { titulo: "Descripción General", texto: temarioData.descripcion_general },
    { titulo: "Audiencia", texto: temarioData.audiencia },
    { titulo: "Prerrequisitos", texto: temarioData.prerrequisitos },
    { titulo: "Objetivos", texto: temarioData.objetivos },
  ];

  secciones.forEach((s) => {
    if (!s.texto) return;
    addPageIfNeeded(60);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(azul);
    doc.text(s.titulo, margin.left, y);
    y += 18;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(negro);
    const lineas = doc.splitTextToSize(s.texto, contentWidth);
    lineas.forEach((linea) => {
      addPageIfNeeded(14);
      doc.text(linea, margin.left, y, { align: "justify" });
      y += 14;
    });
    y += 10;
  });

  // 🔹 Temario
  addPageIfNeeded(50);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(20);
  doc.setTextColor(azul);
  doc.text("Temario", margin.left, y);
  y += 25;

  temarioData.temario.forEach((cap, i) => {
    addPageIfNeeded(60);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(13);
    doc.setTextColor(azul);

    const tituloCap = `Capítulo ${i + 1}: ${cap.capitulo}`;
    const lineasCap = doc.splitTextToSize(tituloCap, contentWidth - 40);
    lineasCap.forEach((linea) => {
      doc.text(linea, margin.left, y);
      y += 14;
    });
    y += 4;

    doc.setFont("helvetica", "italic");
    doc.setFontSize(9);
    doc.setTextColor(negro);
    doc.text(`Duración total: ${formatDuration(cap.tiempo_capitulo_min || 0)}`, margin.left + 10, y);
    y += 12;

    if (cap.objetivos_capitulo) {
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      const objetivos = Array.isArray(cap.objetivos_capitulo)
        ? cap.objetivos_capitulo.join(" ")
        : cap.objetivos_capitulo;
      const lines = doc.splitTextToSize(`Objetivos: ${objetivos}`, contentWidth);
      lines.forEach((line) => {
        addPageIfNeeded(12);
        doc.text(line, margin.left + 15, y, { align: "justify" });
        y += 12;
      });
      y += 10;
    }

    cap.subcapitulos.forEach((sub, j) => {
      addPageIfNeeded(16);
      const subObj = typeof sub === "object" ? sub : { nombre: sub };
      const meta = `${formatDuration(subObj.tiempo_subcapitulo_min || 0)} • Sesión ${subObj.sesion || 1}`;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      const subTitulo = `${i + 1}.${j + 1} ${subObj.nombre}`;
      const subLineas = doc.splitTextToSize(subTitulo, contentWidth - 120);
      subLineas.forEach((linea, idx) => {
        addPageIfNeeded(12);
        doc.text(linea, margin.left + 25, y);
        if (idx === 0) {
          doc.text(meta, pageWidth - margin.right, y, { align: "right" });
        }
        y += 12;
      });
    });
    y += 16;
  });

  const totalPages = doc.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    const propsEnc = doc.getImageProperties(encabezado);
    const altoEnc = (propsEnc.height / propsEnc.width) * pageWidth;
    doc.addImage(encabezado, "PNG", 0, 0, pageWidth, altoEnc);
    const propsPie = doc.getImageProperties(pie);
    const altoPie = (propsPie.height / propsPie.width) * pageWidth;
    doc.addImage(pie, "PNG", 0, pageHeight - altoPie, pageWidth, altoPie);
    doc.setFontSize(8);
    doc.setTextColor("#666");
    doc.text(
      "Documento generado mediante tecnología de IA bajo la supervisión y aprobación de Netec.",
      margin.left,
      pageHeight - 70
    );
    doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageHeight - 55, {
      align: "center",
    });
  }

  doc.save(`Temario_${temarioData.nombre_curso || "curso"}.pdf`);
};


export default EditorDeTemario_KNTR;