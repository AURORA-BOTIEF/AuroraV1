// src/utils/downloadExcel.js
// Exporta temario a Excel con estilos profesionales y soporte UTF-8

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Estilos para celdas
const styles = {
  header: {
    font: { bold: true, sz: 14, color: { rgb: "FFFFFF" } },
    fill: { fgColor: { rgb: "1B5784" } },
    alignment: { horizontal: "center", vertical: "center" },
    border: {
      top: { style: "thin", color: { rgb: "000000" } },
      bottom: { style: "thin", color: { rgb: "000000" } },
      left: { style: "thin", color: { rgb: "000000" } },
      right: { style: "thin", color: { rgb: "000000" } }
    }
  },
  title: {
    font: { bold: true, sz: 16, color: { rgb: "1B5784" } },
    alignment: { horizontal: "left", vertical: "center" }
  },
  infoLabel: {
    font: { bold: true, sz: 11, color: { rgb: "495057" } },
    fill: { fgColor: { rgb: "F8F9FA" } },
    alignment: { horizontal: "left", vertical: "center" }
  },
  infoValue: {
    font: { sz: 11 },
    alignment: { horizontal: "left", vertical: "center" }
  },
  capitulo: {
    font: { bold: true, sz: 11, color: { rgb: "1B5784" } },
    fill: { fgColor: { rgb: "E3F2FD" } },
    alignment: { horizontal: "left", vertical: "center" },
    border: {
      top: { style: "thin", color: { rgb: "CCCCCC" } },
      bottom: { style: "thin", color: { rgb: "CCCCCC" } },
      left: { style: "thin", color: { rgb: "CCCCCC" } },
      right: { style: "thin", color: { rgb: "CCCCCC" } }
    }
  },
  subcapitulo: {
    font: { sz: 10 },
    alignment: { horizontal: "left", vertical: "center", wrapText: true },
    border: {
      top: { style: "thin", color: { rgb: "E0E0E0" } },
      bottom: { style: "thin", color: { rgb: "E0E0E0" } },
      left: { style: "thin", color: { rgb: "E0E0E0" } },
      right: { style: "thin", color: { rgb: "E0E0E0" } }
    }
  },
  numero: {
    font: { sz: 10 },
    alignment: { horizontal: "center", vertical: "center" },
    border: {
      top: { style: "thin", color: { rgb: "E0E0E0" } },
      bottom: { style: "thin", color: { rgb: "E0E0E0" } },
      left: { style: "thin", color: { rgb: "E0E0E0" } },
      right: { style: "thin", color: { rgb: "E0E0E0" } }
    }
  }
};

function toRowsFromTemario(temario) {
  const rows = [];
  const cellStyles = [];
  
  // Título principal
  rows.push([`TEMARIO DE CURSO: ${(temario?.nombre_curso || "").toUpperCase()}`]);
  cellStyles.push([{ ...styles.title, font: { ...styles.title.font, sz: 18 } }]);
  
  rows.push([]); // Espacio
  cellStyles.push([]);
  
  // Información general del curso
  rows.push(["INFORMACIÓN GENERAL"]);
  cellStyles.push([{ ...styles.header, alignment: { horizontal: "left", vertical: "center" } }]);
  
  const infoFields = [
    ["Nombre del curso", temario?.nombre_curso || ""],
    ["Versión de tecnología", temario?.version_tecnologia || ""],
    ["Horas totales", temario?.horas_totales || ""],
    ["Número de sesiones", temario?.numero_sesiones || ""],
    ["EOL (Soporte)", temario?.EOL || ""],
    ["Distribución Teoría/Práctica", temario?.porcentaje_teoria_practica_general || ""],
    ["Audiencia", temario?.audiencia || ""],
    ["Prerrequisitos", temario?.prerrequisitos || ""],
    ["Objetivos", temario?.objetivos || ""]
  ];
  
  infoFields.forEach(([label, value]) => {
    if (value) {
      rows.push([label, value]);
      cellStyles.push([styles.infoLabel, styles.infoValue]);
    }
  });
  
  // Descripción general (si existe)
  if (temario?.descripcion_general) {
    rows.push([]);
    cellStyles.push([]);
    rows.push(["DESCRIPCIÓN GENERAL"]);
    cellStyles.push([{ ...styles.header, alignment: { horizontal: "left", vertical: "center" } }]);
    rows.push([temario.descripcion_general]);
    cellStyles.push([{ ...styles.infoValue, alignment: { ...styles.infoValue.alignment, wrapText: true } }]);
  }
  
  rows.push([]); // Espacio
  cellStyles.push([]);
  rows.push([]); // Espacio
  cellStyles.push([]);
  
  // Headers de la tabla de contenido
  rows.push(["CONTENIDO DETALLADO"]);
  cellStyles.push([{ ...styles.header, alignment: { horizontal: "left", vertical: "center" } }]);
  
  rows.push(["Capítulo", "Subcapítulo", "Duración (min)", "Sesión", "Distribución T/P", "Objetivos del Capítulo"]);
  cellStyles.push([
    styles.header, styles.header, styles.header, 
    styles.header, styles.header, styles.header
  ]);

  // Contenido de capítulos
  (temario?.temario || []).forEach((cap) => {
    const dist = cap?.porcentaje_teoria_practica_capitulo || "";
    const tiempoCapitulo = cap?.tiempo_capitulo_min ? `${cap.tiempo_capitulo_min} min` : "";
    const objetivos = Array.isArray(cap?.objetivos_capitulo)
      ? cap.objetivos_capitulo.join(" • ")
      : cap?.objetivos_capitulo || "";

    if (Array.isArray(cap?.subcapitulos) && cap.subcapitulos.length > 0) {
      cap.subcapitulos.forEach((sub, index) => {
        const nombre = typeof sub === "object" ? sub?.nombre || "" : sub || "";
        const minutos = typeof sub === "object" ? sub?.tiempo_subcapitulo_min || "" : "";
        const sesion = typeof sub === "object" ? sub?.sesion || "" : "";
        
        // Solo mostrar info del capítulo en la primera fila
        if (index === 0) {
          rows.push([
            cap?.capitulo || "", 
            nombre, 
            minutos, 
            sesion, 
            dist, 
            objetivos
          ]);
          cellStyles.push([
            styles.capitulo, styles.subcapitulo, styles.numero,
            styles.numero, styles.subcapitulo, styles.subcapitulo
          ]);
        } else {
          rows.push(["", nombre, minutos, sesion, "", ""]);
          cellStyles.push([
            styles.subcapitulo, styles.subcapitulo, styles.numero,
            styles.numero, styles.subcapitulo, styles.subcapitulo
          ]);
        }
      });
    } else {
      // Capítulo sin subcapítulos
      rows.push([cap?.capitulo || "", "", tiempoCapitulo, "", dist, objetivos]);
      cellStyles.push([
        styles.capitulo, styles.subcapitulo, styles.numero,
        styles.numero, styles.subcapitulo, styles.subcapitulo
      ]);
    }
  });

  return { rows, cellStyles };
}

export async function downloadExcelTemario(temario) {
  const filenameBase = (temario?.nombre_curso || "temario")
    .toString()
    .trim()
    .replace(/\s+/g, "_")
    .replace(/[^\w\-_.]/g, ""); // Limpiar caracteres especiales

  const timestamp = new Date().toISOString().slice(0, 10);
  const filename = `${filenameBase}_${timestamp}`;

  try {
    const XLSX = (await import("xlsx")).default;
    const { rows, cellStyles } = toRowsFromTemario(temario);
    
    // Crear worksheet
    const ws = XLSX.utils.aoa_to_sheet(rows);
    
    // Aplicar estilos a las celdas
    cellStyles.forEach((rowStyles, rowIndex) => {
      rowStyles.forEach((style, colIndex) => {
        const cellAddress = XLSX.utils.encode_cell({ r: rowIndex, c: colIndex });
        if (ws[cellAddress] && style) {
          ws[cellAddress].s = style;
        }
      });
    });
    
    // Configurar anchos de columna
    const colWidths = [
      { wch: 25 }, // Capítulo
      { wch: 40 }, // Subcapítulo  
      { wch: 12 }, // Duración
      { wch: 8 },  // Sesión
      { wch: 18 }, // Distribución
      { wch: 50 }  // Objetivos
    ];
    ws['!cols'] = colWidths;
    
    // Crear workbook
    const wb = XLSX.utils.book_new();
    
    // Configurar propiedades del documento con UTF-8
    wb.Props = {
      Title: `Temario: ${temario?.nombre_curso || "Curso"}`,
      Subject: "Temario de Curso",
      Author: "Sistema de Temarios",
      CreatedDate: new Date(),
      Application: "Generador de Temarios"
    };
    
    // Agregar worksheet
    XLSX.utils.book_append_sheet(wb, ws, "Temario");
    
    // Configurar opciones de escritura con soporte UTF-8
    const writeOptions = {
      bookType: "xlsx",
      type: "array",
      compression: true,
      Props: wb.Props
    };
    
    const wbout = XLSX.write(wb, writeOptions);
    
    // Crear blob con encoding UTF-8 explícito
    const blob = new Blob([wbout], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;charset=UTF-8",
    });
    
    downloadBlob(blob, `${filename}.xlsx`);
    
  } catch (error) {
    console.warn("Error creando Excel, usando CSV como fallback:", error);
    
    // Fallback CSV mejorado con UTF-8 BOM
    const { rows } = toRowsFromTemario(temario);
    
    // Agregar BOM para UTF-8
    const BOM = '\uFEFF';
    const csv = BOM + rows
      .map((r) =>
        r
          .map((cell) => {
            const v = (cell ?? "").toString().replace(/"/g, '""');
            return `"${v}"`;
          })
          .join(",")
      )
      .join("\r\n"); // Usar CRLF para mejor compatibilidad

    const blob = new Blob([csv], { 
      type: "text/csv;charset=utf-8;" 
    });
    
    downloadBlob(blob, `${filename}.csv`);
  }
}
