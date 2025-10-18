import React, { useState, useEffect } from "react";
import jsPDF from "jspdf";
import { fetchAuthSession } from "aws-amplify/auth";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";

function slugify(str = "") {
  return String(str)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "curso";
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
  const [userEmail, setUserEmail] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [okUi, setOkUi] = useState("");
  const [errorUi, setErrorUi] = useState("");

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

  // === AGREGAR CAPÍTULO ===
  const agregarCapitulo = () => {
    const nuevo = {
      capitulo: `Nuevo Capítulo ${temario.temario.length + 1}`,
      objetivos_capitulo: "",
      subcapitulos: [],
    };
    setTemario((prev) => ({
      ...prev,
      temario: [...prev.temario, nuevo],
    }));
  };

  // === AGREGAR TEMA ===
  const agregarTema = (i) => {
    const nuevo = { nombre: `Nuevo Tema`, tiempo_subcapitulo_min: 0, sesion: 1 };
    const actualizado = [...temario.temario];
    actualizado[i].subcapitulos.push(nuevo);
    setTemario({ ...temario, temario: actualizado });
  };

  // === AJUSTAR TIEMPOS AUTOMÁTICAMENTE (7h = 420 min) ===
  const ajustarTiempos = () => {
    const totalCapitulos = temario.temario.reduce(
      (acc, c) => acc + (c.subcapitulos?.length || 0),
      0
    );
    if (totalCapitulos === 0) {
      alert("No hay subtemas para distribuir tiempos.");
      return;
    }

    const minutosPorTema = Math.floor(420 / totalCapitulos);
    const actualizado = temario.temario.map((cap, i) => ({
      ...cap,
      subcapitulos: cap.subcapitulos.map((sub, j) => ({
        ...sub,
        tiempo_subcapitulo_min: minutosPorTema,
        sesion: Math.ceil(((i + 1) * (j + 1)) / 3),
      })),
    }));

    setTemario({ ...temario, temario: actualizado });
    alert(`⏱️ Tiempos ajustados automáticamente (${minutosPorTema} min por tema).`);
  };

  // === CAMBIO DE CAMPOS ===
  const handleFieldChange = (capIndex, subIndex, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (subIndex === null) {
      nuevo.temario[capIndex][field] = value;
    } else {
      nuevo.temario[capIndex].subcapitulos[subIndex][field] = value;
    }
    setTemario(nuevo);
  };

  // === GUARDAR VERSIÓN ===
  const handleSaveClick = async () => {
    setOkUi("");
    setErrorUi("");
    setGuardando(true);
    try {
      await onSave({ ...temario, creado_por: userEmail });
      setOkUi("✅ Versión guardada correctamente");
    } catch (err) {
      console.error(err);
      setErrorUi("❌ Error al guardar versión");
    } finally {
      setGuardando(false);
    }
  };

  // === EXPORTAR PDF ===
  const exportarPDF = async () => {
    try {
      const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
      const azul = "#035b6e";
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = { top: 210, bottom: 100, left: 40, right: 40 };
      const contentWidth = pageWidth - margin.left - margin.right;
      let y = margin.top;

      const enc = await toDataURL(encabezadoImagen);
      const pie = await toDataURL(pieDePaginaImagen);
      const addPageIfNeeded = (space = 20) => {
        if (y + space > pageHeight - margin.bottom) {
          doc.addPage();
          y = margin.top;
        }
      };

      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azul);
      doc.text(temario.nombre_curso || "Temario del Curso", pageWidth / 2, y, { align: "center" });
      y += 40;

      temario.temario.forEach((cap, i) => {
        addPageIfNeeded(40);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, margin.left, y);
        y += 20;

        if (cap.objetivos_capitulo) {
          doc.setFontSize(10);
          const lineas = doc.splitTextToSize(cap.objetivos_capitulo, contentWidth - 20);
          lineas.forEach((l) => {
            addPageIfNeeded(14);
            doc.text(l, margin.left + 10, y);
            y += 14;
          });
        }

        cap.subcapitulos.forEach((sub, j) => {
          addPageIfNeeded(15);
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          const linea = `${i + 1}.${j + 1} ${sub.nombre}`;
          const detalle = `${sub.tiempo_subcapitulo_min || 0} min • Sesión ${sub.sesion || "-"}`;
          doc.text(linea, margin.left + 20, y);
          doc.text(detalle, pageWidth - margin.right, y, { align: "right" });
          y += 12;
        });
        y += 10;
      });

      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        const encProps = doc.getImageProperties(enc);
        const encH = pageWidth * (encProps.height / encProps.width);
        doc.addImage(enc, "PNG", 0, 0, pageWidth, encH);
        const pieProps = doc.getImageProperties(pie);
        const pieH = pageWidth * (pieProps.height / pieProps.width);
        doc.addImage(pie, "PNG", 0, pageHeight - pieH, pageWidth, pieH);
        doc.setFontSize(8);
        doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageHeight - 55, { align: "center" });
      }

      doc.save(`Temario_${slugify(temario.nombre_curso)}.pdf`);
    } catch (e) {
      console.error("Error PDF:", e);
      alert("❌ Error al generar PDF");
    }
  };

  // === EXPORTAR EXCEL ===
  const exportarExcel = () => {
    try {
      downloadExcelTemario(temario);
      alert("📊 Archivo Excel exportado correctamente");
    } catch {
      alert("❌ Error al exportar Excel");
    }
  };

  if (!temario) return null;

  return (
    <div className="editor-container">
      {(okUi || errorUi) && (
        <div className="ui-messages">
          {okUi && <div className="msg ok">{okUi}</div>}
          {errorUi && <div className="msg error">{errorUi}</div>}
        </div>
      )}

      {isLoading ? (
        <div className="spinner-container">
          <div className="spinner" />
          <p>Generando nueva versión...</p>
        </div>
      ) : (
        <>
          <div className="acciones-agregar">
            <button className="btn-agregar-capitulo" onClick={agregarCapitulo}>Agregar Capítulo</button>
            <button className="btn-secundario" onClick={ajustarTiempos}>Ajustar Tiempos</button>
          </div>

          {temario.temario.map((cap, i) => (
            <div key={i} className="capitulo-editor">
              <h4>Capítulo {i + 1}</h4>
              <input
                value={cap.capitulo}
                onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
                className="input-capitulo"
              />
              <textarea
                className="textarea-objetivos-capitulo"
                placeholder="Objetivos del capítulo..."
                value={cap.objetivos_capitulo}
                onChange={(e) => handleFieldChange(i, null, "objetivos_capitulo", e.target.value)}
              />

              <div className="acciones-subcapitulos">
                <button className="btn-agregar-tema" onClick={() => agregarTema(i)}>Agregar Tema</button>
              </div>

              <ul>
                {cap.subcapitulos.map((sub, j) => (
                  <li key={j}>
                    <div className="subcapitulo-item-detallado">
                      <span>{i + 1}.{j + 1}</span>
                      <input
                        className="input-subcapitulo"
                        value={sub.nombre}
                        onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)}
                      />
                      <div className="subcapitulo-meta-inputs">
                        <input
                          type="number"
                          value={sub.tiempo_subcapitulo_min || ""}
                          onChange={(e) => handleFieldChange(i, j, "tiempo_subcapitulo_min", e.target.value)}
                          placeholder="min"
                        />
                        <input
                          type="number"
                          value={sub.sesion || ""}
                          onChange={(e) => handleFieldChange(i, j, "sesion", e.target.value)}
                          placeholder="sesión"
                        />
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}

      <div className="acciones-footer">
        <button className="btn-secundario" onClick={exportarPDF}>Exportar PDF</button>
        <button className="btn-secundario" onClick={exportarExcel}>Exportar Excel</button>
        <button className="btn-guardar" onClick={handleSaveClick} disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>
      </div>
    </div>
  );
}

export default EditorDeTemario;

