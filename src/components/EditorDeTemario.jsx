// src/components/EditorDeTemario.jsx (FINAL - estilo Netec original + funciones nuevas)
import React, { useState, useEffect, useRef } from "react";
import jsPDF from 'jspdf';
import { fetchAuthSession } from "aws-amplify/auth";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from '../assets/encabezado.png';
import pieDePaginaImagen from '../assets/pie_de_pagina.png';
import "./EditorDeTemario.css";

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
  const [userEmail, setUserEmail] = useState("");
  const [vista, setVista] = useState('detallada');
  const [guardando, setGuardando] = useState(false);
  const [errorUi, setErrorUi] = useState("");
  const [okUi, setOkUi] = useState("");
  const [modalExportar, setModalExportar] = useState(false);
  const [exportTipo, setExportTipo] = useState("pdf");

  useEffect(() => {
    const obtenerUsuario = async () => {
      try {
        const session = await fetchAuthSession();
        const idToken = session?.tokens?.idToken;
        const email = idToken?.payload?.email || "sin-correo";
        console.log("📩 Usuario autenticado:", email);
        setUserEmail(email);
      } catch (error) {
        console.error("⚠️ Error al obtener usuario:", error);
      }
    };
    obtenerUsuario();
  }, []);

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
      const resultado = await onSave?.({ ...temario, creado_por: userEmail }, nota);
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
    try {
      setOkUi("Generando PDF profesional...");
      setErrorUi("");

      const doc = new jsPDF({
        orientation: 'portrait',
        unit: 'pt',
        format: 'letter'
      });

      const azulNetec = "#005A9C";
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = { top: 210, bottom: 100, left: 40, right: 40 };
      const contentWidth = pageWidth - margin.left - margin.right;

      const encabezadoDataUrl = await toDataURL(encabezadoImagen);
      const pieDePaginaDataUrl = await toDataURL(pieDePaginaImagen);
      let y = margin.top;

      const addPageIfNeeded = (spaceNeeded = 20) => {
        if (y + spaceNeeded > pageHeight - margin.bottom) {
          doc.addPage();
          y = margin.top;
        }
      };

      // Título
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azulNetec);
      doc.text(temario?.nombre_curso || "Temario del Curso", pageWidth / 2, y, { align: 'center' });
      doc.setTextColor(0, 0, 0);
      y += 30;

      // Descripción general
      const secciones = [
        { titulo: "Descripción General", texto: temario?.descripcion_general },
        { titulo: "Audiencia", texto: temario?.audiencia },
        { titulo: "Prerrequisitos", texto: Array.isArray(temario?.prerrequisitos) ? temario.prerrequisitos.join('\n') : temario?.prerrequisitos },
        { titulo: "Objetivos", texto: Array.isArray(temario?.objetivos) ? temario.objetivos.join('\n') : temario?.objetivos }
      ];

      secciones.forEach(sec => {
        if (!sec.texto) return;
        addPageIfNeeded(50);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azulNetec);
        doc.text(sec.titulo, margin.left, y);
        doc.setTextColor(0, 0, 0);
        y += 14;
        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        const texto = doc.splitTextToSize(sec.texto, contentWidth);
        doc.text(texto, margin.left, y);
        y += texto.length * 12 + 15;
      });

      // Temario detallado
      if (temario?.temario?.length > 0) {
        addPageIfNeeded(40);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(16);
        doc.setTextColor(azulNetec);
        doc.text("Temario", margin.left, y);
        doc.setTextColor(0, 0, 0);
        y += 20;

        temario.temario.forEach((cap, i) => {
          addPageIfNeeded(50);
          doc.setFont("helvetica", "bold");
          doc.setFontSize(12);
          doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, margin.left, y);
          y += 15;

          if (cap.objetivos_capitulo && cap.objetivos_capitulo.length > 0) {
            const objetivos = Array.isArray(cap.objetivos_capitulo)
              ? cap.objetivos_capitulo
              : [cap.objetivos_capitulo];
            const texto = `Objetivos: ${objetivos.join(" ")}`;
            const lineas = doc.splitTextToSize(texto, contentWidth);
            doc.setFont("helvetica", "normal");
            doc.setFontSize(10);
            doc.text(lineas, margin.left + 15, y);
            y += lineas.length * 12 + 8;
          }

          cap.subcapitulos?.forEach((sub, j) => {
            addPageIfNeeded(15);
            const subObj = typeof sub === 'object' ? sub : { nombre: sub };
            const linea = `${i + 1}.${j + 1} ${subObj.nombre}`;
            const tiempo = subObj.tiempo_subcapitulo_min ? `${subObj.tiempo_subcapitulo_min} min` : "";
            const sesion = subObj.sesion ? `• Sesión ${subObj.sesion}` : "";
            doc.setFont("helvetica", "normal");
            doc.setFontSize(10);
            doc.text(linea, margin.left + 20, y);
            doc.text(`${tiempo} ${sesion}`.trim(), pageWidth - margin.right, y, { align: 'right' });
            y += 12;
          });

          y += 10;
        });
      }

      // Encabezado, pie y numeración
      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        const propsEnc = doc.getImageProperties(encabezadoDataUrl);
        const altoEnc = pageWidth * (propsEnc.height / propsEnc.width);
        doc.addImage(encabezadoDataUrl, 'PNG', 0, 0, pageWidth, altoEnc);

        const propsPie = doc.getImageProperties(pieDePaginaDataUrl);
        const altoPie = pageWidth * (propsPie.height / propsPie.width);
        doc.addImage(pieDePaginaDataUrl, 'PNG', 0, pageHeight - altoPie, pageWidth, altoPie);

        doc.setFontSize(8);
        doc.setTextColor("#666666");
        doc.text("Documento generado mediante tecnología de IA bajo la supervisión y aprobación de Netec.", margin.left, pageHeight - 70);
        doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageHeight - 55, { align: 'center' });
      }

      const nombreArchivo = `Temario_${slugify(temario?.nombre_curso)}`;
      doc.save(`${nombreArchivo}.pdf`);
      setOkUi("✅ PDF exportado correctamente");
    } catch (error) {
      console.error("Error al generar PDF:", error);
      setErrorUi("Error al generar el PDF.");
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
        </div>

        {vista === 'detallada' && (
          <div>
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

      <div className="acciones-footer">
        <button
          className="btn-secundario"
          onClick={() => {
            const totalMinutos = 420;
            const numCapitulos = temario.temario.length;
            if (numCapitulos === 0) return;
            const minutosPorCap = Math.floor(totalMinutos / numCapitulos);
            const nuevo = JSON.parse(JSON.stringify(temario));
            nuevo.temario.forEach(cap => {
              cap.tiempo_capitulo_min = minutosPorCap;
              const temas = cap.subcapitulos?.length || 1;
              const minPorTema = Math.floor(minutosPorCap / temas);
              cap.subcapitulos.forEach(sub => {
                sub.tiempo_subcapitulo_min = minPorTema;
              });
            });
            setTemario(nuevo);
            setOkUi("⏱️ Tiempos ajustados automáticamente");
          }}
        >
          Ajustar Tiempos Automáticamente
        </button>

        <button onClick={handleSaveClick} disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>
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


