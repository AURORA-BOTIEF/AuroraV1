// src/components/EditorDeTemario.jsx
import React, { useState, useEffect } from "react";
import jsPDF from "jspdf";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";

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

function EditorDeTemario({ temarioInicial, onSave, onRegenerate, isLoading }) {
  const [temario, setTemario] = useState(temarioInicial || {});
  const [guardando, setGuardando] = useState(false);
  const [okUi, setOkUi] = useState("");
  const [errorUi, setErrorUi] = useState("");

  useEffect(() => {
    setTemario(temarioInicial);
  }, [temarioInicial]);

  // 🔹 Calcular tiempos (basado en las horas y sesiones)
  const totalHoras =
    (temario?.horas_por_sesion || 7) *
    (temario?.numero_sesiones_por_semana || 1);
  const totalSubtemas = temario.temario
    ? temario.temario.reduce(
        (acc, cap) => acc + (cap.subcapitulos?.length || 0),
        0
      )
    : 0;
  const horasPorSubtema =
    totalSubtemas > 0 ? (totalHoras / totalSubtemas).toFixed(2) : 0;

  // 🔹 Guardar versión
  const handleSave = async () => {
    setGuardando(true);
    setOkUi("");
    setErrorUi("");
    try {
      const nota = window.prompt("Escribe una nota para esta versión:", "");
      const res = await onSave(temario, nota);
      if (res?.success) setOkUi("✅ Temario guardado correctamente");
      else setErrorUi("❌ Error al guardar el temario");
    } catch (err) {
      console.error(err);
      setErrorUi("❌ Error al guardar el temario");
    } finally {
      setGuardando(false);
    }
  };

  // 🔹 Exportar PDF (con encabezado y pie)
  const exportarPDF = async () => {
    const doc = new jsPDF();
    const encabezado = await toDataURL(encabezadoImagen);
    const pie = await toDataURL(pieDePaginaImagen);
    const pageWidth = doc.internal.pageSize.getWidth();

    doc.addImage(encabezado, "PNG", 0, 0, pageWidth, 100);
    doc.setFont("helvetica", "bold");
    doc.text(temario.nombre_curso || "Temario", pageWidth / 2, 120, {
      align: "center",
    });

    let y = 150;
    doc.setFont("helvetica", "normal");
    doc.text(`Duración total: ${totalHoras} horas`, 20, y);
    y += 15;
    doc.text(`Tiempo estimado por subtema: ${horasPorSubtema} h`, 20, y);
    y += 25;

    (temario.temario || []).forEach((cap, i) => {
      doc.setFont("helvetica", "bold");
      doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, 20, y);
      y += 15;
      (cap.subcapitulos || []).forEach((sub, j) => {
        const nombre = typeof sub === "object" ? sub.nombre : sub;
        doc.setFont("helvetica", "normal");
        doc.text(`• ${nombre} (${horasPorSubtema} h aprox.)`, 30, y);
        y += 12;
      });
      y += 10;
    });

    const totalPages = doc.internal.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      doc.addImage(pie, "PNG", 0, 730, pageWidth, 70);
      doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, 780, {
        align: "center",
      });
    }

    doc.save(`Temario_${temario.nombre_curso || "curso"}.pdf`);
  };

  const exportarExcel = () => {
    downloadExcelTemario(temario);
  };

  const handleFieldChange = (capIndex, subIndex, fieldName, value) => {
    const nuevoTemario = JSON.parse(JSON.stringify(temario));
    if (!nuevoTemario.temario[capIndex]) return;

    if (subIndex === null) {
      nuevoTemario.temario[capIndex][fieldName] = value;
    } else {
      if (!nuevoTemario.temario[capIndex].subcapitulos[subIndex]) return;
      nuevoTemario.temario[capIndex].subcapitulos[subIndex][fieldName] = value;
    }
    setTemario(nuevoTemario);
  };

  if (!temario) return null;

  return (
    <div className="editor-container">
      <h2>📘 Editor de Temario</h2>

      <div className="ui-messages">
        {okUi && <div className="msg ok">{okUi}</div>}
        {errorUi && <div className="msg error">{errorUi}</div>}
      </div>

      {isLoading ? (
        <div className="spinner-container">
          <div className="spinner"></div>
          <p>Generando versión...</p>
        </div>
      ) : (
        <>
          <label className="editor-label">Nombre del Curso</label>
          <textarea
            name="nombre_curso"
            value={temario.nombre_curso || ""}
            onChange={(e) =>
              setTemario({ ...temario, nombre_curso: e.target.value })
            }
            className="input-titulo"
          />

          <label className="editor-label">Descripción General</label>
          <textarea
            name="descripcion_general"
            value={temario.descripcion_general || ""}
            onChange={(e) =>
              setTemario({ ...temario, descripcion_general: e.target.value })
            }
            className="textarea-descripcion"
          />

          <div className="duracion-info">
            <p>
              <strong>Duración total:</strong> {totalHoras} h
            </p>
            <p>
              <strong>Tiempo estimado por subtema:</strong> {horasPorSubtema} h
            </p>
          </div>

          <h3>Temario Detallado</h3>
          {(temario.temario || []).map((cap, i) => (
            <div key={i} className="capitulo-editor">
              <div className="capitulo-titulo-con-numero">
                <h4>Capítulo {i + 1}</h4>
                <input
                  value={cap.capitulo || ""}
                  onChange={(e) =>
                    handleFieldChange(i, null, "capitulo", e.target.value)
                  }
                  className="input-capitulo"
                  placeholder="Nombre del capítulo"
                />
              </div>

              <ul>
                {(cap.subcapitulos || []).map((sub, j) => {
                  const subObj =
                    typeof sub === "object" ? sub : { nombre: sub };
                  return (
                    <li key={j}>
                      <div className="subcapitulo-item-detallado">
                        <input
                          value={subObj.nombre || ""}
                          onChange={(e) =>
                            handleFieldChange(i, j, "nombre", e.target.value)
                          }
                          className="input-subcapitulo"
                          placeholder="Nombre del subcapítulo"
                        />
                        <div className="subcapitulo-meta-inputs">
                          <input
                            type="number"
                            value={subObj.tiempo_subcapitulo_min || ""}
                            onChange={(e) =>
                              handleFieldChange(
                                i,
                                j,
                                "tiempo_subcapitulo_min",
                                e.target.value
                              )
                            }
                            className="input-tiempo-sub"
                            placeholder="Min"
                          />
                          <input
                            type="number"
                            value={subObj.sesion || ""}
                            onChange={(e) =>
                              handleFieldChange(i, j, "sesion", e.target.value)
                            }
                            className="input-sesion-sub"
                            placeholder="Ses."
                          />
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </>
      )}

      <div className="acciones-footer">
        <button
          className="btn-guardar"
          onClick={handleSave}
          disabled={guardando}
        >
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>
        <button className="btn-secundario" onClick={exportarPDF}>
          Exportar PDF
        </button>
        <button className="btn-secundario" onClick={exportarExcel}>
          Exportar Excel
        </button>
      </div>
    </div>
  );
}

export default EditorDeTemario;





