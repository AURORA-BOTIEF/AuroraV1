// src/components/EditorDeTemario.jsx (versión con agregado de capítulos, temas y ajuste de tiempos)
import React, { useState, useEffect, useRef } from "react";
import jsPDF from 'jspdf';
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from '../assets/encabezado.png';
import pieDePaginaImagen from '../assets/pie_de_pagina.png';
import "./EditorDeTemario.css";

const API_BASE = import.meta.env.VITE_TEMARIOS_API || "";

function slugify(str = "") {
  return String(str)
    .normalize("NFD").replace(/[\u00-~]/g, "")
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
  const [vista, setVista] = useState('detallada');
  const [mostrarFormRegenerar, setMostrarFormRegenerar] = useState(false);

  const [guardando, setGuardando] = useState(false);
  const [errorUi, setErrorUi] = useState("");
  const [okUi, setOkUi] = useState("");
  const [modalExportar, setModalExportar] = useState(false);
  const [exportTipo, setExportTipo] = useState("pdf");

  const pdfContentRef = useRef(null);

  const [params, setParams] = useState({
    tecnologia: temarioInicial?.version_tecnologia || '',
    tema_curso: temarioInicial?.tema_curso || temarioInicial?.nombre_curso || '',
    extension_curso_dias: temarioInicial?.numero_sesiones || 1,
    nivel_dificultad: temarioInicial?.nivel_dificultad || 'basico',
    audiencia: temarioInicial?.audiencia || '',
    enfoque: temarioInicial?.enfoque || ''
  });

  useEffect(() => {
    setTemario(temarioInicial);
  }, [temarioInicial]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setTemario(prev => ({ ...prev, [name]: value }));
  };

  const handleFieldChange = (capIndex, subIndex, fieldName, value) => {
    const nuevoTemario = JSON.parse(JSON.stringify(temario));
    let targetObject;

    if (subIndex === null) {
      targetObject = nuevoTemario.temario[capIndex];
    } else {
      if (typeof nuevoTemario.temario[capIndex].subcapitulos[subIndex] !== 'object') {
        nuevoTemario.temario[capIndex].subcapitulos[subIndex] = {
          nombre: nuevoTemario.temario[capIndex].subcapitulos[subIndex]
        };
      }
      targetObject = nuevoTemario.temario[capIndex].subcapitulos[subIndex];
    }

    const numericFields = ['tiempo_capitulo_min', 'tiempo_subcapitulo_min', 'sesion'];
    targetObject[fieldName] = numericFields.includes(fieldName) ? parseInt(value, 10) || 0 : value;
    setTemario(nuevoTemario);
  };

  const handleSaveClick = async () => {
    setErrorUi("");
    setOkUi("");
    setGuardando(true);
    const nota = window.prompt(
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

  const exportarPDF = async () => {
    setOkUi("Generando PDF...");
    try {
      const doc = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'letter' });
      const azulNetec = "#005A9C";
      const encabezadoDataUrl = await toDataURL(encabezadoImagen);
      const pieDePaginaDataUrl = await toDataURL(pieDePaginaImagen);
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = { top: 210, bottom: 100, left: 40, right: 40 };
      let y = margin.top;

      const addPageIfNeeded = (space) => {
        if (y + space > pageHeight - margin.bottom) {
          doc.addPage();
          y = margin.top;
        }
      };

      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azulNetec);
      doc.text(temario?.nombre_curso || "Temario", pageWidth / 2, y, { align: 'center' });
      y += 40;

      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);

      temario.temario?.forEach((cap, i) => {
        addPageIfNeeded(60);
        doc.setFont("helvetica", "bold");
        doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, margin.left, y);
        y += 15;
        doc.setFont("helvetica", "normal");

        cap.subcapitulos?.forEach((sub, j) => {
          addPageIfNeeded(15);
          const subObj = typeof sub === 'object' ? sub : { nombre: sub };
          doc.text(`${i + 1}.${j + 1} ${subObj.nombre}`, margin.left + 20, y);
          y += 12;
        });
        y += 10;
      });

      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        doc.addImage(encabezadoDataUrl, 'PNG', 0, 0, pageWidth, 100);
        doc.addImage(pieDePaginaDataUrl, 'PNG', 0, pageHeight - 60, pageWidth, 60);
        doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageHeight - 30, { align: 'center' });
      }

      doc.save(`Temario_${slugify(temario?.nombre_curso)}.pdf`);
      setOkUi("PDF exportado correctamente ✔");
    } catch (err) {
      console.error(err);
      setErrorUi("Error al exportar PDF");
    }
  };

  const exportarExcel = () => {
    if (!temario) return;
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

      <div className="app-view">
        <div className="vista-selector">
          <button className={`btn-vista ${vista === 'detallada' ? 'activo' : ''}`} onClick={() => setVista('detallada')}>Vista Detallada</button>
          <button className={`btn-vista ${vista === 'resumida' ? 'activo' : ''}`} onClick={() => setVista('resumida')}>Vista Resumida</button>
        </div>

        {vista === 'detallada' && (
          <div>
            <label className="editor-label">Nombre del Curso</label>
            <textarea name="nombre_curso" value={temario?.nombre_curso || ''} onChange={handleInputChange} className="input-titulo" />

            <h3>Temario Detallado</h3>
            {(temario?.temario || []).map((cap, capIndex) => (
              <div key={capIndex} className="capitulo-editor">
                <div className="capitulo-titulo-con-numero">
                  <h4>Capítulo {capIndex + 1}:</h4>
                  <input value={cap?.capitulo || ''} onChange={(e) => handleFieldChange(capIndex, null, 'capitulo', e.target.value)} className="input-capitulo" placeholder="Nombre del capítulo" />
                </div>

                <div className="info-grid-capitulo">
                  <div className="info-item">
                    <label>Duración (min)</label>
                    <input type="number" value={cap?.tiempo_capitulo_min || ''} onChange={(e) => handleFieldChange(capIndex, null, 'tiempo_capitulo_min', e.target.value)} className="input-info-small" />
                  </div>
                </div>

                <div className="objetivos-capitulo">
                  <label>Objetivos del Capítulo</label>
                  <textarea value={Array.isArray(cap?.objetivos_capitulo) ? cap.objetivos_capitulo.join('\n') : cap?.objetivos_capitulo || ''} onChange={(e) => handleFieldChange(capIndex, null, 'objetivos_capitulo', e.target.value.split('\n'))} className="textarea-objetivos-capitulo" />
                </div>

                <ul>
                  {(cap?.subcapitulos || []).map((sub, subIndex) => {
                    const subObj = typeof sub === 'object' ? sub : { nombre: sub };
                    return (
                      <li key={subIndex}>
                        <div className="subcapitulo-item-detallado">
                          <span className="subcapitulo-numero">{capIndex + 1}.{subIndex + 1}</span>
                          <input value={subObj?.nombre || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'nombre', e.target.value)} className="input-subcapitulo" placeholder="Nombre del subcapítulo" />
                          <div className="subcapitulo-meta-inputs">
                            <input type="number" value={subObj?.tiempo_subcapitulo_min || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'tiempo_subcapitulo_min', e.target.value)} placeholder="min" />
                            <input type="number" value={subObj?.sesion || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'sesion', e.target.value)} placeholder="sesión" />
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>

                {/* 🔹 NUEVO: botón para agregar tema dentro del capítulo */}
                <div className="acciones-subcapitulos">
                  <button
                    className="btn-agregar-tema"
                    onClick={() => {
                      const nuevoTemario = JSON.parse(JSON.stringify(temario));
                      nuevoTemario.temario[capIndex].subcapitulos.push({
                        nombre: `Nuevo tema ${nuevoTemario.temario[capIndex].subcapitulos.length + 1}`,
                        tiempo_subcapitulo_min: 30,
                        sesion: 1
                      });
                      setTemario(nuevoTemario);
                    }}
                  >
                    Agregar Tema
                  </button>
                </div>
              </div>
            ))}

            {/* 🔹 NUEVO: botón global para agregar capítulos */}
            <div className="acciones-agregar">
              <button
                className="btn-agregar-capitulo"
                onClick={() => {
                  const nuevo = {
                    capitulo: `Nuevo capítulo ${temario.temario.length + 1}`,
                    tiempo_capitulo_min: 60,
                    objetivos_capitulo: [""],
                    subcapitulos: []
                  };
                  setTemario(prev => ({
                    ...prev,
                    temario: [...(prev.temario || []), nuevo]
                  }));
                }}
              >
                Agregar Capítulo
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 🔹 NUEVO: botón de ajuste de tiempos */}
      <div className="acciones-footer">
        <button
          className="btn-secundario"
          onClick={() => {
            const totalMinutos = 420; // 7 horas = 420 min
            const numCapitulos = temario.temario.length;
            if (numCapitulos === 0) return;

            const minutosPorCapitulo = Math.floor(totalMinutos / numCapitulos);
            const nuevoTemario = JSON.parse(JSON.stringify(temario));

            nuevoTemario.temario.forEach(cap => {
              cap.tiempo_capitulo_min = minutosPorCapitulo;
              const subCount = cap.subcapitulos?.length || 1;
              const minutosPorSub = Math.floor(minutosPorCapitulo / subCount);
              cap.subcapitulos.forEach(sub => {
                sub.tiempo_subcapitulo_min = minutosPorSub;
              });
            });

            setTemario(nuevoTemario);
            setOkUi("⏱️ Tiempos ajustados automáticamente");
          }}
        >
          Ajustar Tiempos Automáticamente
        </button>

        <button onClick={handleSaveClick} disabled={guardando}>{guardando ? "Guardando..." : "Guardar Versión"}</button>
        <button className="btn-secundario" onClick={() => setModalExportar(true)}>Exportar...</button>
      </div>

      {modalExportar && (
        <div className="modal-overlay" onClick={() => setModalExportar(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Exportar</h3>
              <button className="modal-close" onClick={() => setModalExportar(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="export-format">
                <label><input type="radio" checked={exportTipo === "pdf"} onChange={() => setExportTipo("pdf")} /> PDF</label>
                <label><input type="radio" checked={exportTipo === "excel"} onChange={() => setExportTipo("excel")} /> Excel</label>
              </div>
            </div>
            <div className="modal-footer">
              {exportTipo === "pdf" ? (
                <button onClick={exportarPDF} className="btn-guardar">Exportar PDF</button>
              ) : (
                <button onClick={exportarExcel} className="btn-guardar">Exportar Excel</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default EditorDeTemario;


