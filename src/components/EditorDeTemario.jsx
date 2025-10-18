// src/components/EditorDeTemario.jsx (VERSIÓN FINAL - NETEC PRO)
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

function slugify(str = "") {
  return String(str)
    .normalize("NFD")
    .replace(/[\u00-~]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "curso";
}

const nowIso = () => {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`;
};

function EditorDeTemario({ temarioInicial, onSave, isLoading }) {
  const [temario, setTemario] = useState(temarioInicial);
  const [userEmail, setUserEmail] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [errorUi, setErrorUi] = useState("");
  const [okUi, setOkUi] = useState("");

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

  // Cambiar campos
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

  // Agregar capítulo
  const agregarCapitulo = () => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    const nuevoCapitulo = {
      capitulo: `Nuevo capítulo ${nuevo.temario.length + 1}`,
      tiempo_capitulo_min: 60,
      objetivos_capitulo: "",
      subcapitulos: [
        { nombre: "Nuevo tema 1", tiempo_subcapitulo_min: 30, sesion: 1 },
        { nombre: "Nuevo tema 2", tiempo_subcapitulo_min: 30, sesion: 1 },
      ],
    };
    nuevo.temario.push(nuevoCapitulo);
    setTemario(nuevo);
  };

  // Agregar tema
  const agregarTema = (capIndex) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    const cap = nuevo.temario[capIndex];
    cap.subcapitulos.push({
      nombre: `Nuevo tema ${cap.subcapitulos.length + 1}`,
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevo);
  };

  // Ajustar tiempos automáticamente
  const ajustarTiempos = () => {
    if (!temario?.temario?.length) return;
    const horasTotales = temario.horas_por_sesion || 7;
    const minutosTotales = horasTotales * 60;
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
    setOkUi("⏱️ Tiempos ajustados automáticamente según las horas totales.");
  };

  // Guardar versión
  const handleSaveClick = async () => {
    setErrorUi("");
    setOkUi("");
    setGuardando(true);
    const nota =
      window.prompt("Escribe una nota para esta versión (opcional):", `Guardado ${nowIso()}`) ||
      "";
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

  // --- EXPORTAR PDF PROFESIONAL (colores + alineado limpio) ---
  const exportarPDF = async () => {
    try {
      const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
      const azulNetec = "#005A9C";
      const negroTexto = "#000000";
      const grisMeta = "#444444";
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

      // --- Título principal ---
      doc.setFont("helvetica", "bold");
      doc.setFontSize(22);
      doc.setTextColor(azulNetec);
      doc.text(temario?.nombre_curso || "Temario del Curso", pageWidth / 2, y, { align: "center" });
      y += 40;

      // --- Secciones iniciales ---
      const secciones = [
        { titulo: "Descripción General", texto: temario?.descripcion_general },
        { titulo: "Audiencia", texto: temario?.audiencia },
        { titulo: "Prerrequisitos", texto: temario?.prerrequisitos },
        { titulo: "Objetivos", texto: temario?.objetivos },
      ];

      secciones.forEach((sec) => {
        if (!sec.texto) return;
        addPageIfNeeded(50);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(15);
        doc.setTextColor(azulNetec);
        doc.text(sec.titulo, margin.left, y);
        y += 18;
        doc.setFont("helvetica", "normal");
        doc.setFontSize(11);
        doc.setTextColor(negroTexto);
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

      // --- Título Temario ---
      addPageIfNeeded(40);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azulNetec);
      doc.text("Temario", margin.left, y);
      y += 30;

      // --- Capítulos y Subcapítulos ---
      temario.temario.forEach((cap, i) => {
        addPageIfNeeded(40);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azulNetec);
        doc.text(`Capítulo ${i + 1}: ${cap.capitulo || ""}`, margin.left, y);
        y += 18;

        if (cap.objetivos_capitulo?.length) {
          const texto = `Objetivos: ${
            Array.isArray(cap.objetivos_capitulo)
              ? cap.objetivos_capitulo.join(" ")
              : cap.objetivos_capitulo
          }`;
          const lineas = doc.splitTextToSize(texto, contentWidth);
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          doc.setTextColor(negroTexto);
          lineas.forEach((l) => {
            addPageIfNeeded(14);
            doc.text(l, margin.left + 15, y);
            y += 14;
          });
          y += 8;
        }

        cap.subcapitulos?.forEach((sub, j) => {
          addPageIfNeeded(15);
          const subObj = typeof sub === "object" ? sub : { nombre: sub };
          const numero = `${i + 1}.${j + 1}`;
          const nombre = subObj.nombre || "";
          const tiempo = subObj.tiempo_subcapitulo_min
            ? `${subObj.tiempo_subcapitulo_min} min`
            : "";
          const sesion = subObj.sesion ? `Sesión ${subObj.sesion}` : "";

          doc.setFont("helvetica", "bold");
          doc.setFontSize(10);
          doc.setTextColor(azulNetec);
          doc.text(numero, margin.left + 10, y);

          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          doc.setTextColor(negroTexto);
          const lineasSub = doc.splitTextToSize(nombre, contentWidth - 80);
          lineasSub.forEach((ln) => {
            addPageIfNeeded(14);
            doc.text(ln, margin.left + 40, y);
            y += 12;
          });

          if (tiempo || sesion) {
            addPageIfNeeded(14);
            const tiempoSesion = `${tiempo}${tiempo && sesion ? " • " : ""}${sesion}`;
            doc.setFont("helvetica", "normal");
            doc.setFontSize(10);
            doc.setTextColor(grisMeta);
            doc.text(tiempoSesion, pageWidth - margin.right, y, { align: "right" });
            y += 16;
          } else {
            y += 8;
          }
        });
        y += 15;
      });

      // --- Encabezado / pie ---
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
        doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageHeight - 55, { align: "center" });
      }

      doc.save(`Temario_${slugify(temario?.nombre_curso)}.pdf`);
      setOkUi("✅ PDF exportado correctamente");
    } catch (e) {
      console.error("Error PDF:", e);
      setErrorUi("Error al generar el PDF.");
    }
  };

  const exportarExcel = () => {
    downloadExcelTemario(temario);
    setOkUi("✅ Excel exportado correctamente");
  };

  if (!temario) return null;

  return (
    <div className="editor-container">
      {errorUi && <div className="msg error">{errorUi}</div>}
      {okUi && <div className="msg ok">{okUi}</div>}

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
          />
          <ul>
            {cap.subcapitulos.map((sub, j) => (
              <li key={j} className="subcapitulo-item-detallado">
                <span>{i + 1}.{j + 1}</span>
                <input
                  value={sub.nombre}
                  onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)}
                  className="input-subcapitulo"
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
        <button onClick={agregarCapitulo}>Agregar Capítulo</button>
        <button onClick={ajustarTiempos}>Ajustar Tiempos</button>
        <button className="btn-secundario" onClick={exportarPDF}>
          Exportar PDF
        </button>
        <button className="btn-secundario" onClick={exportarExcel}>
          Exportar Excel
        </button>
        <button className="btn-secundario" onClick={handleSaveClick} disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>
      </div>
    </div>
  );
}

export default EditorDeTemario;


