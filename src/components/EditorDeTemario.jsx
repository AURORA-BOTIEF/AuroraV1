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

function EditorDeTemario({ temarioInicial, onSave, isLoading, totalHoras }) {
  const [temario, setTemario] = useState(temarioInicial);
  const [userEmail, setUserEmail] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [errorUi, setErrorUi] = useState("");
  const [okUi, setOkUi] = useState("");

  useEffect(() => {
    const obtenerUsuario = async () => {
      try {
        const session = await fetchAuthSession();
        const email = session?.tokens?.idToken?.payload?.email || "sin-correo";
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

  // --- Actualizar campos ---
  const handleFieldChange = (capIndex, subIndex, fieldName, value) => {
    const nuevoTemario = JSON.parse(JSON.stringify(temario));
    let target;
    if (subIndex === null) {
      target = nuevoTemario.temario[capIndex];
    } else {
      if (typeof nuevoTemario.temario[capIndex].subcapitulos[subIndex] !== "object") {
        nuevoTemario.temario[capIndex].subcapitulos[subIndex] = {
          nombre: nuevoTemario.temario[capIndex].subcapitulos[subIndex],
        };
      }
      target = nuevoTemario.temario[capIndex].subcapitulos[subIndex];
    }
    const numeric = ["tiempo_capitulo_min", "tiempo_subcapitulo_min", "sesion"];
    target[fieldName] = numeric.includes(fieldName)
      ? parseInt(value, 10) || 0
      : value;
    setTemario(nuevoTemario);
  };

  // --- Agregar capítulo ---
  const handleAgregarCapitulo = () => {
    const nuevoCap = {
      capitulo: `Nuevo capítulo ${temario.temario.length + 1}`,
      tiempo_capitulo_min: 60,
      objetivos_capitulo: "",
      subcapitulos: [
        { nombre: "Nuevo tema 1", tiempo_subcapitulo_min: 30, sesion: 1 },
        { nombre: "Nuevo tema 2", tiempo_subcapitulo_min: 30, sesion: 1 },
      ],
    };
    setTemario((prev) => ({
      ...prev,
      temario: [...prev.temario, nuevoCap],
    }));
  };

  // --- Agregar tema ---
  const handleAgregarTema = (i) => {
    const nuevoTemario = JSON.parse(JSON.stringify(temario));
    nuevoTemario.temario[i].subcapitulos.push({
      nombre: `Nuevo tema ${nuevoTemario.temario[i].subcapitulos.length + 1}`,
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevoTemario);
  };

  // --- Ajustar tiempos dinámicos ---
  const handleAjustarTiempos = () => {
    const totalMinutos = totalHoras * 60;
    const nuevoTemario = JSON.parse(JSON.stringify(temario));
    const totalSubtemas = nuevoTemario.temario.reduce(
      (sum, cap) => sum + cap.subcapitulos.length,
      0
    );
    if (totalSubtemas === 0) return alert("No hay temas para ajustar.");

    const minutosPorTema = Math.floor(totalMinutos / totalSubtemas);
    nuevoTemario.temario.forEach((cap) =>
      cap.subcapitulos.forEach((sub) => (sub.tiempo_subcapitulo_min = minutosPorTema))
    );
    setTemario(nuevoTemario);
    setOkUi(`⏱️ Tiempos ajustados automáticamente (${totalMinutos} min totales)`);
  };

  // --- Guardar versión ---
  const handleSaveClick = async () => {
    setErrorUi("");
    setOkUi("");
    setGuardando(true);
    try {
      const resultado = await onSave?.({ ...temario, creado_por: userEmail });
      if (resultado?.success ?? true) setOkUi("✅ Versión guardada correctamente");
      else setErrorUi("❌ Error al guardar la versión");
    } catch (err) {
      console.error(err);
      setErrorUi("Error al guardar la versión");
    } finally {
      setGuardando(false);
    }
  };

  // --- Exportar PDF ---
  const exportarPDF = async () => {
    try {
      const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
      const azulNetec = "#005A9C";
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = { top: 210, bottom: 100, left: 40, right: 40 };
      const contentWidth = pageWidth - margin.left - margin.right;

      const encabezadoDataUrl = await toDataURL(encabezadoImagen);
      const pieDataUrl = await toDataURL(pieDePaginaImagen);
      let y = margin.top;

      const addPageIfNeeded = (space = 20) => {
        if (y + space > pageHeight - margin.bottom) {
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

      // Temario
      if (temario?.temario?.length > 0) {
        doc.setFont("helvetica", "bold");
        doc.setFontSize(16);
        doc.setTextColor(azulNetec);
        doc.text("Temario", margin.left, y);
        y += 20;

        temario.temario.forEach((cap, i) => {
          addPageIfNeeded(40);
          doc.setFont("helvetica", "bold");
          doc.setFontSize(12);
          doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, margin.left, y);
          y += 15;

          if (cap.objetivos_capitulo) {
            const texto = `Objetivos: ${
              Array.isArray(cap.objetivos_capitulo)
                ? cap.objetivos_capitulo.join(" ")
                : cap.objetivos_capitulo
            }`;
            const lineas = doc.splitTextToSize(texto, contentWidth);
            lineas.forEach((linea) => {
              addPageIfNeeded(14);
              doc.text(linea, margin.left + 15, y);
              y += 14;
            });
            y += 10;
          }

          cap.subcapitulos?.forEach((sub, j) => {
            addPageIfNeeded(15);
            const subObj = typeof sub === "object" ? sub : { nombre: sub };
            const linea = `${i + 1}.${j + 1} ${subObj.nombre}`;
            const tiempo = subObj.tiempo_subcapitulo_min
              ? `${subObj.tiempo_subcapitulo_min} min`
              : "";
            const sesion = subObj.sesion ? `• Sesión ${subObj.sesion}` : "";
            doc.setFont("helvetica", "normal");
            doc.setFontSize(10);
            doc.text(linea, margin.left + 20, y);
            doc.text(`${tiempo} ${sesion}`.trim(), pageWidth - margin.right, y, {
              align: "right",
            });
            y += 12;
          });
          y += 10;
        });
      }

      // Encabezado y pie
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

      doc.save(`Temario_${slugify(temario?.nombre_curso)}.pdf`);
      setOkUi("✅ PDF exportado correctamente");
    } catch (e) {
      console.error("Error PDF:", e);
      setErrorUi("Error al generar el PDF.");
    }
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
          <h3>Temario Detallado</h3>
          {temario.temario.map((cap, i) => (
            <div key={i} className="capitulo-editor">
              <h4>Capítulo {i + 1}:</h4>
              <input
                value={cap.capitulo || ""}
                onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
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
                    handleFieldChange(i, null, "objetivos_capitulo", e.target.value.split("\n"))
                  }
                  className="textarea-objetivos-capitulo"
                />
              </div>
              <ul>
                {cap.subcapitulos?.map((sub, j) => (
                  <li key={j}>
                    <div className="subcapitulo-item-detallado">
                      <span>{i + 1}.{j + 1}</span>
                      <input
                        value={sub.nombre || ""}
                        onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)}
                        className="input-subcapitulo"
                      />
                      <div className="subcapitulo-meta-inputs">
                        <input
                          type="number"
                          value={sub.tiempo_subcapitulo_min || ""}
                          onChange={(e) =>
                            handleFieldChange(i, j, "tiempo_subcapitulo_min", e.target.value)
                          }
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
              <div className="acciones-subcapitulos">
                <button className="btn-agregar-tema" onClick={() => handleAgregarTema(i)}>
                  Agregar Tema
                </button>
              </div>
            </div>
          ))}
          <div className="acciones-agregar">
            <button className="btn-agregar-capitulo" onClick={handleAgregarCapitulo}>
              Agregar Capítulo
            </button>
            <button className="btn-secundario" onClick={handleAjustarTiempos}>
              Ajustar Tiempos Automáticamente
            </button>
          </div>
        </>
      )}

      <div className="acciones-footer">
        <button className="btn-secundario" onClick={exportarPDF}>
          Exportar PDF
        </button>
        <button
          className="btn-secundario"
          onClick={() => downloadExcelTemario(temario)}
        >
          Exportar Excel
        </button>
        <button onClick={handleSaveClick} disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>
      </div>
    </div>
  );
}

export default EditorDeTemario;

