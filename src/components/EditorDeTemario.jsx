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

function EditorDeTemario({ temarioInicial, onRegenerate, onSave, isLoading }) {
  const [temario, setTemario] = useState(temarioInicial);
  const [guardando, setGuardando] = useState(false);
  const [okUi, setOkUi] = useState("");
  const [errorUi, setErrorUi] = useState("");

  // 🔹 Calcula horas totales y tiempo por capítulo/subcapítulo
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

  useEffect(() => {
    setTemario(temarioInicial);
  }, [temarioInicial]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setTemario((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    setGuardando(true);
    setOkUi("");
    setErrorUi("");

    try {
      const nota = window.prompt(
        "Agrega una nota para esta versión:",
        "Guardado automático"
      );
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

  const exportarPDF = async () => {
    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.getWidth();
    const encabezado = await toDataURL(encabezadoImagen);
    const pie = await toDataURL(pieDePaginaImagen);

    doc.addImage(encabezado, "PNG", 0, 0, pageWidth, 100);
    doc.setFont("helvetica", "bold");
    doc.text(temario.nombre_curso || "Temario", pageWidth / 2, 120, {
      align: "center",
    });

    let y = 150;
    doc.setFontSize(12);
    doc.setFont("helvetica", "normal");
    doc.text(`Duración total: ${totalHoras} h`, 20, y);
    y += 15;
    doc.text(`Tiempo estimado por subtema: ${horasPorSubtema} h`, 20, y);
    y += 30;

    (temario.temario || []).forEach((cap, i) => {
      doc.setFont("helvetica", "bold");
      doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, 20, y);
      y += 15;

      (cap.subcapitulos || []).forEach((sub, j) => {
        const nombre =
          typeof sub === "object" && sub.nombre ? sub.nombre : sub;
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

  if (!temario) return null;

  return (
    <div className="editor-container">
      <h2>📘 Editor de Temario</h2>

      {okUi && <div className="msg ok">{okUi}</div>}
      {errorUi && <div className="msg error">{errorUi}</div>}

      <label className="editor-label">Nombre del Curso</label>
      <textarea
        name="nombre_curso"
        value={temario.nombre_curso || ""}
        onChange={handleInputChange}
        className="input-titulo"
      />

      <label className="editor-label">Descripción General</label>
      <textarea
        name="descripcion_general"
        value={temario.descripcion_general || ""}
        onChange={handleInputChange}
        className="textarea-descripcion"
      />

      <label className="editor-label">Audiencia</label>
      <textarea
        name="audiencia"
        value={temario.audiencia || ""}
        onChange={handleInputChange}
        className="textarea-descripcion"
      />

      <label className="editor-label">Prerrequisitos</label>
      <textarea
        name="prerrequisitos"
        value={
          Array.isArray(temario.prerrequisitos)
            ? temario.prerrequisitos.join("\n")
            : temario.prerrequisitos || ""
        }
        onChange={(e) =>
          handleInputChange({
            target: {
              name: "prerrequisitos",
              value: e.target.value.split("\n"),
            },
          })
        }
        className="textarea-descripcion"
      />

      <label className="editor-label">Objetivos Generales</label>
      <textarea
        name="objetivos"
        value={
          Array.isArray(temario.objetivos)
            ? temario.objetivos.join("\n")
            : temario.objetivos || ""
        }
        onChange={(e) =>
          handleInputChange({
            target: {
              name: "objetivos",
              value: e.target.value.split("\n"),
            },
          })
        }
        className="textarea-descripcion"
      />

      <div className="duracion-info">
        <p>
          <strong>Duración total:</strong> {totalHoras} horas
        </p>
        <p>
          <strong>Tiempo por subtema:</strong> {horasPorSubtema} h aprox.
        </p>
      </div>

      <h3>Temario Detallado</h3>
      {(temario.temario || []).map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <h4>
            Capítulo {i + 1}: {cap.capitulo}
          </h4>
          <ul>
            {(cap.subcapitulos || []).map((sub, j) => (
              <li key={j}>
                {typeof sub === "object" ? sub.nombre : sub}
                <span className="tiempo-subtema">
                  ⏱ {horasPorSubtema} h aprox.
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}

      <div className="acciones-footer">
        <button className="btn-guardar" onClick={handleSave} disabled={guardando}>
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




