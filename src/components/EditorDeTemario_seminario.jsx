import React, { useState, useEffect } from "react";
import jsPDF from "jspdf";
import { fetchAuthSession } from "aws-amplify/auth";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";

// Convertir imágenes a base64 para PDF
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

  // Obtener usuario autenticado
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

  // Actualiza el temario al cambiar el inicial
  useEffect(() => {
    setTemario({
      ...temarioInicial,
      temario: Array.isArray(temarioInicial?.temario)
        ? temarioInicial.temario
        : [],
    });
  }, [temarioInicial]);

  // === Editar campos ===
  const handleFieldChange = (capIndex, subIndex, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!nuevo.temario[capIndex]) return;

    if (subIndex === null) {
      nuevo.temario[capIndex][field] = value;
    } else {
      if (!Array.isArray(nuevo.temario[capIndex].subcapitulos))
        nuevo.temario[capIndex].subcapitulos = [];
      nuevo.temario[capIndex].subcapitulos[subIndex][field] =
        field.includes("tiempo") ? parseFloat(value) || 0 : value;
    }

    // Recalcular duración total del capítulo
    nuevo.temario[capIndex].tiempo_capitulo_min = nuevo.temario[
      capIndex
    ].subcapitulos.reduce(
      (sum, s) => sum + (parseFloat(s.tiempo_subcapitulo_min) || 0),
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
    if (!Array.isArray(nuevo.temario[capIndex].subcapitulos))
      nuevo.temario[capIndex].subcapitulos = [];
    nuevo.temario[capIndex].subcapitulos.push({
      nombre: `Nuevo tema ${nuevo.temario[capIndex].subcapitulos.length + 1}`,
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevo);
  };

  // === Ajustar tiempos automáticamente ===
  const ajustarTiempos = () => {
    if (!Array.isArray(temario.temario) || temario.temario.length === 0) return;
    const horas = temario.horas_totales || temario.horas_por_sesion || 2;
    const minutosTotales = horas * 60;
    const totalTemas = temario.temario.reduce(
      (acc, cap) => acc + (cap.subcapitulos?.length || 0),
      0
    );
    if (totalTemas === 0) return;

    const minutosPorTema = Math.floor(minutosTotales / totalTemas);
    const nuevo = JSON.parse(JSON.stringify(temario));

    nuevo.temario.forEach((cap) => {
      cap.subcapitulos.forEach((sub) => {
        sub.tiempo_subcapitulo_min = minutosPorTema;
      });
      cap.tiempo_capitulo_min = cap.subcapitulos.reduce(
        (a, s) => a + (s.tiempo_subcapitulo_min || 0),
        0
      );
    });

    setTemario(nuevo);
    setMensaje({
      tipo: "ok",
      texto: `⏱️ Tiempos ajustados a ${horas}h totales.`,
    });
  };

  // === Guardar versión ===
  const handleSaveClick = async () => {
    setGuardando(true);
    setMensaje({ tipo: "", texto: "" });
    const nota =
      window.prompt("Escribe una nota para esta versión (opcional):") || "";
    try {
      await onSave?.({ ...temario, autor: userEmail }, nota);
      setMensaje({ tipo: "ok", texto: "✅ Versión guardada correctamente" });
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: "❌ Error al guardar la versión" });
    } finally {
      setGuardando(false);
      setTimeout(() => setMensaje({ tipo: "", texto: "" }), 4000);
    }
  };

  // === Exportar PDF ===
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

      doc.setFont("helvetica", "bold");
      doc.setFontSize(22);
      doc.setTextColor(azul);
      doc.text(temario?.nombre_curso || "Seminario", pageWidth / 2, y, { align: "center" });
      y += 40;

      doc.setFont("helvetica", "normal");
      doc.setFontSize(11);
      const lines = doc.splitTextToSize(temario?.descripcion_general || "", contentWidth);
      lines.forEach((line) => {
        doc.text(line, margin.left, y);
        y += 14;
      });

      y += 20;
      doc.setFont("helvetica", "bold");
      doc.setFontSize(16);
      doc.text("Temario Detallado", margin.left, y);
      y += 20;

      temario.temario.forEach((cap, i) => {
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, margin.left, y);
        y += 14;

        doc.setFont("helvetica", "italic");
        doc.setFontSize(9);
        doc.setTextColor(negro);
        doc.text(`Duración total: ${cap.tiempo_capitulo_min || 0} min`, margin.left + 10, y);
        y += 14;

        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        const objetivos = doc.splitTextToSize(
          cap.objetivos_capitulo || "",
          contentWidth
        );
        objetivos.forEach((line) => {
          doc.text(line, margin.left + 15, y);
          y += 12;
        });

        cap.subcapitulos.forEach((sub, j) => {
          doc.text(`${i + 1}.${j + 1} ${sub.nombre}`, margin.left + 25, y);
          doc.text(`${sub.tiempo_subcapitulo_min || 0} min`, pageWidth - margin.right, y, {
            align: "right",
          });
          y += 12;
        });
        y += 10;
      });

      doc.save(`Seminario_${slugify(temario?.nombre_curso)}.pdf`);
      setMensaje({ tipo: "ok", texto: "✅ PDF exportado correctamente" });
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: "❌ Error al generar PDF" });
    }
  };

  const exportarExcel = () => {
    downloadExcelTemario(temario);
    setMensaje({ tipo: "ok", texto: "✅ Excel exportado correctamente" });
  };

  return (
    <div className="editor-container">
      {mensaje.texto && <div className={`msg ${mensaje.tipo}`}>{mensaje.texto}</div>}

      <h3>Temario Detallado</h3>

      {(temario.temario || []).map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <h4>Capítulo {i + 1}</h4>
          <input
            value={cap.capitulo || ""}
            onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
            className="input-capitulo"
          />
          <div className="duracion-total">
            ⏱️ <strong>Duración total: {cap.tiempo_capitulo_min || 0} min</strong>
          </div>
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
                <input
                  type="number"
                  value={sub.sesion || 1}
                  onChange={(e) => handleFieldChange(i, j, "sesion", e.target.value)}
                  placeholder="sesión"
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
