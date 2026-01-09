// src/components/VersionesTemario.jsx
import React, { useEffect, useMemo, useState } from "react";
import "./VersionesTemario.css";

// 🔁 Exportar CSV
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

// Helpers
const stripTrailingSlash = (s = "") => s.replace(/\/+$/, "");
const joinUrl = (base, path) => `${stripTrailingSlash(base)}${path.startsWith("/") ? "" : "/"}${path}`;

async function fetchJsonOrThrow(url, options) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }

  if (!res.ok) {
    const msg = data?.error || data?.message || `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

// Intenta varios endpoints hasta que uno funcione (evita adivinar tu path exacto)
async function tryMany(candidates, options) {
  let lastErr = null;
  for (const url of candidates) {
    try {
      return await fetchJsonOrThrow(url, options);
    } catch (e) {
      lastErr = e;
      // Si es 401/403, ya no intentes más rutas: es auth, no path
      if (e?.status === 401 || e?.status === 403) throw e;
      // Si es 404, prueba el siguiente
      continue;
    }
  }
  throw lastErr || new Error("No se pudo conectar a ningún endpoint");
}

/**
 * Modal de versiones:
 * - lista versiones
 * - restaurar
 * - exportar CSV
 *
 * Props:
 * - cursoId: string
 * - apiBase: string (ej: https://.../versiones)
 * - token: string (Bearer token opcional)
 * - visible: bool
 * - onClose: fn
 * - onRestore: fn(json)
 */
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
    if (!visible || !cursoId || !apiBase) return;

    const run = async () => {
      setLoading(true);
      setErr("");

      const q = `?cursoId=${encodeURIComponent(cursoId)}`;

      // ✅ Fallback según tu API real (por screenshots):
      // - /list (raíz) o /versiones/list (dentro) o GET /versiones
      const candidates = [
        joinUrl(apiBase, `/list${q}`),
        joinUrl(apiBase, `/versiones/list${q}`),
        joinUrl(apiBase, `/versiones${q}`), // por si GET /versiones lista
      ];

      try {
        const data = await tryMany(candidates, { method: "GET", headers });

        // normaliza a array
        const items = Array.isArray(data) ? data : (Array.isArray(data?.items) ? data.items : []);
        setVersiones(items);
      } catch (e) {
        setVersiones([]);
        setErr(e?.message || "Error cargando versiones");
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [visible, cursoId, apiBase, headers]);

  if (!visible) return null;

  const handleGetOne = async (versionId) => {
    const q = `?cursoId=${encodeURIComponent(cursoId)}&versionId=${encodeURIComponent(versionId)}`;

    // ✅ Fallback para obtener una versión:
    // - /get?cursoId&versionId
    // - /versiones/{id}?cursoId=...
    // - /versiones/get?...
    const candidates = [
      joinUrl(apiBase, `/get${q}`),
      joinUrl(apiBase, `/versiones/get${q}`),
      joinUrl(apiBase, `/versiones/${encodeURIComponent(versionId)}?cursoId=${encodeURIComponent(cursoId)}`),
    ];

    return await tryMany(candidates, { method: "GET", headers });
  };

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
              <li key={v.versionId || v.id || JSON.stringify(v)} className="item-version">
                <div className="col-info">
                  <strong>{new Date(v.createdAt || v.fecha_creacion || Date.now()).toLocaleString()}</strong>
                  <div className="nota">{v.nota_version || v.nota_usuario || v.nota || "Sin nota"}</div>
                  <div className="mini">
                    {v.isLatest ? "Última" : ""} {v.size ? `• ${v.size} bytes` : ""}
                  </div>
                </div>

                <div className="col-actions">
                  <button
                    className="btn"
                    onClick={async () => {
                      try {
                        const json = await handleGetOne(v.versionId || v.id);
                        onRestore?.(json?.contenido ?? json); // por si viene envuelto
                      } catch (e) {
                        setErr(e?.message || "No se pudo restaurar");
                      }
                    }}
                  >
                    Restaurar
                  </button>

                  <button
                    className="btn sec"
                    onClick={async () => {
                      try {
                        const json = await handleGetOne(v.versionId || v.id);
                        const payload = json?.contenido ?? json;
                        downloadTemarioAsExcel(payload, cursoId, v.versionId || v.id || "version");
                      } catch (e) {
                        setErr(e?.message || "No se pudo descargar");
                      }
                    }}
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
