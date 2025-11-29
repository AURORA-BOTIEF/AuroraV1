// src/components/VersionesTemario.jsx
import React, { useEffect, useState } from "react";
import "./VersionesTemario.css";

// 🔁 Función incrustada para exportar a CSV (sin import externo)
function downloadTemarioAsExcel(temarioJson, cursoId = "curso", versionId = "version") {
  const lines = [];
  const safe = (v) => {
    const s = (v ?? "").toString().replace(/"/g, '""');
    return /[",\n]/.test(s) ? `"${s}"` : s;
  };

  lines.push(["Campo", "Valor"].map(safe).join(","));
  lines.push(["Nombre del curso", temarioJson?.nombre_curso || ""].map(safe).join(","));  
  lines.push(["Versión tecnología", temarioJson?.version_tecnologia || ""].map(safe).join(","));
  lines.push(["Horas totales", temarioJson?.horas_totales || ""].map(safe).join(","));
  lines.push(["Número de sesiones", temarioJson?.numero_sesiones || ""].map(safe).join(","));
  lines.push(["EOL", temarioJson?.EOL || ""].map(safe).join(","));
  lines.push(["% Teoría/Práctica general", temarioJson?.porcentaje_teoria_practica_general || ""].map(safe).join(","));
  lines.push([]);
  lines.push(["Descripción general", (temarioJson?.descripcion_general || "").replace(/\n/g, " ")].map(safe).join(","));
  lines.push(["Audiencia", (temarioJson?.audiencia || "").replace(/\n/g, " ")].map(safe).join(","));
  lines.push(["Prerrequisitos", (temarioJson?.prerrequisitos || "").replace(/\n/g, " ")].map(safe).join(","));
  lines.push(["Objetivos", (temarioJson?.objetivos || "").replace(/\n/g, " ")].map(safe).join(","));
  lines.push([]);
  lines.push(["Capítulo", "Subcapítulo", "Duración cap (min)", "Distribución cap", "Tiempo sub (min)", "Sesión"].map(safe).join(","));
  for (const cap of (temarioJson?.temario || [])) {
    const capTitulo = cap?.capitulo || "";
    const dur = cap?.tiempo_capitulo_min ?? "";
    const dist = cap?.porcentaje_teoria_practica_capitulo || "";
    const subs = cap?.subcapitulos || [];
    if (!subs.length) {
      lines.push([capTitulo, "", dur, dist, "", ""].map(safe).join(","));
    } else {
      for (const sub of subs) {
        const nombreSub = typeof sub === "object" ? (sub?.nombre || "") : (sub ?? "");
        const tSub = typeof sub === "object" ? (sub?.tiempo_subcapitulo_min ?? "") : "";
        const ses = typeof sub === "object" ? (sub?.sesion ?? "") : "";
        lines.push([capTitulo, nombreSub, dur, dist, tSub, ses].map(safe).join(","));
      }
    }
  }
  const csv = lines.join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const file = `${cursoId}_${versionId}.csv`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = file;
  document.body.appendChild(a);
  a.click();
  URL.revokeObjectURL(a.href);
  a.remove();
}

/**
 * Panel de versiones que lista el historial y permite descargar cada versión en CSV/Excel.
 */
function VersionesTemario({ cursoId, apiBase, visible, onClose, onRestore }) {
  const [versiones, setVersiones] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!visible || !cursoId) return;
    setLoading(true);
    setErr("");
    fetch(`${apiBase}/temarios?cursoId=${encodeURIComponent(cursoId)}`)
      .then((r) => (r.ok ? r.json() : r.json().then((e) => Promise.reject(e))))
      .then(setVersiones)
      .catch((e) => setErr(e?.error || "Error cargando versiones"))
      .finally(() => setLoading(false));
  }, [visible, cursoId, apiBase]);

  if (!visible) return null;

  return (
    <div className="versiones-overlay" role="dialog" aria-modal="true">
      <div className="versiones-card">
        <button className="btn-cerrar" onClick={onClose} aria-label="Cerrar">✖</button>
        <h3>📑 Versiones de <code>{cursoId}</code></h3>

        {loading && <p>Cargando…</p>}
        {err && <div className="error-mensaje">{err}</div>}

        {!loading && !err && (
          <ul className="lista-versiones">
            {versiones.map((v) => (
              <li key={v.versionId} className="item-version">
                <div className="col-info">
                  <strong>{new Date(v.createdAt).toLocaleString()}</strong>
                  <div className="nota">{v.nota || "Sin nota"}</div>
                  <div className="mini">
                    {v.isLatest ? "Última" : ""} {v.size ? `• ${v.size} bytes` : ""}
                  </div>
                </div>
                <div className="col-actions">
                  <button
                    className="btn"
                    onClick={() =>
                      fetch(`${apiBase}/temarios/${encodeURIComponent(v.versionId)}?cursoId=${encodeURIComponent(cursoId)}`)
                        .then((r) => r.json())
                        .then(onRestore)
                    }
                  >
                    Restaurar
                  </button>
                  <button
                    className="btn sec"
                    onClick={() =>
                      fetch(`${apiBase}/temarios/${encodeURIComponent(v.versionId)}?cursoId=${encodeURIComponent(cursoId)}`)
                        .then((r) => r.json())
                        .then((json) => downloadTemarioAsExcel(json, cursoId, v.versionId))
                    }
                  >
                    Excel ⬇️
                  </button>
                </div>
              </li>
            ))}
            {versiones.length === 0 && <li>No hay versiones aún.</li>}
          </ul>
        )}
      </div>
    </div>
  );
}

export default VersionesTemario;


