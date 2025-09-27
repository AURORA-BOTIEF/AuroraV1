// src/components/EditorDeTemario.jsx (VERSIÓN FINAL CON AJUSTES DE MARGEN)
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

  const handleSaveClick = async () => {
    setErrorUi("");
    setOkUi("");
    if (!API_BASE) {
      setErrorUi("Falta configurar VITE_TEMARIOS_API.");
      return;
    }
    try {
      setGuardando(true);
      const cursoId = slugify(temario?.nombre_curso || params?.tema_curso || "curso");
      const nota =
        window.prompt("Escribe una nota para esta versión (opcional):", `Guardado ${nowIso()}`) ||
        "";
      const token = localStorage.getItem("id_token") || "";
      const res = await fetch(`${API_BASE.replace(/\/$/, "")}/temarios`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ cursoId, contenido: temario, nota })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Error al guardar versión");
      setOkUi(`Versión guardada ✔ (versionId: ${data.versionId || "N/A"})`);
    } catch (err) {
      console.error(err);
      setErrorUi(err.message || "Error al guardar versión");
    } finally {
      setGuardando(false);
    }
  };

// --- FUNCIÓN PROFESIONAL PARA EXPORTAR PDF (VERSIÓN FINAL CON HELVETICA) ---
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
        
        const margin = { top: 140, bottom: 80, left: 40, right: 40 };
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

        const drawMetaInfo = () => {
            const metaData = [
                { label: "Versión:", value: temario.version_tecnologia },
                { label: "Horas Totales:", value: temario.horas_totales },
                { label: "Sesiones:", value: temario.numero_sesiones },
                { label: "EOL:", value: temario.EOL },
                { label: "Distribución:", value: temario.porcentaje_teoria_practica_general },
            ].filter(item => item.value); 

            if (metaData.length === 0) return;

            addPageIfNeeded(metaData.length * 15);
            doc.setFont("helvetica", "normal");
            doc.setFontSize(10);

            metaData.forEach(item => {
                doc.setFont("helvetica", "bold");
                doc.text(item.label, margin.left, y);
                doc.setFont("helvetica", "normal");
                doc.text(String(item.value), margin.left + 80, y);
                y += 15;
            });
            y += 15;
        };

        drawMetaInfo();

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
        drawSection("Objetivos", temario.objetivos);
        
        if (temario.temario && temario.temario.length > 0) {
            addPageIfNeeded(40);
            doc.setFont("helvetica", "bold");
            doc.setFontSize(16);
            doc.setTextColor(azulNetec);
            doc.text("Temario", margin.left, y);
            doc.setTextColor(0, 0, 0);
            y += 20;

            temario.temario.forEach(capitulo => {
                addPageIfNeeded(50);
                doc.setFont("helvetica", "bold");
                doc.setFontSize(12);
                doc.text(capitulo.capitulo, margin.left, y);
                y += 15;
                
                // <-- AJUSTE CLAVE: Cambia el formato de los objetivos de capítulo
                if (capitulo.objetivos_capitulo && capitulo.objetivos_capitulo.length > 0) {
                    const objetivos = Array.isArray(capitulo.objetivos_capitulo) ? capitulo.objetivos_capitulo : [capitulo.objetivos_capitulo];
                    const objetivosTexto = objetivos.join(' ');
                    const textoCompleto = `Objetivos: ${objetivosTexto}`;
                    
                    const textLines = doc.splitTextToSize(textoCompleto, contentWidth - 15);
                    
                    addPageIfNeeded(20 + textLines.length * 12);
                    
                    doc.setFont("helvetica", "normal");
                    doc.setFontSize(10);
                    doc.text(textLines, margin.left + 15, y);
                    y += (textLines.length * 12) + 8;
                }

                if (capitulo.subcapitulos && capitulo.subcapitulos.length > 0) {
                    doc.setFont("helvetica", "normal");
                    doc.setFontSize(10);
                    capitulo.subcapitulos.forEach(sub => {
                        addPageIfNeeded(14);
                        const nombre = typeof sub === 'object' ? sub.nombre : sub;
                        const tiempo = typeof sub === 'object' ? sub.tiempo_subcapitulo_min : '';
                        const sesion = typeof sub === 'object' ? sub.sesion : '';
                        
                        let meta = '';
                        if (tiempo) meta += `${tiempo} min`;
                        if (tiempo && sesion) meta += ' • ';
                        if (sesion) meta += `Sesión ${sesion}`;
                        
                        const subLines = doc.splitTextToSize(`• ${nombre}`, contentWidth - 80); 
                        doc.text(subLines, margin.left + 15, y);
                        
                        doc.text(meta, pageWidth - margin.right - 10, y, { align: 'right' });
                        
                        y += (subLines.length * 12) + 2;
                    });
                }
                y += 10;
            });
        }

        const totalPages = doc.internal.getNumberOfPages();

        for (let i = 1; i <= totalPages; i++) {
            doc.setPage(i);

            const propsEncabezado = doc.getImageProperties(encabezadoDataUrl);
            const altoEncabezado = pageWidth * (propsEncabezado.height / propsEncabezado.width);
            doc.addImage(encabezadoDataUrl, 'PNG', 0, 0, pageWidth, altoEncabezado);

            const propsPie = doc.getImageProperties(pieDePaginaDataUrl);
            const altoPie = pageWidth * (propsPie.height / propsPie.width);
            doc.addImage(pieDePaginaDataUrl, 'PNG', 0, pageHeight - altoPie, pageWidth, altoPie);

            const leyendaY = pageHeight - 60;
            const pageNumY = pageHeight - 45;

            doc.setFont("helvetica", "normal");
            const leyenda = "Documento generado mediante tecnología de IA bajo la supervisión y aprobación de Netec.";
            doc.setFontSize(8);
            doc.setTextColor("#888888");
            doc.text(leyenda, margin.left, leyendaY);

            doc.setFontSize(9);
            doc.setTextColor("#6c757d");
            const pageNumText = `Página ${i} de ${totalPages}`;
            doc.text(pageNumText, pageWidth / 2, pageNumY, { align: 'center' });
        }

        doc.save(`Temario_${slugify(temario.nombre_curso)}.pdf`);
        setOkUi("PDF exportado correctamente ✔");

    } catch (error) {
        console.error("Error al generar PDF:", error);
        setErrorUi("Error al generar el PDF.");
    }
};

  const exportarExcel = () => {
    if (!temario) {
      setErrorUi("No hay temario para exportar");
      return;
    }
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
        <div className="vista-info">
            {vista === 'detallada' ? (<p>📝 Vista completa con todos los campos editables organizados verticalmente</p>) : (<p>📋 Vista compacta con campos organizados en grillas para edición rápida</p>)}
        </div>

        {isLoading ? (
            <div className="spinner-container"><div className="spinner"></div><p>Generando nueva versión...</p></div>
        ) : (
            <div>
            {vista === 'detallada' ? (
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
                    <input value={cap.capitulo || ''} onChange={(e) => handleFieldChange(capIndex, null, 'capitulo', e.target.value)} className="input-capitulo" placeholder="Nombre del capítulo"/>
                    
                    <div className="info-grid-capitulo">
                        <div className="info-item">
                            <label>Duración (min)</label>
                            <input type="number" value={cap.tiempo_capitulo_min || ''} onChange={(e) => handleFieldChange(capIndex, null, 'tiempo_capitulo_min', e.target.value)} className="input-info-small"/>
                        </div>
                    </div>

                    <div className="objetivos-capitulo">
                        <label>Objetivos del Capítulo</label>
                        <textarea value={Array.isArray(cap.objetivos_capitulo) ? cap.objetivos_capitulo.join('\n') : cap.objetivos_capitulo || ''} onChange={(e) => handleFieldChange(capIndex, null, 'objetivos_capitulo', e.target.value.split('\n'))} className="textarea-objetivos-capitulo" placeholder="Un objetivo por línea"/>
                    </div>
                    
                    <ul>
                        {(cap.subcapitulos || []).map((sub, subIndex) => {
                        const subObj = typeof sub === 'object' ? sub : { nombre: sub };
                        return (
                            <li key={subIndex}>
                            <div className="subcapitulo-item-detallado">
                                <input value={subObj.nombre || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'nombre', e.target.value)} className="input-subcapitulo" placeholder="Nombre del subcapítulo"/>
                                <div className="subcapitulo-meta-inputs">
                                    <input type="number" value={subObj.tiempo_subcapitulo_min || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'tiempo_subcapitulo_min', e.target.value)} placeholder="min"/>
                                    <input type="number" value={subObj.sesion || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'sesion', e.target.value)} placeholder="sesión"/>
                                </div>
                            </div>
                            </li>
                        )
                        })}
                    </ul>
                    </div>
                ))}
                </div>
            ) : (
                <div className="vista-resumida-editable">
                <input name="nombre_curso" value={temario.nombre_curso || ''} onChange={handleInputChange} className="input-titulo-resumido" placeholder="Nombre del curso" />
                
                <h3>Temario Detallado</h3>
                {(temario.temario || []).map((cap, capIndex) => (
                    <div key={capIndex} className="capitulo-resumido">
                    <input value={cap.capitulo || ''} onChange={(e) => handleFieldChange(capIndex, null, 'capitulo', e.target.value)} className="input-capitulo-resumido" placeholder="Nombre del capítulo"/>
                    
                    <div className="info-grid-capitulo">
                        <div className="info-item">
                        <label>Duración Total (min)</label>
                        <input type="number" className="input-info-small" value={cap.tiempo_capitulo_min || ''} onChange={(e) => handleFieldChange(capIndex, null, 'tiempo_capitulo_min', e.target.value)} />
                        </div>
                    </div>

                    <div className="objetivos-capitulo-resumido">
                        <label>Objetivos del Capítulo</label>
                        <textarea className="textarea-objetivos-resumido" value={Array.isArray(cap.objetivos_capitulo) ? cap.objetivos_capitulo.join('\n') : cap.objetivos_capitulo || ''} onChange={(e) => handleFieldChange(capIndex, null, 'objetivos_capitulo', e.target.value.split('\n'))} />
                    </div>

                    <div className="subcapitulos-resumidos">
                        {(cap.subcapitulos || []).map((sub, subIndex) => {
                            const subObj = typeof sub === 'object' ? sub : { nombre: sub };
                            return (
                            <div key={subIndex} className="subcapitulo-item">
                                <input className="input-subcapitulo-resumido" value={subObj.nombre || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'nombre', e.target.value)} placeholder="Nombre del subcapítulo" />
                                <div className="subcapitulo-tiempos">
                                    <input className="input-tiempo-sub" type="number" value={subObj.tiempo_subcapitulo_min || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'tiempo_subcapitulo_min', e.target.value)} placeholder="min" />
                                    <input className="input-sesion-sub" type="number" value={subObj.sesion || ''} onChange={(e) => handleFieldChange(capIndex, subIndex, 'sesion', e.target.value)} placeholder="sesión" />
                                </div>
                            </div>
                            )
                        })}
                    </div>
                    </div>
                ))}
                </div>
            )}
            </div>
        )}
        </div>

      <div className="acciones-footer">
        <button onClick={() => setMostrarFormRegenerar(prev => !prev)}>Ajustar y Regenerar</button>
        <button className="btn-secundario" onClick={handleSaveClick} disabled={guardando}>{guardando ? "Guardando..." : "Guardar Versión"}</button>
        <button className="btn-secundario" onClick={abrirExportar}>Exportar...</button>
      </div>

      {mostrarFormRegenerar && (
        <div className="regenerar-form">{/*...*/}</div>
      )}

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
              {exportTipo === "pdf" ? (<button onClick={exportarPDF} className="btn-guardar">Exportar PDF</button>) : (<button onClick={exportarExcel} className="btn-guardar">Exportar Excel</button>)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default EditorDeTemario;


