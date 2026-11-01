// src/components/BotonVersionesTemario.jsx
import React, { useState } from "react";
import VersionesTemario from "./VersionesTemario";
import "./VersionesTemario.css";

/**
 * Botón flotante para abrir el panel de versiones.
 * apiBase: URL base de tu API Gateway (ej: "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2")
 * cursoId (opcional): si lo pasas, abre directo ese curso; si no, pide por prompt.
 */
export default function BotonVersionesTemario({ apiBase, cursoId: propCursoId }) {
  const [visible, setVisible] = useState(false);
  const [cursoId, setCursoId] = useState(propCursoId || "");

  const abrir = () => {
    let cid = propCursoId || cursoId;
    if (!cid) {
      cid = prompt("¿Cuál es el cursoId para ver sus versiones?", "aws-serverless-basico") || "";
    }
    if (!cid.trim()) return;
    setCursoId(cid.trim());
    setVisible(true);
  };

  return (
    <>
      <button
        className="btn-flotante-versiones"
        onClick={abrir}
        title="Ver versiones del temario"
      >
        📑
      </button>

      {visible && (
        <VersionesTemario
          cursoId={cursoId}
          apiBase={apiBase}
          visible={visible}
          onClose={() => setVisible(false)}
          onRestore={() => {}} // listo para futuro si quieres restaurar al editor
        />
      )}
    </>
  );
}
