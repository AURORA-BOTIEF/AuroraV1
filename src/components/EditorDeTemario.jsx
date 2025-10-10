// src/components/EditorDeTemario.jsx
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
  const [modalVersiones, setModalVersiones] = useState(false);
  const [versiones, setVersiones] = useState([]);
  const [cargandoVersiones, setCargandoVersiones] = useState(false);
  const [modalExportar, setModalExportar] = useState(false);
  const [exportTipo, setExportTipo] = useState("pdf");
  const [seleccionadas, setSeleccionadas] = useState({});

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

  // 🔧 Ajuste: Cargar campos si vienen dentro de temario.temario
  useEffect(() => {
    if (temarioInicial) {
      if (temarioInicial.temario) {
        setTemario(prev => ({
          ...prev,
          audiencia: temarioInicial.temario.audiencia || "",
          prerrequisitos: temarioInicial.temario.prerrequisitos || [],
          objetivos: temarioInicial.temario.objetivos_generales || []
        }));
      } else {
        setTemario(prev => ({
          ...prev,
          audiencia: temarioInicial.audiencia || "",
          prerrequisitos: temarioInicial.prerrequisitos || [],
          objetivos: temarioInicial.objetivos || []
        }));
      }
    }
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

  const handleParamsChange = (e) => {
    const { name, value } = e.target;
    setParams(prev => ({ ...prev, [name]: value }));
  };

  const handleRegenerateClick = () => {
    setErrorUi("");
    setOkUi("");
    onRegenerate(params);
    setMostrarFormRegenerar(false);
  };

  // <-- AJUSTE CLAVE: Guardar versión
  const handleSaveClick = async () => {
    setErrorUi("");
    setOkUi("");
    setGuardando(true);

    const nota = window.prompt("Escribe una nota para esta versión (opcional):", `Guardado ${nowIso()}`) || "";

    const resultado = await onSave(temario, nota);

    if (resultado?.success) {
      setOkUi(resultado.message);
    } else {
      setErrorUi(resultado?.message || "Error al guardar");
    }
    
    setGuardando(false);
  };

  // --- EXPORTACIÓN PDF (NUMERADA) ---
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

      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azulNetec);
      doc.text(temario.nombre_curso || "Temario del Curso", pageWidth / 2, y, { align: 'center' });
      doc.setTextColor(0, 0, 0);
      y += 30;

      const drawSection = (title, content) => {
        if (!content) return;
        const contentAsText = Array.isArray(content) ? content.join('\n') : content;
        const textLines = doc.splitTextToSize(contentAsText, contentWidth);
        const sectionHeight = 15 + (textLines.length * 12) + 20;
        addPageIfNeeded(sectionHeight);

        doc.setFont("helvetica", "bold");
        doc.setFontSize(14);
        doc.setTextColor(azulNetec);
        doc.text(title, margin.left, y);
        doc.setTextColor(0, 0, 0);
        y += 15;

        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        doc.text(textLines, margin.left, y);
        y += (textLines.length * 12) + 20;
      };

      drawSection("Descripción General", temario.descripcion_general);
      drawSection("Audiencia", temario.audiencia);
      drawSection("Prerrequisitos", temario.prerrequisitos);
      drawSection("Objetivos Generales", temario.objetivos);

      if (temario.temario && temario.temario.length > 0) {
        addPageIfNeeded(40);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(16);
        doc.setTextColor(azulNetec);
        doc.text("Temario", margin.left, y);
        doc.setTextColor(0, 0, 0);
        y += 20;

        temario.temario.forEach((capitulo, capIndex) => {
          addPageIfNeeded(50);
          doc.setFont("helvetica", "bold");
          doc.setFontSize(12);
          doc.text(`Capítulo ${capIndex + 1}: ${capitulo.capitulo}`, margin.left, y);
          y += 15;

          if (capitulo.subcapitulos && capitulo.subcapitulos.length > 0) {
            doc.setFont("helvetica", "normal");
            doc.setFontSize(10);
            capitulo.subcapitulos.forEach((sub, subIndex) => {
              addPageIfNeeded(14);
              const nombre = typeof sub === 'object' ? sub.nombre : sub;
              const subLines = doc.splitTextToSize(`${capIndex + 1}.${subIndex + 1} ${nombre}`, contentWidth - 80);
              doc.text(subLines, margin.left + 15, y);
              y += (subLines.length * 12) + 2;
            });
          }
          y += 10;
        });
      }

      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        const propsEnc = doc.getImageProperties(encabezadoDataUrl);
        const altoEnc = pageWidth * (propsEnc.height / propsEnc.width);
        doc.addImage(encabezadoDataUrl, 'PNG', 0, 0, pageWidth, altoEnc);

        const propsPie = doc.getImageProperties(pieDePaginaDataUrl);
        const altoPie = pageWidth * (propsPie.height / propsPie.width);
        doc.addImage(pieDePaginaDataUrl, 'PNG', 0, pageHeight - altoPie, pageWidth, altoPie);

        const leyendaY = pageHeight - 70;
        const pageNumY = pageHeight - 55;
        doc.setFont("helvetica", "normal");
        const leyenda = "Documento generado mediante tecnología de IA bajo supervisión de Netec.";
        doc.setFontSize(8);
        doc.setTextColor("#888");
        doc.text(leyenda, margin.left, leyendaY);

        doc.setFontSize(9);
        doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageNumY, { align: 'center' });
      }

      const nombreArchivo = temario.nombre_curso || temario.tema_curso;
      doc.save(`Temario_${slugify(nombreArchivo)}.pdf`);
      setOkUi("PDF exportado correctamente ✔");
    } catch (error) {
      console.error(error);
      setErrorUi("Error al generar el PDF.");
    }
  };

  const exportarExcel = () => {
    if (!temario) return setErrorUi("No hay temario para exportar");
    downloadExcelTemario(temario);
    setOkUi("Exportado correctamente ✔");
    setModalExportar(false);
  };

  const abrirExportar = () => {
    setModalExportar(true);
    setErrorUi("");
    setOkUi("");
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

      <div ref={pdfContentRef} style={{ display: 'none' }}></div>

      <div className="app-view">
        <div className="vista-selector">
          <button className={`btn-vista ${vista === 'detallada' ? 'activo' : ''}`} onClick={() => setVista('detallada')}>Vista Detallada</button>
          <button className={`btn-vista ${vista === 'resumida' ? 'activo' : ''}`} onClick={() => setVista('resumida')}>Vista Resumida</button>
        </div>

        {isLoading ? (
          <div className="spinner-container"><div className="spinner"></div><p>Generando nueva versión...</p></div>
        ) : (
          <div>
            <label className="editor-label">Nombre del Curso</label>
            <textarea name="nombre_curso" value={temario.nombre_curso || ''} onChange={handleInputChange} className="input-titulo" />
            
            <label className="editor-label">Descripción General</label>
            <textarea name="descripcion_general" value={temario.descripcion_general || ''} onChange={handleInputChange} className="textarea-descripcion" />
            
            <label className="editor-label">Audiencia</label>
            <textarea name="audiencia" value={temario.audiencia || ''} onChange={handleInputChange} className="textarea-descripcion" />
            
            <label className="editor-label">Prerrequisitos</label>
            <textarea name="prerrequisitos" value={Array.isArray(temario.prerrequisitos) ? temario.prerrequisitos.join('\n') : temario.prerrequisitos || ''} onChange={(e) => handleInputChange({ target: { name: 'prerrequisitos', value: e.target.value.split('\n') }})} className="textarea-descripcion" placeholder="Un prerrequisito por línea"/>
            
            <label className="editor-label">Objetivos Generales</label>
            <textarea name="objetivos" value={Array.isArray(temario.objetivos) ? temario.objetivos.join('\n') : temario.objetivos || ''} onChange={(e) => handleInputChange({ target: { name: 'objetivos', value: e.target.value.split('\n') }})} className="textarea-descripcion" placeholder="Un objetivo por línea" />

            <h3>Temario Detallado</h3>
            {(temario.temario || []).map((cap, capIndex) => (
              <div key={capIndex} className="capitulo-editor">
                <div className="capitulo-titulo-con-numero">
                  <h4>Capítulo {capIndex + 1}:</h4>
                  <input value={cap.capitulo || ''} onChange={(e) => handleFieldChange(capIndex, null, 'capitulo', e.target.value)} className="input-capitulo" placeholder="Nombre del capítulo"/>
                </div>
                <ul>
                  {(cap.subcapitulos || []).map((sub, subIndex) => {
                    const subObj = typeof sub === 'object' ? sub : { nombre: sub };
                    return (
                      <li key={subIndex}>
                        <div className="subcapitulo-item-detallado">
                          <span className="subcapitulo-numero">{capIndex + 1}.{subIndex + 1}</span>
                          <input value={subObj.nombre || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'nombre', e.target.value)} className="input-subcapitulo" placeholder="Nombre del subcapítulo"/>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="acciones-footer">
        <button onClick={() => setMostrarFormRegenerar(prev => !prev)}>Ajustar y Regenerar</button>
        <button className="btn-secundario" onClick={handleSaveClick} disabled={guardando}>{guardando ? "Guardando..." : "Guardar Versión"}</button>
        <button className="btn-secundario" onClick={abrirExportar}>Exportar...</button>
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
              {exportTipo === "pdf"
                ? <button onClick={exportarPDF} className="btn-guardar">Exportar PDF</button>
                : <button onClick={exportarExcel} className="btn-guardar">Exportar Excel</button>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default EditorDeTemario;


