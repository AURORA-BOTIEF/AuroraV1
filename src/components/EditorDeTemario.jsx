import React, { useState, useEffect } from "react";
import jsPDF from "jspdf";
import { fetchAuthSession } from "aws-amplify/auth";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";
import { Plus, Trash2 } from "lucide-react";

// 🔹 Convierte minutos en formato legible (ej: "1 hr 6 min")
const formatDuration = (minutos) => {
  if (!minutos || minutos < 0) return "0 min";
  const horas = Math.floor(minutos / 60);
  const mins = minutos % 60;
  if (horas === 0) return `${mins} min`;
  if (mins === 0) return `${horas} hr`;
  return `${horas} hr ${mins} min`;
};

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
    .replace(/^-+|-+$/g, "") || "curso";

// ✅ token robusto
const getAuthToken = () => {
  return (
    localStorage.getItem("id_token") ||
    sessionStorage.getItem("id_token") ||
    ""
  );
};

// ✅ headers robustos (Bearer + fallback sin Bearer)
const buildAuthHeaders = (token) => {
  const h1 = { Authorization: `Bearer ${token}` };
  const h2 = { Authorization: token };
  return { h1, h2 };
};

// ✅ parse seguro (evita romper con 401/HTML)
const safeJson = async (response) => {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { raw: text };
  }
};

function EditorDeTemario({ temarioInicial, onSave, isLoading }) {
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

  // ✅ NUEVO: Modal Versiones
  const [modalVersiones, setModalVersiones] = useState(false);
  const [cargandoVersiones, setCargandoVersiones] = useState(false);
  const [versiones, setVersiones] = useState([]);

  const API_VERSIONES =
    "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

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
    setTemario({
      ...temarioInicial,
      temario: Array.isArray(temarioInicial?.temario)
        ? temarioInicial.temario
        : [],
    });
  }, [temarioInicial]);

  // ===== CAMBIO DE CAMPOS =====
  const handleFieldChange = (capIndex, subIndex, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) nuevo.temario = [];
    if (!nuevo.temario[capIndex]) return;

    if (subIndex === null) {
      nuevo.temario[capIndex][field] = value;

      if (field === "tiempo_capitulo_min") {
        const nuevoTotal = Math.max(0, parseInt(value, 10) || 0);
        nuevo.temario[capIndex].tiempo_capitulo_min = nuevoTotal;

        const subcaps = nuevo.temario[capIndex].subcapitulos || [];
        if (subcaps.length > 0) {
          if (nuevoTotal === 0) {
            subcaps.forEach((sub) => (sub.tiempo_subcapitulo_min = 0));
          } else {
            const minutosPorSub = Math.floor(nuevoTotal / subcaps.length);
            const residuo = nuevoTotal % subcaps.length;

            subcaps.forEach((sub, idx) => {
              sub.tiempo_subcapitulo_min = Math.max(
                0,
                minutosPorSub + (idx === 0 ? residuo : 0)
              );
            });
          }
        }
      } else {
        nuevo.temario[capIndex].tiempo_capitulo_min = (
          nuevo.temario[capIndex].subcapitulos || []
        ).reduce(
          (sum, s) => sum + (parseInt(s.tiempo_subcapitulo_min) || 0),
          0
        );
      }
    } else {
      if (!Array.isArray(nuevo.temario[capIndex].subcapitulos))
        nuevo.temario[capIndex].subcapitulos = [];

      if (typeof nuevo.temario[capIndex].subcapitulos[subIndex] !== "object") {
        nuevo.temario[capIndex].subcapitulos[subIndex] = {
          nombre:
            String(nuevo.temario[capIndex].subcapitulos[subIndex]) || "Tema",
        };
      }

      if (field.includes("tiempo") || field === "sesion") {
        const parsed = parseInt(value, 10) || 0;
        nuevo.temario[capIndex].subcapitulos[subIndex][field] = Math.max(
          0,
          parsed
        );
      } else {
        nuevo.temario[capIndex].subcapitulos[subIndex][field] = value;
      }

      nuevo.temario[capIndex].tiempo_capitulo_min = (
        nuevo.temario[capIndex].subcapitulos || []
      ).reduce(
        (sum, s) => sum + (parseInt(s.tiempo_subcapitulo_min) || 0),
        0
      );
    }

    setTemario(nuevo);
  };

  // ===== AGREGAR CAPÍTULO =====
  const agregarCapitulo = () => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) nuevo.temario = [];
    nuevo.temario.push({
      capitulo: `Nuevo capítulo ${nuevo.temario.length + 1}`,
      tiempo_capitulo_min: 0,
      objetivos_capitulo: "",
      subcapitulos: [
        { nombre: "Nuevo tema 1", tiempo_subcapitulo_min: 30, sesion: 1 },
      ],
    });
    setTemario(nuevo);
  };

  // ===== ELIMINAR CAPÍTULO =====
  const eliminarCapitulo = (capIndex) => {
    if (
      !window.confirm(
        `¿Seguro que deseas eliminar el capítulo ${capIndex + 1} y todos sus temas?`
      )
    )
      return;

    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.splice(capIndex, 1);
    nuevo.temario = nuevo.temario.map((c, i) => ({
      ...c,
      capitulo: c.capitulo || `Capítulo ${i + 1}`,
    }));
    setTemario(nuevo);
    setMensaje({ tipo: "ok", texto: "🗑️ Capítulo eliminado" });
  };

  // ===== AGREGAR TEMA =====
  const agregarTema = (capIndex) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) return;
    if (!Array.isArray(nuevo.temario[capIndex].subcapitulos))
      nuevo.temario[capIndex].subcapitulos = [];
    nuevo.temario[capIndex].subcapitulos.push({
      nombre: `Nuevo tema ${nuevo.temario[capIndex].subcapitulos.length + 1}`,
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevo);
  };

  // ===== ELIMINAR TEMA =====
  const eliminarTema = (capIndex, subIndex) => {
    if (!window.confirm("¿Seguro que deseas eliminar este tema?")) return;
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario[capIndex].subcapitulos.splice(subIndex, 1);
    setTemario(nuevo);
    setMensaje({ tipo: "ok", texto: "🗑️ Tema eliminado correctamente" });
  };

  // ===== AJUSTAR TIEMPOS =====
  const ajustarTiempos = () => {
    if (!Array.isArray(temario.temario) || temario.temario.length === 0) return;
    const horas = temario?.horas_por_sesion || 2;
    const minutosTotales = horas * 60;
    const totalTemas = temario.temario.reduce(
      (acc, cap) => acc + (cap.subcapitulos?.length || 0),
      0
    );
    if (totalTemas === 0) return;

    const minutosPorTema = Math.floor(minutosTotales / totalTemas);
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.forEach((cap) => {
      if (!Array.isArray(cap.subcapitulos)) cap.subcapitulos = [];
      cap.subcapitulos.forEach((sub) => {
        sub.tiempo_subcapitulo_min = minutosPorTema;
      });
      cap.tiempo_capitulo_min = cap.subcapitulos.reduce(
        (a, s) => a + (s.tiempo_subcapitulo_min || 0),
        0
      );
    });

    setTemario(nuevo);
    setMensaje({ tipo: "ok", texto: `⏱️ Tiempos ajustados a ${horas}h` });
  };

  // ✅ GUARDAR (POST) — Combina tu lógica con auth robusto
  const handleSaveClick = async () => {
    setGuardando(true);
    setMensaje({ tipo: "", texto: "" });

    const nota = window.prompt("Escribe una nota para esta versión (opcional):") || "";

    try {
      const token = getAuthToken();
      if (!token) throw new Error("No hay id_token (localStorage/sessionStorage)");

      const bodyData = {
        cursoId:
          temario?.nombre_curso?.trim() ||
          temario?.tema_curso?.trim() ||
          `curso_${Date.now()}`,
        contenido: temario,
        autor: userEmail || "sin-correo",
        nombre_curso: temario?.nombre_curso || "",
        tecnologia: temario?.tecnologia || "",
        asesor_comercial: temario?.asesor_comercial || "",
        nombre_preventa: temario?.nombre_preventa || "",
        nota_version: nota,
        fecha_creacion: new Date().toISOString(),
      };

      const { h1, h2 } = buildAuthHeaders(token);

      // 1) Bearer
      let response = await fetch(API_VERSIONES, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...h1,
        },
        body: JSON.stringify(bodyData),
      });

      // 2) fallback sin Bearer
      if (response.status === 401 || response.status === 403) {
        response = await fetch(API_VERSIONES, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...h2,
          },
          body: JSON.stringify(bodyData),
        });
      }

      const data = await safeJson(response);

      if (!response.ok || data?.success === false) {
        throw new Error(data?.error || data?.message || `HTTP ${response.status}`);
      }

      setMensaje({ tipo: "ok", texto: "✅ Versión guardada correctamente" });
    } catch (err) {
      console.error("Error al guardar versión:", err);
      setMensaje({
        tipo: "error",
        texto: `❌ Error al guardar versión: ${err?.message || "ver consola"}`,
      });
    } finally {
      setGuardando(false);
      setTimeout(() => setMensaje({ tipo: "", texto: "" }), 4000);
    }
  };

  // ✅ VER VERSIONES (GET) — Auth robusto + sort seguro
  const verVersionesGuardadas = async () => {
    setModalVersiones(true);
    setCargandoVersiones(true);
    setVersiones([]);
    setMensaje({ tipo: "", texto: "" });

    try {
      const token = getAuthToken();
      if (!token) throw new Error("No hay id_token (localStorage/sessionStorage)");

      const { h1, h2 } = buildAuthHeaders(token);

      // 1) Bearer
      let response = await fetch(API_VERSIONES, {
        method: "GET",
        headers: { ...h1 },
      });

      // 2) fallback sin Bearer
      if (response.status === 401 || response.status === 403) {
        response = await fetch(API_VERSIONES, {
          method: "GET",
          headers: { ...h2 },
        });
      }

      const data = await safeJson(response);

      if (!response.ok) {
        throw new Error(data?.error || data?.message || `HTTP ${response.status}`);
      }

      // Normaliza posibles formas de respuesta
      const arr =
        Array.isArray(data) ? data :
        Array.isArray(data?.items) ? data.items :
        Array.isArray(data?.versiones) ? data.versiones :
        Array.isArray(data?.data) ? data.data :
        [];

      // sort seguro
      const ordenadas = Array.isArray(arr)
        ? [...arr].sort(
            (a, b) =>
              new Date(b?.fecha_creacion || 0) - new Date(a?.fecha_creacion || 0)
          )
        : [];

      setVersiones(ordenadas);
    } catch (err) {
      console.error("Error al obtener versiones:", err);
      setMensaje({
        tipo: "error",
        texto: `❌ Error al obtener versiones: ${err?.message || "ver consola"}`,
      });
      setVersiones([]);
    } finally {
      setCargandoVersiones(false);
    }
  };

  const cargarVersionEnEditor = (v) => {
    const contenido = v?.contenido || v;
    if (!contenido || typeof contenido !== "object") {
      setMensaje({ tipo: "error", texto: "❌ Versión inválida (sin contenido)" });
      return;
    }

    setTemario({
      ...contenido,
      temario: Array.isArray(contenido.temario) ? contenido.temario : [],
    });

    setModalVersiones(false);
    setMensaje({ tipo: "ok", texto: "✅ Versión cargada en el editor" });
    setTimeout(() => setMensaje({ tipo: "", texto: "" }), 3000);
  };

  // ✅ EXPORTAR PDF (con tus mejoras visuales)
  const exportarPDFLocal = async () => {
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
      const margin = { top: 230, bottom: 100, left: 60, right: 60 };
      const contentWidth = pageWidth - margin.left - margin.right;

      const encabezado = await toDataURL(encabezadoImagen);
      const pie = await toDataURL(pieDePaginaImagen);

      let y = margin.top;

      const addPageIfNeeded = (extra = 40) => {
        if (y + extra > pageHeight - margin.bottom) {
          doc.addPage();
          y = margin.top;
        }
      };

      doc.setFont("helvetica", "bold");
      doc.setFontSize(22);
      doc.setTextColor(azul);

      const tituloCurso = temario?.nombre_curso || "Temario del Curso";
      const lineasCurso = doc.splitTextToSize(tituloCurso, contentWidth - 40);
      lineasCurso.forEach((linea) => {
        doc.text(linea, pageWidth / 2, y, { align: "center" });
        y += 18;
      });

      y += 20;

      // ✅ Duración alineada a la derecha (tu mejora)
      doc.setFont("helvetica", "bolditalic");
      doc.setFontSize(12);
      doc.setTextColor(azul);
      const duracionTexto = `Duración total del curso: ${temario?.horas_total_curso || 0} horas`;
      doc.text(duracionTexto, pageWidth - margin.right, y + 10, { align: "right" });
      y += 30;

      const secciones = [
        { titulo: "Descripción General", texto: temario?.descripcion_general },
        { titulo: "Audiencia", texto: temario?.audiencia },
        { titulo: "Prerrequisitos", texto: temario?.prerrequisitos },
        { titulo: "Objetivos", texto: temario?.objetivos },
      ];

      secciones.forEach((s) => {
        if (!s.texto) return;
        addPageIfNeeded(60);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(14);
        doc.setTextColor(azul);
        doc.text(s.titulo, margin.left, y);
        y += 18;

        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        doc.setTextColor(negro);

        const lineas = doc.splitTextToSize(s.texto, contentWidth);
        lineas.forEach((linea) => {
          addPageIfNeeded(14);
          doc.text(linea, margin.left, y, { align: "justify" });
          y += 14;
        });
        y += 10;
      });

      // ✅ divisor (tu mejora)
      y += 10;
      doc.setDrawColor(150, 150, 150);
      doc.setLineWidth(0.8);
      doc.line(margin.left, y, pageWidth - margin.right, y);
      y += 25;

      addPageIfNeeded(70);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azul);
      doc.text("Temario", margin.left, y);
      y += 35;

      temario.temario.forEach((cap, i) => {
        addPageIfNeeded(60);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);

        const tituloCap = `Capítulo ${i + 1}: ${cap.capitulo}`;
        const lineasCap = doc.splitTextToSize(tituloCap, contentWidth - 40);
        lineasCap.forEach((linea) => {
          doc.text(linea, margin.left, y);
          y += 14;
        });
        y += 6;

        doc.setFont("helvetica", "italic");
        doc.setFontSize(9);
        doc.setTextColor(negro);
        doc.text(`Duración total: ${cap.tiempo_capitulo_min || 0} min`, margin.left + 10, y);
        y += 14;

        if (cap.objetivos_capitulo) {
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          const objetivos = Array.isArray(cap.objetivos_capitulo)
            ? cap.objetivos_capitulo.join(" ")
            : cap.objetivos_capitulo;
          const lines = doc.splitTextToSize(`Objetivos: ${objetivos}`, contentWidth);
          lines.forEach((line) => {
            addPageIfNeeded(12);
            doc.text(line, margin.left + 15, y, { align: "justify" });
            y += 12;
          });
          y += 10;
        }

        (cap.subcapitulos || []).forEach((sub, j) => {
          addPageIfNeeded(18);
          const subObj = typeof sub === "object" ? sub : { nombre: sub };
          const meta = `${subObj.tiempo_subcapitulo_min || 0} min • Sesión ${subObj.sesion || 1}`;

          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);

          const subTitulo = `${i + 1}.${j + 1} ${subObj.nombre}`;
          const subLineas = doc.splitTextToSize(subTitulo, contentWidth - 120);

          subLineas.forEach((linea, idx) => {
            addPageIfNeeded(12);
            doc.text(linea, margin.left + 25, y);
            if (idx === 0)
              doc.text(meta, pageWidth - margin.right, y, { align: "right" });
            y += 12;
          });
        });

        y += 20;
      });

      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);

        const propsEnc = doc.getImageProperties(encabezado);
        const altoEnc = (propsEnc.height / propsEnc.width) * pageWidth;
        doc.addImage(encabezado, "PNG", 0, 0, pageWidth, altoEnc);

        const propsPie = doc.getImageProperties(pie);
        const altoPie = (propsPie.height / propsPie.width) * pageWidth;
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
      setMensaje({ tipo: "ok", texto: "✅ PDF exportado correctamente" });
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: "❌ Error al generar PDF" });
    }
  };

  // EXPORTAR YAML 
  const exportarYAML = () => {
  if (!temario || !Array.isArray(temario.temario)) {
    setMensaje({ tipo: "error", texto: "No hay datos para exportar." });
    return;
  }

  const esPractica = (nombre = "") =>
    nombre.startsWith("Práctica:") || nombre.startsWith("Laboratorio:");

  // Convierte audiencia/prerrequisitos en listas YAML
  const toList = (v) => {
    if (Array.isArray(v)) return v.filter(Boolean);
    if (typeof v === "string") {
      return v
        .split(/\r?\n|;/)
        .map((s) => s.trim())
        .filter(Boolean);
    }
    return [];
  };

  // Mapear nivel a basic/intermediate/advanced
  const normalizarLevel = (raw) => {
    const v = String(raw || "").trim().toLowerCase();
    if (["basic", "intermediate", "advanced"].includes(v)) return v;

    // Soporta entradas comunes en español
    if (["básico", "basico"].includes(v)) return "basic";
    if (["intermedio"].includes(v)) return "intermediate";
    if (["avanzado"].includes(v)) return "advanced";

    // Heurística: si no viene, estimamos por duración
    const horas = Number(temario.horas_total_curso || 0);
    if (horas <= 16) return "basic";
    if (horas <= 32) return "intermediate";
    return "advanced";
  };

  // Bloom: si es práctica/lab => Aplicar. Si no, por duración.
  const calcularBloom = (sub) => {
    if (esPractica(sub.nombre || "")) return "Aplicar";
    const dur = Number(sub.tiempo_subcapitulo_min || 0);
    if (dur <= 20) return "Recordar";
    if (dur <= 40) return "Comprender";
    return "Analizar";
  };

  // Porcentaje teoría/práctica a nivel curso
  // (en tu UI el campo es "Porcentaje de teoría y práctica", normalmente representa teoría)
  const percentPracticeCurso = 70; // Number(temario.porcentaje_teoria_practica || 0); 
  const percentTheoryCurso = 30; // 100 - percentPracticeCurso;

  // Horas totales del curso
  const hoursTotal = temario?.horas_total_curso || 0; // Number(temario.horas_total_curso || 0);

  // ✅ Corrección: theory usa percentTheory, practice usa percentPractice
  const hoursTheory = +(hoursTotal * percentTheoryCurso / 100).toFixed(2);
  const hoursPractice = +(hoursTotal * percentPracticeCurso / 100).toFixed(2);

  // ✅ Corrección: total_duration_minutes (suma de capítulos; fallback suma de subcapítulos)
  const totalDurationMinutesFromCaps = (temario.temario || []).reduce(
    (acc, cap) => acc + (Number(cap.tiempo_capitulo_min) || 0),
    0
  );

  const totalDurationMinutesFromSubs = (temario.temario || []).reduce((acc, cap) => {
    return (
      acc +
      (cap.subcapitulos || []).reduce(
        (s, sub) => s + (Number(sub.tiempo_subcapitulo_min) || 0),
        0
      )
    );
  }, 0);

  const totalDurationMinutes =
    totalDurationMinutesFromCaps > 0
      ? totalDurationMinutesFromCaps
      : totalDurationMinutesFromSubs;

  // ===============================
  // 📌 OBJETO YAML según plantilla_objetivo.yaml
  // ===============================
  const yamlObject = {
    course: {
      title: temario.nombre_curso || "",
      description: temario.descripcion_general || ".",
      level: normalizarLevel(temario.level || temario.nivel),
      audience: toList(temario.audiencia),
      prerequisites: toList(temario.prerrequisitos),
      total_duration_minutes: totalDurationMinutes, // ✅ ahora sí
    },

    language: "es", // (IDIOMA - si tu plantilla tiene otro valor fijo, cámbialo aquí por ese valor)

    learning_outcomes: temario.objetivos || "",

    hours_total: (totalDurationMinutes / 60).toFixed(2),
    hours_theory: hoursTheory,     // ✅ corregido
    hours_practice: hoursPractice, // ✅ corregido

    modules: (temario.temario || []).map((cap, capIndex) => {
      let theoryMin = 0;
      let practiceMin = 0;

      (cap.subcapitulos || []).forEach((sub) => {
        const dur = Number(sub.tiempo_subcapitulo_min || 0);
        esPractica(sub.nombre || "") ? (practiceMin += dur) : (theoryMin += dur);
      });

      const totalMin = theoryMin + practiceMin || 1;

      const module = {
        title: cap.capitulo || "",
        duration_minutes: Number(cap.tiempo_capitulo_min || totalMin),
        percent_theory: Math.round((theoryMin / totalMin) * 100),
        percent_practice: Math.round((practiceMin / totalMin) * 100),

        lessons: (cap.subcapitulos || []).map((sub, subIndex) => ({
          title: sub.nombre || "",
          duration_minutes: Number(sub.tiempo_subcapitulo_min || 0),
          bloom_level: calcularBloom(sub), // ✅ agregado
          topics: [`${capIndex + 1}.${subIndex + 1} ${sub.nombre || ""}`],
        })),
      };

      // lab_activities (solo si hay Práctica/Laboratorio)
      const labs = (cap.subcapitulos || [])
        .filter((s) => esPractica(s.nombre || ""))
        .map((s) => s.nombre);

      if (labs.length > 0) module.lab_activities = labs;

      return module;
    }),
  };

  // Serializador YAML controlado (igual que antes)
  const toYAML = (obj, indent = 0) => {
    const space = "  ".repeat(indent);

    if (Array.isArray(obj)) {
      return obj
        .map((item) => `${space}- ${toYAML(item, indent + 1).trimStart()}`)
        .join("\n");
    }

    if (obj !== null && typeof obj === "object") {
      return Object.entries(obj)
        .map(([key, value]) => {
          if (typeof value === "object" && value !== null) {
            return `${space}${key}:\n${toYAML(value, indent + 1)}`;
          }
          return `${space}${key}: ${value ?? ""}`;
        })
        .join("\n");
    }

    return `${space}${String(obj)}`;
  };

  const yamlContent = toYAML(yamlObject);

  const blob = new Blob([yamlContent], { type: "text/yaml;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Temario_${slugify(temario.nombre_curso)}.yaml`;
  a.click();
  URL.revokeObjectURL(url);

  setMensaje({ tipo: "ok", texto: "✅ YAML exportado correctamente" });
};




  const exportarExcel = () => {
    if (!Array.isArray(temario.temario) || temario.temario.length === 0) {
      setMensaje({ tipo: "error", texto: "No hay datos para exportar." });
      return;
    }
    downloadExcelTemario(temario);
    setMensaje({ tipo: "ok", texto: "✅ Excel exportado correctamente" });
  };

  // === RENDER ===
  return (
    <div className="temario-editor-container">
      {mensaje.texto && <div className={`msg ${mensaje.tipo}`}>{mensaje.texto}</div>}

      <h3>Información general del curso</h3>

      <label>Duración total del curso (horas)</label>
      <input
        type="number"
        min="0"
        value={temario.horas_total_curso || 0}
        onChange={(e) => setTemario({ ...temario, horas_total_curso: e.target.value })}
        className="input-capitulo"
        placeholder="Ej: 40"
      />

      <label>Descripción General</label>
      <textarea
        value={temario.descripcion_general || ""}
        onChange={(e) => setTemario({ ...temario, descripcion_general: e.target.value })}
        className="textarea-objetivos-capitulo"
        placeholder="Ej: Curso introductorio..."
      />

      <label>Audiencia</label>
      <textarea
        value={temario.audiencia || ""}
        onChange={(e) => setTemario({ ...temario, audiencia: e.target.value })}
        className="textarea-objetivos-capitulo"
        placeholder="Ej: Desarrolladores..."
      />

      <label>Prerrequisitos</label>
      <textarea
        value={temario.prerrequisitos || ""}
        onChange={(e) => setTemario({ ...temario, prerrequisitos: e.target.value })}
        className="textarea-objetivos-capitulo"
        placeholder="Ej: Conocimientos básicos..."
      />

      <label>Objetivos</label>
      <textarea
        value={temario.objetivos || ""}
        onChange={(e) => setTemario({ ...temario, objetivos: e.target.value })}
        className="textarea-objetivos-capitulo"
        placeholder="Ej: Al finalizar..."
      />

      <hr style={{ margin: "20px 0" }} />

      <h3>Temario Detallado</h3>

      {(temario.temario || []).map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <h4>Capítulo {i + 1}</h4>

          <input
            value={cap.capitulo || ""}
            onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
            className="input-capitulo"
            placeholder="Nombre del capítulo"
          />

          <div className="duracion-total">
            ⏱️ Duración total:&nbsp;
            <input
              type="number"
              min="0"
              value={cap.tiempo_capitulo_min || 0}
              onChange={(e) =>
                handleFieldChange(i, null, "tiempo_capitulo_min", e.target.value)
              }
              className="input-duracion"
              style={{ width: "80px", textAlign: "center" }}
            />
            <span style={{ marginLeft: "8px", color: "#035b6e", fontWeight: 600 }}>
              {formatDuration(cap.tiempo_capitulo_min || 0)}
            </span>
          </div>

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
            placeholder="Un objetivo por línea"
          />

          <ul>
            {(cap.subcapitulos || []).map((sub, j) => (
              <li key={j} className="subcapitulo-item">
                <span>
                  {i + 1}.{j + 1}
                </span>

                <input
                  value={sub.nombre || ""}
                  onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)}
                  type="text"
                  placeholder="Nombre del tema"
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
                  className="input-sesion"
                />

                <button
                  className="btn-eliminar-tema"
                  onClick={() => eliminarTema(i, j)}
                  title="Eliminar tema"
                >
                  <Trash2 size={18} strokeWidth={2} />
                  <span>Eliminar</span>
                </button>
              </li>
            ))}
          </ul>

          <div className="acciones-capitulo">
            <button className="btn-agregar-tema" onClick={() => agregarTema(i)}>
              <Plus size={18} strokeWidth={2} />
              <span>Agregar Tema</span>
            </button>

            <button
              className="btn-eliminar-capitulo"
              onClick={() => eliminarCapitulo(i)}
              title="Eliminar este capítulo"
            >
              <Trash2 size={18} strokeWidth={2} />
              <span>Eliminar Capítulo</span>
            </button>
          </div>
        </div>
      ))}

      <div className="btn-agregar-capitulo-container">
        <button className="btn-agregar-capitulo" onClick={agregarCapitulo}>
          <Plus size={18} strokeWidth={2} />
          <span>Agregar Capítulo</span>
        </button>
      </div>

      <div className="acciones-footer">
        <button className="btn-primario" onClick={ajustarTiempos}>
          Ajustar Tiempos
        </button>

        <button className="btn-secundario" onClick={handleSaveClick} disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>

        <button className="btn-secundario" onClick={verVersionesGuardadas}>
          Ver Versiones Guardadas
        </button>

        <button className="btn-secundario" onClick={() => setModalExportar(true)}>
          Exportar
        </button>
      </div>

      {/* ✅ MODAL VERSIONES */}
      {modalVersiones && (
        <div className="modal-overlay" onClick={() => setModalVersiones(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setModalVersiones(false)}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              {cargandoVersiones ? (
                <p>Cargando versiones...</p>
              ) : versiones.length === 0 ? (
                <p>No hay versiones disponibles.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {versiones.map((v, idx) => (
                    <div
                      key={v?.id || v?._id || v?.cursoId || idx}
                      style={{
                        border: "1px solid #ddd",
                        borderRadius: 10,
                        padding: 10,
                      }}
                    >
                      <div style={{ fontWeight: 700 }}>
                        {v?.nombre_curso || v?.contenido?.nombre_curso || "Sin nombre"}
                      </div>

                      <div style={{ fontSize: 12, opacity: 0.8 }}>
                        {v?.fecha_creacion
                          ? new Date(v.fecha_creacion).toLocaleString()
                          : "Sin fecha"}
                        {" • "}
                        {v?.autor || v?.contenido?.autor || "Sin autor"}
                      </div>

                      <div style={{ marginTop: 6, fontSize: 13 }}>
                        {v?.nota_version || "Sin nota"}
                      </div>

                      <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
                        <button className="btn-guardar" onClick={() => cargarVersionEnEditor(v)}>
                          Cargar en editor
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn-secundario" onClick={() => setModalVersiones(false)}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL EXPORTAR */}
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
                />{" "}
                PDF
              </label>
              <label>
                <input
                  type="radio"
                  checked={exportTipo === "yaml"}
                  onChange={() => setExportTipo("yaml")}
                />{" "}
                Yaml
              </label>
              <label>
                <input
                  type="radio"
                  checked={exportTipo === "excel"}
                  onChange={() => setExportTipo("excel")}
                />{" "}
                Excel
              </label>
            </div>
            <div className="modal-footer">
              <button
                onClick={() => {
                  if (exportTipo === "pdf") {
                    exportarPDF(temario);
                  } else if (exportTipo === "excel") {
                    exportarExcel();
                  } else if (exportTipo === "yaml") {
                    exportarYAML();
                  }
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

// ✅ Exportar función exportarPDF para que GeneradorTemarios pueda usar la misma lógica
// (se deja como la tenías; no afecta a las versiones)
export const exportarPDF = async (temarioData) => {
  if (!temarioData || !Array.isArray(temarioData.temario)) {
    alert("No hay contenido válido para exportar.");
    return;
  }

  const { jsPDF } = await import("jspdf");

  const toDataURL2 = async (url) => {
    const res = await fetch(url);
    const blob = await res.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  };

  const encabezado = await toDataURL2("/src/assets/encabezado.png");
  const pie = await toDataURL2("/src/assets/pie_de_pagina.png");

  const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
  const azul = "#005A9C";
  const negro = "#000000";
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = { top: 220, bottom: 90, left: 50, right: 50 };
  const contentWidth = pageWidth - margin.left - margin.right;
  let y = margin.top;

  const addPageIfNeeded = (extra = 40) => {
    if (y + extra > pageHeight - margin.bottom) {
      doc.addPage();
      y = margin.top;
    }
  };

  doc.setFont("helvetica", "bold");
  doc.setFontSize(22);
  doc.setTextColor(azul);

  const tituloCurso = temarioData.nombre_curso || "Temario del Curso";
  const lineasCurso = doc.splitTextToSize(tituloCurso, contentWidth - 40);
  lineasCurso.forEach((linea) => {
    doc.text(linea, pageWidth / 2, y, { align: "center" });
    y += 18;
  });

  y += 20;
  doc.text(
    `Duración total del curso: ${temarioData.horas_total_curso || 0} horas`,
    margin.left,
    y
  );
  y += 14;

  const secciones = [
    { titulo: "Descripción General", texto: temarioData.descripcion_general },
    { titulo: "Audiencia", texto: temarioData.audiencia },
    { titulo: "Prerrequisitos", texto: temarioData.prerrequisitos },
    { titulo: "Objetivos", texto: temarioData.objetivos },
  ];

  secciones.forEach((s) => {
    if (!s.texto) return;
    addPageIfNeeded(60);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(azul);
    doc.text(s.titulo, margin.left, y);
    y += 18;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(negro);

    const lineas = doc.splitTextToSize(s.texto, contentWidth);
    lineas.forEach((linea) => {
      addPageIfNeeded(14);
      doc.text(linea, margin.left, y, { align: "justify" });
      y += 14;
    });

    y += 10;
  });

  addPageIfNeeded(50);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(20);
  doc.setTextColor(azul);
  doc.text("Temario", margin.left, y);
  y += 25;

  temarioData.temario.forEach((cap, i) => {
    addPageIfNeeded(60);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(13);
    doc.setTextColor(azul);

    const tituloCap = `Capítulo ${i + 1}: ${cap.capitulo}`;
    const lineasCap = doc.splitTextToSize(tituloCap, contentWidth - 40);
    lineasCap.forEach((linea) => {
      doc.text(linea, margin.left, y);
      y += 14;
    });
    y += 4;

    doc.setFont("helvetica", "italic");
    doc.setFontSize(9);
    doc.setTextColor(negro);
    doc.text(`Duración total: ${formatDuration(cap.tiempo_capitulo_min || 0)}`, margin.left + 10, y);
    y += 12;

    if (cap.objetivos_capitulo) {
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      const objetivos = Array.isArray(cap.objetivos_capitulo)
        ? cap.objetivos_capitulo.join(" ")
        : cap.objetivos_capitulo;

      const lines = doc.splitTextToSize(`Objetivos: ${objetivos}`, contentWidth);
      lines.forEach((line) => {
        addPageIfNeeded(12);
        doc.text(line, margin.left + 15, y, { align: "justify" });
        y += 12;
      });
      y += 10;
    }

    cap.subcapitulos.forEach((sub, j) => {
      addPageIfNeeded(16);
      const subObj = typeof sub === "object" ? sub : { nombre: sub };
      const meta = `${formatDuration(subObj.tiempo_subcapitulo_min || 0)} • Sesión ${subObj.sesion || 1}`;

      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);

      const subTitulo = `${i + 1}.${j + 1} ${subObj.nombre}`;
      const subLineas = doc.splitTextToSize(subTitulo, contentWidth - 120);

      subLineas.forEach((linea, idx) => {
        addPageIfNeeded(12);
        doc.text(linea, margin.left + 25, y);
        if (idx === 0) doc.text(meta, pageWidth - margin.right, y, { align: "right" });
        y += 12;
      });
    });

    y += 16;
  });

  const totalPages = doc.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);

    const propsEnc = doc.getImageProperties(encabezado);
    const altoEnc = (propsEnc.height / propsEnc.width) * pageWidth;
    doc.addImage(encabezado, "PNG", 0, 0, pageWidth, altoEnc);

    const propsPie = doc.getImageProperties(pie);
    const altoPie = (propsPie.height / propsPie.width) * pageWidth;
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

  doc.save(`Temario_${temarioData.nombre_curso || "curso"}.pdf`);
};

export default EditorDeTemario;
