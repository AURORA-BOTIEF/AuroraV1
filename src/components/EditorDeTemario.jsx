// src/components/EditorDeTemario.jsx (FINAL COMPLETO CORREGIDO + PDF PRO + Ajustar tiempos)
import React, { useState, useEffect, useRef } from "react";
import jsPDF from "jspdf";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";

const API_BASE = import.meta.env.VITE_TEMARIOS_API || "";

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

function EditorDeTemario({ temarioInicial, onRegenerate, onSave, isLoading }) {
  const [temario, setTemario] = useState(temarioInicial);
  const [vista, setVista] = useState("detallada");
  const [mostrarFormRegenerar, setMostrarFormRegenerar] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [errorUi, setErrorUi] = useState("");
  const [okUi, setOkUi] = useState("");
  const [modalExportar, setModalExportar] = useState(false);
  const [exportTipo, setExportTipo] = useState("pdf");

  const pdfContentRef = useRef(null);

  const [params, setParams] = useState({
    tecnologia: temarioInicial?.version_tecnologia || "",
    tema_curso: temarioInicial?.tema_curso || temarioInicial?.nombre_curso || "",
    extension_curso_dias: temarioInicial?.numero_sesiones || 1,
    nivel_dificultad: temarioInicial?.nivel_dificultad || "basico",
    audiencia: temarioInicial?.audiencia || "",
    enfoque: temarioInicial?.enfoque || "",
  });

  useEffect(() => {
    setTemario(temarioInicial);
  }, [temarioInicial]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setTemario((prev) => ({ ...prev, [name]: value }));
  };

  const handleFieldChange = (capIndex, subIndex, fieldName, value) => {
    const nuevoTemario = JSON.parse(JSON.stringify(temario));
    let targetObject;

    if (subIndex === null) {
      targetObject = nuevoTemario.temario[capIndex];
    } else {
      if (typeof nuevoTemario.temario[capIndex].subcapitulos[subIndex] !== "object") {
        nuevoTemario.temario[capIndex].subcapitulos[subIndex] = {
          nombre: nuevoTemario.temario[capIndex].subcapitulos[subIndex],
        };
      }
      targetObject = nuevoTemario.temario[capIndex].subcapitulos[subIndex];
    }

    const numericFields = ["tiempo_capitulo_min", "tiempo_subcapitulo_min", "sesion"];
    targetObject[fieldName] = numericFields.includes(fieldName)
      ? parseInt(value, 10) || 0
      : value;

    setTemario(nuevoTemario);
  };

  const handleParamsChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleRegenerateClick = () => {
    setErrorUi("");
    setOkUi("");
    onRegenerate?.(params);
    setMostrarFormRegenerar(false);
  };

  // ✅ Ajustar tiempos automáticamente según total horas del curso
  const handleAjustarTiempos = () => {
    const totalHoras = temario?.horas_totales || 7; // fallback si no está definido
    const totalMinutos = totalHoras * 60;
    const nuevoTemario = JSON.parse(JSON.stringify(temario));

    const subtemasTotales = nuevoTemario.temario.reduce(
      (sum, cap) => sum + (cap.subcapitulos?.length || 0),
      0
    );

    if (subtemasTotales === 0) {
      alert("No hay temas definidos para ajustar.");
      return;
    }

    const minutosPorSubtema = Math.floor(totalMinutos / subtemasTotales);
    nuevoTemario.temario.forEach((cap) => {
      cap.subcapitulos.forEach((sub) => (sub.tiempo_subcapitulo_min = minutosPorSubtema));
    });

    setTemario(nuevoTemario);
    setOkUi(`⏱️ Tiempos ajustados automáticamente (${totalMinutos} min totales)`);
  };

  // ✅ Guardar versión
  const handleSaveClick = async () => {
    setErrorUi("");
    setOkUi("");
    setGuardando(true);

    const nota =
      window.prompt(
        "Escribe una nota para esta versión (opcional):",
        `Guardado ${nowIso()}`
      ) || "";

    try {
      const resultado = await onSave?.(temario, nota);
      const success = resultado?.success ?? true;
      const message = resultado?.message || "Versión guardada correctamente";
      success ? setOkUi(message) : setErrorUi(message);
    } catch (err) {
      console.error(err);
      setErrorUi("No se pudo guardar la versión");
    } finally {
      setGuardando(false);
    }
  };

  // ✅ Exportar PDF (corregido sin encimado)
  const exportarPDF = async () => {
    try {
      setOkUi("Generando PDF profesional...");
      const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
      const azulNetec = "#005A9C";
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = { top: 210, bottom: 100, left: 40, right: 40 };
      const contentWidth = pageWidth - margin.left - margin.right;
      const encabezadoDataUrl = await toDataURL(encabezadoImagen);
      const pieDataUrl = await toDataURL(pieDePaginaImagen);
      let y = margin.top;

      const addPageIfNeeded = (extra = 40) => {
        if (y + extra > pageHeight - margin.bottom) {
          doc.addPage();
          y = margin.top;
        }
      };

      // Título
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azulNetec);
      doc.text(temario?.nombre_curso || "Temario del Curso", pageWidth / 2, y, {
        align: "center",
      });
      doc.setTextColor(0, 0, 0);
      y += 30;

      // Secciones descriptivas
      const drawSection = (title, content) => {
        if (!content) return;
        const text = Array.isArray(content) ? content.join("\n") : content;
        const lines = doc.splitTextToSize(text, contentWidth);
        addPageIfNeeded(15 + lines.length * 14);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azulNetec);
        doc.text(title, margin.left, y);
        doc.setTextColor(0, 0, 0);
        y += 14;
        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        lines.forEach((line) => {
          addPageIfNeeded(14);
          doc.text(line, margin.left, y);
          y += 14;
        });
        y += 10;
      };

      drawSection("Descripción General", temario?.descripcion_general);
      drawSection("Audiencia", temario?.audiencia);
      drawSection("Prerrequisitos", temario?.prerrequisitos);
      drawSection("Objetivos", temario?.objetivos);

      // Temario
      doc.setFont("helvetica", "bold");
      doc.setFontSize(16);
      doc.setTextColor(azulNetec);
      doc.text("Temario", margin.left, y);
      y += 25;
      doc.setTextColor(0, 0, 0);

      temario.temario.forEach((cap, i) => {
        addPageIfNeeded(60);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(12);
        doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, margin.left, y);
        y += 18;

        if (cap.objetivos_capitulo) {
          const text = Array.isArray(cap.objetivos_capitulo)
            ? cap.objetivos_capitulo.join(" ")
            : cap.objetivos_capitulo;
          const lines = doc.splitTextToSize(`Objetivos: ${text}`, contentWidth - 20);
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          lines.forEach((line) => {
            addPageIfNeeded(14);
            doc.text(line, margin.left + 15, y);
            y += 14;
          });
          y += 8;
        }

        cap.subcapitulos?.forEach((sub, j) => {
          addPageIfNeeded(20);
          const subObj = typeof sub === "object" ? sub : { nombre: sub };
          const nombre = `${i + 1}.${j + 1} ${subObj.nombre}`;
          const tiempo = subObj.tiempo_subcapitulo_min ? `${subObj.tiempo_subcapitulo_min} min` : "";
          const sesion = subObj.sesion ? `• Sesión ${subObj.sesion}` : "";
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          doc.text(nombre, margin.left + 20, y);
          doc.text(`${tiempo} ${sesion}`.trim(), pageWidth - margin.right, y, {
            align: "right",
          });
          y += 16;
        });
        y += 12;
      });

      // Encabezado / Pie
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

      const nombreArchivo = slugify(temario?.nombre_curso || temario?.tema_curso || "curso");
      doc.save(`Temario_${nombreArchivo}.pdf`);
      setOkUi("✅ PDF exportado correctamente");
    } catch (error) {
      console.error("Error al generar PDF:", error);
      setErrorUi("Error al generar el PDF.");
    }
  };

  const exportarExcel = () => {
    if (!temario) return setErrorUi("No hay temario para exportar");
    downloadExcelTemario(temario);
    setOkUi("Exportado correctamente ✔");
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

      {isLoading ? (
        <div className="spinner-container">
          <div className="spinner" />
          <p>Generando nueva versión...</p>
        </div>
      ) : (
        <>
          <div className="vista-selector">
            <button
              className={`btn-vista ${vista === "detallada" ? "activo" : ""}`}
              onClick={() => setVista("detallada")}
            >
              Vista Detallada
            </button>
            <button
              className={`btn-vista ${vista === "resumida" ? "activo" : ""}`}
              onClick={() => setVista("resumida")}
            >
              Vista Resumida
            </button>
          </div>

          {vista === "detallada" && (
            <div>
              <h3>Temario Detallado</h3>
              {(temario?.temario || []).map((cap, capIndex) => (
                <div key={capIndex} className="capitulo-editor">
                  <h4>Capítulo {capIndex + 1}:</h4>
                  <input
                    value={cap.capitulo || ""}
                    onChange={(e) =>
                      handleFieldChange(capIndex, null, "capitulo", e.target.value)
                    }
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
                        handleFieldChange(
                          capIndex,
                          null,
                          "objetivos_capitulo",
                          e.target.value.split("\n")
                        )
                      }
                      className="textarea-objetivos-capitulo"
                    />
                  </div>
                  <ul>
                    {cap.subcapitulos?.map((sub, subIndex) => (
                      <li key={subIndex}>
                        <div className="subcapitulo-item-detallado">
                          <span>
                            {capIndex + 1}.{subIndex + 1}
                          </span>
                          <input
                            value={sub.nombre || ""}
                            onChange={(e) =>
                              handleFieldChange(capIndex, subIndex, "nombre", e.target.value)
                            }
                            className="input-subcapitulo"
                          />
                          <div className="subcapitulo-meta-inputs">
                            <input
                              type="number"
                              value={sub.tiempo_subcapitulo_min || ""}
                              onChange={(e) =>
                                handleFieldChange(
                                  capIndex,
                                  subIndex,
                                  "tiempo_subcapitulo_min",
                                  e.target.value
                                )
                              }
                              placeholder="min"
                            />
                            <input
                              type="number"
                              value={sub.sesion || ""}
                              onChange={(e) =>
                                handleFieldChange(capIndex, subIndex, "sesion", e.target.value)
                              }
                              placeholder="sesión"
                            />
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <div className="acciones-footer">
        <button onClick={handleAjustarTiempos}>Ajustar Tiempos Automáticamente</button>
        <button className="btn-secundario" onClick={exportarPDF}>
          Exportar PDF
        </button>
        <button className="btn-secundario" onClick={exportarExcel}>
          Exportar Excel
        </button>
        <button className="btn-guardar" onClick={handleSaveClick} disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>
      </div>
    </div>
  );
}

export default EditorDeTemario;

