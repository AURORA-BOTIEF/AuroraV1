// src/components/EditorDeTemario.jsx (FINAL NETEC – restaurado y mejorado)
import React, { useState, useEffect } from "react";
import jsPDF from "jspdf";
import { fetchAuthSession } from "aws-amplify/auth";
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

const slugify = (str = "") =>
  String(str)
    .normalize("NFD")
    .replace(/[\u00-~]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "curso";

function EditorDeTemario({ temarioInicial, onSave, isLoading }) {
  const [temario, setTemario] = useState(temarioInicial);
  const [userEmail, setUserEmail] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [errorUi, setErrorUi] = useState("");
  const [okUi, setOkUi] = useState("");
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
    setTemario(temarioInicial);
  }, [temarioInicial]);

  // --- CAMBIO DE CAMPOS ---
  const handleFieldChange = (capIndex, subIndex, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (subIndex === null) {
      nuevo.temario[capIndex][field] = value;
    } else {
      if (typeof nuevo.temario[capIndex].subcapitulos[subIndex] !== "object") {
        nuevo.temario[capIndex].subcapitulos[subIndex] = {
          nombre: nuevo.temario[capIndex].subcapitulos[subIndex],
        };
      }
      nuevo.temario[capIndex].subcapitulos[subIndex][field] =
        field.includes("tiempo") || field === "sesion"
          ? parseInt(value, 10) || 0
          : value;
    }
    setTemario(nuevo);
  };

  // --- AGREGAR CAPÍTULO ---
  const agregarCapitulo = () => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.push({
      capitulo: `Nuevo capítulo ${nuevo.temario.length + 1}`,
      tiempo_capitulo_min: 60,
      objetivos_capitulo: "",
      subcapitulos: [
        { nombre: "Nuevo tema 1", tiempo_subcapitulo_min: 30, sesion: 1 },
      ],
    });
    setTemario(nuevo);
  };

  // --- AGREGAR TEMA ---
  const agregarTema = (capIndex) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario[capIndex].subcapitulos.push({
      nombre: `Nuevo tema ${nuevo.temario[capIndex].subcapitulos.length + 1}`,
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevo);
  };

  // --- AJUSTAR TIEMPOS SEGÚN HORAS DE SESIÓN ---
  const ajustarTiempos = () => {
    const horas = temario?.horas_por_sesion || 7;
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
    setOkUi(`⏱️ Tiempos ajustados a ${horas}h totales`);
  };

  // --- GUARDAR VERSIÓN ---
  const handleSaveClick = async () => {
    setErrorUi("");
    setOkUi("");
    setGuardando(true);
    const nota =
      window.prompt("Escribe una nota para esta versión (opcional):") || "";
    try {
      await onSave?.({ ...temario, autor: userEmail }, nota);
      setOkUi("✅ Versión guardada correctamente");
    } catch (err) {
      console.error(err);
      setErrorUi("Error al guardar la versión");
    } finally {
      setGuardando(false);
    }
  };

  // --- EXPORTAR PDF PROFESIONAL ---
  const exportarPDF = async () => {
    try {
      const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
      const azul = "#005A9C";
      const negro = "#000000";
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = { top: 210, bottom: 100, left: 40, right: 40 };
      const contentWidth = pageWidth - margin.left - margin.right;
      const encabezado = await toDataURL(encabezadoImagen);
      const pie = await toDataURL(pieDePaginaImagen);
      let y = margin.top;

      const addPageIfNeeded = (h = 20) => {
        if (y + h > pageHeight - margin.bottom) {
          doc.addPage();
          y = margin.top;
        }
      };

      // --- Título principal ---
      doc.setFont("helvetica", "bold");
      doc.setFontSize(22);
      doc.setTextColor(azul);
      doc.text(temario?.nombre_curso || "Temario del Curso", pageWidth / 2, y, { align: "center" });
      y += 40;

      // --- Secciones introductorias ---
      const secciones = [
        { titulo: "Descripción General", texto: temario?.descripcion_general },
        { titulo: "Audiencia", texto: temario?.audiencia },
        { titulo: "Prerrequisitos", texto: temario?.prerrequisitos },
        { titulo: "Objetivos", texto: temario?.objetivos },
      ];

      secciones.forEach((sec) => {
        if (!sec.texto) return;
        addPageIfNeeded(60);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(14);
        doc.setTextColor(azul);
        doc.text(sec.titulo, margin.left, y);
        y += 18;
        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        doc.setTextColor(negro);
        const texto = doc.splitTextToSize(
          Array.isArray(sec.texto) ? sec.texto.join("\n") : sec.texto,
          contentWidth
        );
        texto.forEach((linea) => {
          addPageIfNeeded(14);
          doc.text(linea, margin.left, y);
          y += 14;
        });
        y += 10;
      });

      // --- Título del temario ---
      addPageIfNeeded(40);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azul);
      doc.text("Temario", margin.left, y);
      y += 30;

      // --- Capítulos y subcapítulos ---
      temario.temario.forEach((cap, i) => {
        addPageIfNeeded(40);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        const titulo = doc.splitTextToSize(
          `Capítulo ${i + 1}: ${cap.capitulo}`,
          contentWidth
        );
        titulo.forEach((linea) => {
          doc.text(linea, margin.left, y);
          y += 14;
        });

        if (cap.objetivos_capitulo?.length) {
          addPageIfNeeded(20);
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          doc.setTextColor(negro);
          const texto = doc.splitTextToSize(
            `Objetivos: ${
              Array.isArray(cap.objetivos_capitulo)
                ? cap.objetivos_capitulo.join(" ")
                : cap.objetivos_capitulo
            }`,
            contentWidth
          );
          texto.forEach((linea) => {
            addPageIfNeeded(14);
            doc.text(linea, margin.left + 15, y);
            y += 14;
          });
        }

        cap.subcapitulos.forEach((sub, j) => {
          addPageIfNeeded(14);
          const subObj = typeof sub === "object" ? sub : { nombre: sub };
          const nombre = subObj.nombre || "";
          const tiempo = subObj.tiempo_subcapitulo_min
            ? `${subObj.tiempo_subcapitulo_min} min`
            : "";
          const sesion = subObj.sesion ? `• Sesión ${subObj.sesion}` : "";
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          doc.setTextColor(negro);
          doc.text(`${i + 1}.${j + 1} ${nombre}`, margin.left + 20, y);
          if (tiempo || sesion) {
            doc.text(`${tiempo} ${sesion}`.trim(), pageWidth - margin.right, y, {
              align: "right",
            });
          }
          y += 12;
        });
        y += 15;
      });

      // --- Encabezado y pie de página ---
      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        const propsEnc = doc.getImageProperties(encabezado);
        const altoEnc = pageWidth * (propsEnc.height / propsEnc.width);
        doc.addImage(encabezado, "PNG", 0, 0, pageWidth, altoEnc);
        const propsPie = doc.getImageProperties(pie);
        const altoPie = pageWidth * (propsPie.height / propsPie.width);
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
      setOkUi("✅ PDF exportado correctamente");
    } catch (err) {
      console.error("Error PDF:", err);
      setErrorUi("Error al generar el PDF");
    }
  };

  const exportarExcel = () => {
    downloadExcelTemario(temario);
    setOkUi("✅ Excel exportado correctamente");
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

      {temario.temario.map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <h4>Capítulo {i + 1}</h4>
          <input
            value={cap.capitulo}
            onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
            className="input-capitulo"
          />
          <label>Objetivos del Capítulo</label>
          <textarea
            value={
              Array.isArray(cap.objetivos_capitulo)
                ? cap.objetivos_capitulo.join("\n")
                : cap.objetivos_capitulo
            }
            onChange={(e) =>
              handleFieldChange(i, null, "objetivos_capitulo", e.target.value.split("\n"))
            }
            className="textarea-objetivos-capitulo"
          />
          <ul>
            {cap.subcapitulos.map((sub, j) => (
              <li key={j} className="subcapitulo-item">
                <span>{i + 1}.{j + 1}</span>
                <input
                  value={sub.nombre}
                  onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)}
                />
                <input
                  type="number"
                  value={sub.tiempo_subcapitulo_min}
                  onChange={(e) =>
                    handleFieldChange(i, j, "tiempo_subcapitulo_min", e.target.value)
                  }
                  placeholder="min"
                />
                <input
                  type="number"
                  value={sub.sesion}
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

      <div className="agregar-capitulo-container">
        <button className="btn-agregar-capitulo" onClick={agregarCapitulo}>
          ➕ Agregar Capítulo
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
                />
                PDF
              </label>
              <label>
                <input
                  type="radio"
                  checked={exportTipo === "excel"}
                  onChange={() => setExportTipo("excel")}
                />
                Excel
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

export default EditorDeTemario;



