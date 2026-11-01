// src/components/VersionesTemario.jsx
import React, { useEffect, useMemo, useState } from "react";
import "./VersionesTemario.css";

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

const stripTrailingSlash = (s = "") => s.replace(/\/+$/, "");
const joinUrl = (base, path) => `${stripTrailingSlash(base)}${path.startsWith("/") ? "" : "/"}${path}`;

async function fetchJsonOrThrow(url, options) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }

  if (!res.ok) {
    const msg = data?.error || data?.message || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function VersionesTemario({ cursoId, apiBase, token = "", visible, onClose, onRestore }) {
  const [versiones, setVersiones] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const headers = useMemo(() => {
    const h = { "Content-Type": "application/json" };
    if (token) h.Authorization = `Bearer ${token}`;
    return h;
  }, [token]);

  useEffect(() => {
    if (!visible || !apiBase) return;

    const run = async () => {
      setLoading(true);
      setErr("");

      // ✅ LISTAR: GET al recurso /versiones (no existe /list)
      const url = joinUrl(apiBase, "/versiones");

      try {
        const data = await fetchJsonOrThrow(url, { method: "GET", headers });
        const items = Array.isArray(data) ? data : [];
        setVersiones(items);
      } catch (e) {
        setVersiones([]);
        setErr(e?.message || "Error cargando versiones");
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [visible, apiBase, headers]);

  if (!visible) return null;

  return (
    <div className="versiones-overlay" role="dialog" aria-modal="true">
      <div className="versiones-card">
        <button className="btn-cerrar" onClick={onClose} aria-label="Cerrar">✖</button>
        <h3>📑 Versiones {cursoId ? <>de <code>{cursoId}</code></> : null}</h3>

        {loading && <p>Cargando…</p>}
        {err && <div className="error-mensaje">{err}</div>}

        {!loading && !err && (
          <ul className="lista-versiones">
            {versiones.map((v) => (
              <li key={v.versionId || v.id || JSON.stringify(v)} className="item-version">
                <div className="col-info">
                  <strong>{new Date(v.createdAt || v.fecha_creacion || Date.now()).toLocaleString()}</strong>
                  <div className="nota">{v.nota_version || v.nota_usuario || v.nota || "Sin nota"}</div>
                </div>

                <div className="col-actions">
                  <button
                    className="btn"
                    onClick={() => onRestore?.(v.contenido || v)}
                  >
                    Restaurar
                  </button>

                  <button
                    className="btn sec"
                    onClick={() => downloadTemarioAsExcel(v.contenido || v, cursoId || "curso", v.versionId || "version")}
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
