// src/components/HistorialTemarios.jsx
import React, { useEffect, useMemo, useState } from "react";
import "./HistorialTemarios.css";

/**
 * HistorialTemarios
 * - Lista versiones guardadas de un curso (S3 con versioning, vía tu Lambda / API Gateway).
 * - Permite: recargar, filtrar por cantidad (últimas N), descargar JSON, exportar a Excel (CSV),
 *   y cargar una versión al editor (onPickVersion).
 *
 * Requisitos:
 * - VITE_API_URL: base URL de tu API Gateway (sin slash final), ej: https://xxxxx.execute-api.us-east-1.amazonaws.com/dev2
 * - Endpoints existentes:
 *   GET  {API}/temarios?cursoId=ID
 *   GET  {API}/temarios/{versionId}?cursoId=ID
 *
 * Props:
 * - cursoId: string (ej: "aws-serverless-basico")
 * - onPickVersion: (json: any) => void   // Para colocar esa versión en tu editor
 */
export default function HistorialTemarios({ cursoId, onPickVersion }) {
  const API_URL = import.meta.env.VITE_API_URL?.replace(/\/$/, "");
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [cantidad, setCantidad] = useState(5); // últimas N por defecto
  const [filtroTexto, setFiltroTexto] = useState("");

  // Header de autorización si usas Cognito (toma token del localStorage)
  const authHeader = useMemo(() => {
    try {
      const token =
        sessionStorage.getItem("id_token") ||
        sessionStorage.getItem("access_token") ||
        sessionStorage.getItem("jwtToken") ||
        "";
      return token ? { Authorization: `Bearer ${token}` } : {};
    } catch {
      return {};
    }
  }, []);

  // Cargar lista de versiones
  async function fetchVersions() {
    if (!API_URL || !cursoId) return;
    setLoading(true);
    setErr("");
    try {
      const url = `${API_URL}/temarios?cursoId=${encodeURIComponent(cursoId)}`;
      const res = await fetch(url, { headers: { "Content-Type": "application/json", ...authHeader } });
      if (!res.ok) throw new Error(`GET versiones ${res.status}`);
      const data = await res.json();
      setVersions(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e?.message || "No se pudo obtener el historial");
      setVersions([]);
    } finally {
      setLoading(false);
    }
  }

  // Trae JSON de una versión específica
  async function fetchVersionJson(versionId) {
    const url = `${API_URL}/temarios/${encodeURIComponent(versionId)}?cursoId=${encodeURIComponent(cursoId)}`;
    const res = await fetch(url, { headers: { "Content-Type": "application/json", ...authHeader } });
    if (!res.ok) throw new Error(`GET versión ${res.status}`);
    return await res.json();
  }

  // Descargar archivo (JSON o CSV)
  function downloadBlob(content, filename, mime) {
    const blob = new Blob([content], { type: mime });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      URL.revokeObjectURL(link.href);
      link.remove();
    }, 0);
  }

  // Convierte la estructura "temario" a CSV simple (compatible Excel)
  function buildCsvFromTemario(json) {
    const rows = [];
    rows.push(["Capítulo", "Duración (min)", "Teoría/Práctica", "Objetivos Capítulo", "Subcapítulo", "Tiempo Subcap.", "Sesión"]);
    const lista = Array.isArray(json?.temario) ? json.temario : [];
    for (const cap of lista) {
      const capTitulo = cap?.capitulo ?? "";
      const dur = cap?.tiempo_capitulo_min ?? "";
      const dist = cap?.porcentaje_teoria_practica_capitulo ?? "";
      const obj = Array.isArray(cap?.objetivos_capitulo)
        ? cap.objetivos_capitulo.join(" | ")
        : (cap?.objetivos_capitulo ?? "");
      const subs = Array.isArray(cap?.subcapitulos) ? cap.subcapitulos : [];
      if (subs.length === 0) {
        rows.push([capTitulo, dur, dist, obj, "", "", ""]);
      } else {
        for (const sub of subs) {
          const nombre = typeof sub === "object" ? (sub?.nombre ?? "") : String(sub ?? "");
          const tsub = typeof sub === "object" ? (sub?.tiempo_subcapitulo_min ?? "") : "";
          const ses = typeof sub === "object" ? (sub?.sesion ?? "") : "";
          rows.push([capTitulo, dur, dist, obj, nombre, tsub, ses]);
        }
      }
    }
    // a CSV
    return rows.map(r => r.map(escapeCsv).join(",")).join("\n");
  }

  function escapeCsv(v) {
    const s = String(v ?? "");
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  }

  // Acciones UI
  async function handleCargar(versionId) {
    try {
      const json = await fetchVersionJson(versionId);
      onPickVersion?.(json);
    } catch (e) {
      alert("No se pudo cargar la versión: " + (e?.message || "Error"));
    }
  }

  async function handleDescargarJson(versionId, nombre = "temario") {
    try {
      const json = await fetchVersionJson(versionId);
      const fname = `${slug(nombre || "temario")}_${versionId}.json`;
      downloadBlob(JSON.stringify(json, null, 2), fname, "application/json;charset=utf-8");
    } catch (e) {
      alert("No se pudo descargar JSON: " + (e?.message || "Error"));
    }
  }

  async function handleExportarCsv(versionId, nombre = "temario") {
    try {
      const json = await fetchVersionJson(versionId);
      const csv = buildCsvFromTemario(json);
      const fname = `${slug(nombre || "temario")}_${versionId}.csv`;
      downloadBlob(csv, fname, "text/csv;charset=utf-8");
    } catch (e) {
      alert("No se pudo exportar CSV: " + (e?.message || "Error"));
    }
  }

  // Helpers
  function slug(s) {
    return String(s || "")
      .toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
  }

  // Efecto: cargar al montar
  useEffect(() => {
    fetchVersions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cursoId, API_URL]);

  // Lista filtrada y recortada (últimas N)
  const filtered = useMemo(() => {
    const text = filtroTexto.trim().toLowerCase();
    let list = versions;
    if (text) {
      list = list.filter(v =>
        (v?.nota || "").toLowerCase().includes(text) ||
        (v?.autorEmail || "").toLowerCase().includes(text) ||
        (v?.versionId || "").toLowerCase().includes(text)
      );
    }
    return list.slice(0, Math.max(1, Number(cantidad) || 5));
  }, [versions, filtroTexto, cantidad]);

  return (
    <section className="historial-box">
      <div className="historial-header">
        <div className="historial-title">
          <span className="folder-emoji">📂</span>
          <strong>Historial de versiones</strong>
          <span className="muted">— {cursoId || "sin-id"}</span>
        </div>
        <div className="historial-actions">
          <label className="inline">
            Mostrar:
            <select
              value={cantidad}
              onChange={(e) => setCantidad(e.target.value)}
              className="form-control small"
            >
              <option value="5">Últimas 5</option>
              <option value="10">Últimas 10</option>
              <option value="20">Últimas 20</option>
              <option value="50">Últimas 50</option>
              <option value="9999">Todas</option>
            </select>
          </label>
          <input
            className="form-control small"
            placeholder="Filtrar por nota, autor o versión…"
            value={filtroTexto}
            onChange={(e) => setFiltroTexto(e.target.value)}
          />
          <button className="btn" onClick={fetchVersions} disabled={loading}>
            {loading ? "Actualizando…" : "Actualizar"}
          </button>
        </div>
      </div>

      {err ? (
        <div className="alert error">{err}</div>
      ) : loading ? (
        <div className="alert">Cargando…</div>
      ) : filtered.length === 0 ? (
        <div className="alert">No hay versiones registradas o no se pudieron cargar.</div>
      ) : (
        <div className="historial-list">
          {filtered.map((v) => (
            <div key={v.versionId} className="historial-item">
              <div className="meta">
                <div className="row">
                  <span className="meta-label">Versión:</span>
                  <code className="mono">{v.versionId}</code>
                  {v.isLatest ? <span className="badge">latest</span> : null}
                </div>
                <div className="row">
                  <span className="meta-label">Fecha:</span>
                  <span>{v.createdAt ? new Date(v.createdAt).toLocaleString() : "-"}</span>
                </div>
                <div className="row">
                  <span className="meta-label">Tamaño:</span>
                  <span>{typeof v.size === "number" ? `${v.size} bytes` : "-"}</span>
                </div>
                <div className="row">
                  <span className="meta-label">Autor:</span>
                  <span>{v.autorEmail || "-"}</span>
                </div>
                <div className="row">
                  <span className="meta-label">Nota:</span>
                  <span>{v.nota || "-"}</span>
                </div>
              </div>
              <div className="actions">
                <button className="btn primary" onClick={() => handleCargar(v.versionId)}>
                  Cargar en editor
                </button>
                <button className="btn" onClick={() => handleDescargarJson(v.versionId, cursoId)}>
                  Descargar JSON
                </button>
                <button className="btn warning" onClick={() => handleExportarCsv(v.versionId, cursoId)}>
                  Exportar Excel (CSV)
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
