import React, { useState, useEffect } from "react";
import jsPDF from "jspdf";
import { fetchAuthSession } from "aws-amplify/auth";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";

// 🔹 Convierte imágenes a base64 para el PDF
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

// 🔹 Limpia el nombre del curso para exportar
const slugify = (str = "") =>
  String(str)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "seminario";

export default function EditorDeTemario({ temarioInicial, onSave, isLoading }) {
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

  // === Obtener usuario autenticado ===
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

  // === Actualiza si cambia el temario inicial ===
  useEffect(() => {
    setTemario({
      ...temarioInicial,
      temario: Array.isArray(temarioInicial?.temario)
        ? temarioInicial.temario
        : [],
    });
  }, [temarioInicial]);

  // === Editar campos (capítulo o tema) ===
  const handleFieldChange = (capIndex, subIndex, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) nuevo.temario = [];

    if (subIndex === null) {
      nuevo.temario[capIndex][field] = value;
    } else {
      const sub = nuevo.temario[capIndex].subcapitulos[subIndex];
      nuevo.temario[capIndex].subcapitulos[subIndex] = {
        ...sub,
        [field]:
          field.includes("tiempo") ? parseInt(value, 10) || 0 : value,
      };
    }

    // Recalcular duración total del capítulo
    nuevo.temario[capIndex].tiempo_capitulo_min = nuevo.temario[
      capIndex
    ].subcapitulos.reduce(
      (sum, s) => sum + (parseInt(s.tiempo_subcapitulo_min) || 0),
      0
    );

    setTemario(nuevo);
  };

  // === Agregar capítulo ===
  const agregarCapitulo = () => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.push({
      capitulo: `Nuevo capítulo ${nuevo.temario.length + 1}`,
      tiempo_capitulo_min: 0,
      objetivos_capitulo: "",
      subcapitulos: [
        { nombre: "Nuevo tema", tiempo_subcapitulo_min: 30, sesion: 1 },
      ],
    });
    setTemario(nuevo);
  };

  // === Agregar tema ===
  const agregarTema = (capIndex) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario[capIndex].subcapitulos.push({
      nombre: `Nuevo tema ${
        nuevo.temario[capIndex].subcapitulos.length + 1
      }`,
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevo);
  };

  // === Guardar versión ===
  const handleSaveClick = async () => {
    if (!onSave) return;
    setGuardando(true);
    setMensaje({ tipo: "", texto: "" });
    const nota =
      window.prompt("Escribe una nota para esta versión (opcional):") || "";
    try {
      await onSave({ ...temario, autor: userEmail }, nota);
      setMensaje({ tipo: "ok", texto: "✅ Versión guardada correctamente" });
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: "❌ Error al guardar la versión" });
    } finally {
      setGuardando(false);
      setTimeout(() => setMensaje({ tipo: "", texto: "" }), 3000);
    }
  };

  // === Exportar a PDF ===
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
      const margin = { top: 220, bottom: 90, left: 50, right: 50 };
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
      doc.text(temario?.nombre_curso || "Seminario", pageWidth / 2, y, { align: "center" });
      y += 40;

      if (temario.descripcion_general) {
        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        const lines = doc.splitTextToSize(temario.descripcion_general, contentWidth);
        lines.forEach((line) => {
          addPageIfNeeded(14);
          doc.text(line, margin.left, y);
          y += 14;
        });
      }

      addPageIfNeeded(30);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(18);
      doc.setTextColor(azul);
      doc.text("Temario", margin.left, y);
      y += 20;

      temario.temario.forEach((cap, i) => {
        addPageIfNeeded(60);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, margin.left, y);
        y += 16;

        if (cap.objetivos_capitulo) {
          doc.setFont("helvetica", "italic");
          doc.setFontSize(10);
          const lines = doc.splitTextToSize(`Objetivos: ${cap.objetivos_capitulo}`, contentWidth);
          lines.forEach((line) => {
            addPageIfNeeded(12);
            doc.text(line, margin.left + 10, y);
            y += 12;
          });
        }

        cap.subcapitulos.forEach((sub, j) => {
          addPageIfNeeded(16);
          const subObj = typeof sub === "object" ? sub : { nombre: sub };
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          doc.text(`${i + 1}.${j + 1} ${subObj.nombre}`, margin.left + 25, y);
          doc.text(
            `${subObj.tiempo_subcapitulo_min || 0} min`,
            pageWidth - margin.right,
            y,
            { align: "right" }
          );
          y += 12;
        });
        y += 10;
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
          "Documento generado automáticamente con IA bajo supervisión de Netec.",
          margin.left,
          pageHeight - 70
        );
        doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageHeight - 55, {
          align: "center",
        });
      }

      doc.save(`Seminario_${slugify(temario?.nombre_curso)}.pdf`);
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

  // === Render ===
  return (
    <div className="editor-container">
      {mensaje.texto && <div className={`msg ${mensaje.tipo}`}>{mensaje.texto}</div>}

      <h3>Temario Detallado del Seminario</h3>

      {(temario.temario || []).map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <h4>Capítulo {i + 1}</h4>
          <input
            value={cap.capitulo || ""}
            onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
            className="input-capitulo"
          />

          <label>Objetivos del Capítulo</label>
          <textarea
            value={cap.objetivos_capitulo || ""}
            onChange={(e) => handleFieldChange(i, null, "objetivos_capitulo", e.target.value)}
          />

          <ul>
            {(cap.subcapitulos || []).map((sub, j) => (
              <li key={j} className="subcapitulo-item">
                <span>{i + 1}.{j + 1}</span>
                <input
                  value={sub.nombre || ""}
                  onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)}
                />
                <input
                  type="number"
                  value={sub.tiempo_subcapitulo_min || 0}
                  onChange={(e) =>
                    handleFieldChange(i, j, "tiempo_subcapitulo_min", e.target.value)
                  }
                  placeholder="min"
                />
              </li>
            ))}
          </ul>

          <button className="btn-agregar-tema" onClick={() => agregarTema(i)}>
            ➕ Agregar Tema
          </button>
        </div>
      ))}

      <div className="btn-agregar-capitulo-container">
        <button className="btn-agregar-capitulo" onClick={agregarCapitulo}>
          ➕ Agregar Capítulo
        </button>
      </div>

      <div className="acciones-footer">
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
              <button className="modal-close" onClick={() => setModalExportar(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>
                <input
                  type="radio"
                  checked={exportTipo === "pdf"}
                  onChange={() => setExportTipo("pdf")}
                /> PDF
              </label>
              <label>
                <input
                  type="radio"
                  checked={exportTipo === "excel"}
                  onChange={() => setExportTipo("excel")}
                /> Excel
              </label>
            </div>
            <div className="modal-footer">
              <button
                onClick={() => {
                  exportTipo === "pdf" ? exportarPDF() : exportarExcel();
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
