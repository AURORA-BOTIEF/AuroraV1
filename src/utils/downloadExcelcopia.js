import * as XLSX from "xlsx";

export function downloadExcelTemario(temario) {

  // ===============================
  // 📌 HOJA 1 – PORTADA
  // ===============================
  const portadaData = [
    ["Nombre del curso", temario.nombre_curso || ""],
    ["Duración total (horas)", temario.horas_total_curso || 0],
    [],
    ["Descripción General"],
    [temario.descripcion_general || ""],
    [],
    ["Audiencia"],
    [temario.audiencia || ""],
    [],
    ["Prerrequisitos"],
    [temario.prerrequisitos || ""],
    [],
    ["Objetivos"],
    [temario.objetivos || ""],
  ];

  const wsPortada = XLSX.utils.aoa_to_sheet(portadaData);

  // Ajuste de columnas
  wsPortada["!cols"] = [{ wch: 30 }, { wch: 80 }];

  // ===============================
  // 📌 HOJA 2 – TEMARIO
  // ===============================
  const temarioRows = [
    [
      "Capítulo",
      "Objetivos del Capítulo",
      "Duración Capítulo (min)",
      "Tema",
      "Sesión",
      "Duración Tema (min)"
    ]
  ];

  temario.temario.forEach((cap, i) => {
    temarioRows.push([
      `Capítulo ${i + 1}: ${cap.capitulo}`,
      Array.isArray(cap.objetivos_capitulo)
        ? cap.objetivos_capitulo.join(", ")
        : cap.objetivos_capitulo || "",
      cap.tiempo_capitulo_min,
      "",
      "",
      ""
    ]);

    cap.subcapitulos.forEach((sub, j) => {
      temarioRows.push([
        "",
        "",
        "",
        `${i + 1}.${j + 1} ${sub.nombre}`,
        sub.sesion,
        sub.tiempo_subcapitulo_min
      ]);
    });

    temarioRows.push([]);
  });

  const wsTemario = XLSX.utils.aoa_to_sheet(temarioRows);
  wsTemario["!cols"] = [
    { wch: 40 },
    { wch: 50 },
    { wch: 20 },
    { wch: 40 },
    { wch: 10 },
    { wch: 20 }
  ];

  // ===============================
  // 📌 WORKBOOK
  // ===============================
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, wsPortada, "Portada");
  XLSX.utils.book_append_sheet(wb, wsTemario, "Temario Detallado");

  XLSX.writeFile(
    wb,
    `Temario_${temario.nombre_curso || "curso"}.xlsx`
  );
}
