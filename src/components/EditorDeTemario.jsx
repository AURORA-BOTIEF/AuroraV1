// src/components/EditorDeTemario.jsx (VERSIÓN FINAL con ajuste de tiempos y PDF sin encimado)
import React, { useState, useEffect, useRef } from "react";
import jsPDF from "jspdf";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";

function slugify(str = "") {
  return String(str)
    .normalize("NFD")
    .replace(/[\u00-~]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "curso";
}

function nowIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`;
}

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

function EditorDeTemario({ temarioInicial, onSave, isLoading }) {
  const [temario, setTemario] = useState(temarioInicial);
  const [guardando, setGuardando] = useState(false);
  const [errorUi, setErrorUi] = useState("");
  const [okUi, setOkUi] = useState("");
  const [modalExportar, setModalExportar] = useState(false);
  const [exportTipo, setExportTipo] = useState("pdf");

  const pdfContentRef = useRef(null);

  useEffect(() => {
    setTemario(temarioInicial);
  }, [temarioInicial]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setTemario((prev) => ({ ...prev, [name]: value }));
  };

  const handleFieldChange = (capIndex, subIndex, fieldName, value) => {
    const nuevoTemario = JSON.parse(JSON.stringify(temario));
    let target;

    if (subIndex === null) {
      target = nuevoTemario.temario[capIndex];
    } else {
      if (typeof nuevoTemario.temario[capIndex].subcapitulos[subIndex] !== "object") {
        nuevoTemario.temario[capIndex].subcapitulos[subIndex] = {
          nombre: nuevoTemario.temario[capIndex].subcapitulos[subIndex],
        };
      }
      target = nuevoTemario.temario[capIndex].subcapitulos[subIndex];
    }

    const numeric = ["tiempo_capitulo_min", "tiempo_subcapitulo_min", "sesion"];
    target[fieldName] = numeric.includes(fieldName)
      ? parseInt(value, 10) || 0
      : value;
    setTemario(nuevoTemario);
  };

  // 🔹 Agregar capítulo
  const agregarCapitulo = () => {
    const nuevo = {
      capitulo: "",
      tiempo_capitulo_min: 0,
      objetivos_capitulo: [],
      subcapitulos: [],
    };
    setTemario((prev) => ({
      ...prev,
      temario: [...(prev.temario || []), nuevo],
    }));
  };

  // 🔹 Agregar tema (subcapítulo)
  const agregarSubcapitulo = (capIndex) => {
    const nuevoTemario = JSON.parse(JSON.stringify(temario));
    nuevoTemario.temario[capIndex].subcapitulos.push({
      nombre: "",
      tiempo_subcapitulo_min: 0,
      sesion: "",
    });
    setTemario(nuevoTemario);
  };

  // 🔹 Ajustar tiempos automáticamente según horas totales
  const ajustarTiempos = () => {
    try {
      const horasTotales = parseFloat(temario?.horas_totales || 7);
      const minutosTotales = horasTotales * 60;
      const capitulos = temario?.temario?.length || 0;

      if (capitulos === 0) {
        alert("No hay capítulos para ajustar tiempos.");
        return;
      }

      const minutosPorCapitulo = Math.floor(minutosTotales / capitulos);
      const nuevoTemario = JSON.parse(JSON.stringify(temario));

      nuevoTemario.temario.forEach((cap) => {
        cap.tiempo_capitulo_min = minutosPorCapitulo;
        if (cap.subcapitulos?.length > 0) {
          const minutosPorSub = Math.floor(minutosPorCapitulo / cap.subcapitulos.length);
          cap.subcapitulos.forEach((sub) => {
            sub.tiempo_subcapitulo_min = minutosPorSub;
          });
        }
      });

      setTemario(nuevoTemario);
      setOkUi("⏱️ Tiempos ajustados correctamente.");
    } catch (e) {
      setErrorUi("Error al ajustar tiempos.");
    }
  };

  // 🔹 Guardar versión
  const handleSaveClick = async () => {
    setErrorUi("");
    setOkUi("");
    setGuardando(true);
    const nota =
      window.prompt("Escribe una nota para esta versión (opcional):", `Guardado ${nowIso()}`) ||
      "";
    try {
      const resultado = await onSave?.(temario, nota);
      if (resultado?.success || resultado === true) {
        setOkUi("Versión guardada correctamente.");
      } else {
        setErrorUi("Error al guardar versión.");
      }
    } catch (err) {
      console.error(err);
      setErrorUi("Error al guardar versión.");
    } finally {
      setGuardando(false);
    }
  };

  // 🔹 Exportar PDF profesional (sin encimado)
  const exportarPDF = async () => {
    try {
      const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
      const azulNetec = "#005A9C";
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = { top: 210, bottom: 100, left: 40, right: 40 };
      const contentWidth = pageWidth - margin.left - margin.right;

      const encabezadoDataUrl = await toDataURL(encabezadoImagen);
      const pieDataUrl = await toDataURL(pieDePaginaImagen);
      let y = margin.top;

      const addPageIfNeeded = (space = 20) => {
        if (y + space > pageHeight - margin.bottom) {
          doc.addPage();
          y = margin.top;
        }
      };

      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azulNetec);
      doc.text(temario?.nombre_curso || "Temario del Curso", pageWidth / 2, y, { align: "center" });
      doc.setTextColor(0, 0, 0);
      y += 40;

      const sections = [
        ["Descripción General", temario?.descripcion_general],
        ["Audiencia", temario?.audiencia],
        ["Prerrequisitos", Array.isArray(temario?.prerrequisitos) ? temario.prerrequisitos.join("\n") : temario?.prerrequisitos],
        ["Objetivos Generales", Array.isArray(temario?.objetivos) ? temario.objetivos.join("\n") : temario?.objetivos],
      ];

      sections.forEach(([title, text]) => {
        if (!text) return;
        addPageIfNeeded(50);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azulNetec);
        doc.text(title, margin.left, y);
        y += 16;
        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        doc.setTextColor(0, 0, 0);
        const lines = doc.splitTextToSize(text, contentWidth);
        lines.forEach((line) => {
          addPageIfNeeded(12);
          doc.text(line, margin.left, y);
          y += 12;
        });
        y += 10;
      });

      // 🔹 Temario detallado
      if (temario?.temario?.length > 0) {
        addPageIfNeeded(30);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(16);
        doc.setTextColor(azulNetec);
        doc.text("Temario", margin.left, y);
        y += 20;

        temario.temario.forEach((cap, i) => {
          addPageIfNeeded(40);
          doc.setFont("helvetica", "bold");
          doc.setFontSize(12);
          doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, margin.left, y);
          y += 15;

          if (cap.objetivos_capitulo?.length) {
            const texto = Array.isArray(cap.objetivos_capitulo)
              ? cap.objetivos_capitulo.join(" ")
              : cap.objetivos_capitulo;
            const lines = doc.splitTextToSize(`Objetivos: ${texto}`, contentWidth);
            lines.forEach((line) => {
              addPageIfNeeded(12);
              doc.setFont("helvetica", "normal");
              doc.text(line, margin.left + 10, y);
              y += 12;
            });
            y += 10;
          }

          cap.subcapitulos?.forEach((sub, j) => {
            addPageIfNeeded(15);
            const s = typeof sub === "object" ? sub : { nombre: sub };
            doc.setFont("helvetica", "normal");
            doc.text(`${i + 1}.${j + 1} ${s.nombre}`, margin.left + 20, y);
            if (s.tiempo_subcapitulo_min || s.sesion) {
              const meta = `${s.tiempo_subcapitulo_min ? s.tiempo_subcapitulo_min + " min" : ""} ${
                s.sesion ? "• Sesión " + s.sesion : ""
              }`;
              doc.text(meta.trim(), pageWidth - margin.right, y, { align: "right" });
            }
            y += 12;
          });
          y += 8;
        });
      }

      // 🔹 Encabezado y pie
      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        const propsEnc = doc.getImageProperties(encabezadoDataUrl);
        const altoEnc = pageWidth * (propsEnc.height / propsEnc.width);
        doc.addImage(encabezadoDataUrl, "PNG", 0, 0, pageWidth, altoEnc);
        const propsPie = doc.getImageProperties(pieDataUrl);
        const altoPie = pageWidth * (propsPie.height / propsPie.width);
        doc.addImage(pieDataUrl, "PNG", 0, pageHeight - altoPie, pageWidth, altoPie);
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
      setOkUi("✅ PDF exportado correctamente");
    } catch (error) {
      console.error("Error PDF:", error);
      setErrorUi("Error al generar el PDF.");
    }
  };

  const exportarExcel = () => {
    downloadExcelTemario(temario);
    setOkUi("✅ Exportado correctamente a Excel");
    setModalExportar(false);
  };

  if (!temario) return null;

  return (
    <div className="editor-container">
      {(errorUi || okUi) && (
        <div className="ui-messages">
          {errorUi && <div className="msg error">{errorUi}</div>}
          {okUi && <div className="msg ok">{okUi}</div>}
        </div>
      )}

      <h3>Temario Detallado</h3>
      {(temario?.temario || []).map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <h4>Capítulo {i + 1}</h4>
          <input
            value={cap.capitulo || ""}
            onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
            className="input-capitulo"
          />

          <div className="objetivos-capitulo">
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
            />
          </div>

          <ul>
            {cap.subcapitulos?.map((sub, j) => {
              const s = typeof sub === "object" ? sub : { nombre: sub };
              return (
                <li key={j}>
                  <div className="subcapitulo-item-detallado">
                    <span className="subcapitulo-numero">{i + 1}.{j + 1}</span>
                    <input
                      value={s.nombre || ""}
                      onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)}
                      className="input-subcapitulo"
                      placeholder="Nombre del subcapítulo"
                    />
                    <div className="subcapitulo-meta-inputs">
                      <input
                        type="number"
                        value={s.tiempo_subcapitulo_min || ""}
                        onChange={(e) =>
                          handleFieldChange(i, j, "tiempo_subcapitulo_min", e.target.value)
                        }
                        placeholder="min"
                      />
                      <input
                        type="number"
                        value={s.sesion || ""}
                        onChange={(e) => handleFieldChange(i, j, "sesion", e.target.value)}
                        placeholder="sesión"
                      />
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="acciones-subcapitulos">
            <button className="btn-agregar-tema" onClick={() => agregarSubcapitulo(i)}>
              Agregar Tema
            </button>
          </div>
        </div>
      ))}

      <div className="acciones-agregar">
        <button className="btn-agregar-capitulo" onClick={agregarCapitulo}>
          Agregar Capítulo
        </button>
      </div>

      <div className="acciones-footer">
        <button onClick={ajustarTiempos}>Ajustar Tiempos Automáticamente</button>
        <button className="btn-secundario" onClick={handleSaveClick} disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>
        <button className="btn-secundario" onClick={() => setModalExportar(true)}>
          Exportar...
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
              <div className="export-format">
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
            </div>
            <div className="modal-footer">
              {exportTipo === "pdf" ? (
                <button onClick={exportarPDF} className="btn-guardar">
                  Exportar PDF
                </button>
              ) : (
                <button onClick={exportarExcel} className="btn-guardar">
                  Exportar Excel
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default EditorDeTemario;

