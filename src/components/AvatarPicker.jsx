// src/components/AvatarPicker.jsx
import { useEffect, useState } from "react";
import { getCurrentUser, fetchUserAttributes, updateUserAttribute } from "aws-amplify/auth";

// Carga todas las imágenes del folder avatars (minús./MAYÚS.)
const avatarModules = import.meta.glob("../assets/avatars/*.{png,PNG,jpg,JPG,jpeg,JPEG,webp,WEBP,svg,SVG}", {
  eager: true,
});
const AVATAR_URLS = Object.values(avatarModules).map((m) => m.default);

// Clave de storage por usuario (email opcional)
const storageKey = (email) => `app_avatar_url:${email || "anon"}`;

export default function AvatarPicker({ isOpen, onClose, email, onSaved }) {
  const [selected, setSelected] = useState("");

  useEffect(() => {
    if (!isOpen) return;
    const prev = localStorage.getItem(storageKey(email)) || "";
    setSelected(prev);
  }, [isOpen, email]);

  const save = async () => {
    if (!selected) return;

    // 1) Persistencia local (pintado instantáneo)
    localStorage.setItem(storageKey(email), selected);

    // 2) Persistencia en Cognito (sobrevive cierre de sesión)
    try {
      const flag = String(import.meta.env.VITE_AVATAR_SYNC_COGNITO || "true");
      if (flag === "true") {
        await updateUserAttribute({ userAttribute: { attributeKey: 'picture', value: selected } });
      }
    } catch (err) {
      console.log("No se pudo sincronizar avatar con Cognito (ok):", err?.message || err);
    }

    // 3) Aviso global (tu Sidebar lo escucha)
    window.dispatchEvent(new CustomEvent("profilePhotoUpdated", { detail: { photoUrl: selected } }));

    onSaved?.(selected);
    onClose?.();
  };

  const clear = async () => {
    localStorage.removeItem(storageKey(email));
    try {
      const flag = String(import.meta.env.VITE_AVATAR_SYNC_COGNITO || "true");
      if (flag === "true") {
        await updateUserAttribute({ userAttribute: { attributeKey: 'picture', value: "" } });
      }
    } catch { }
    window.dispatchEvent(new CustomEvent("profilePhotoUpdated", { detail: { photoUrl: "" } }));
    onSaved?.("");
    onClose?.();
  };

  if (!isOpen) return null;

  return (
    <div
      onClick={(e) => e.target === e.currentTarget && onClose?.()}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,.45)",
        display: "grid",
        placeItems: "center",
        zIndex: 9999,
      }}
    >
      <div
        style={{
          width: "min(680px, 92vw)",
          background: "#0f172a",
          color: "#e5e7eb",
          borderRadius: 14,
          padding: 18,
          boxShadow: "0 20px 60px rgba(0,0,0,.5)",
        }}
      >
        <h3 style={{ margin: 0, marginBottom: 12 }}>Elige tu avatar</h3>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(84px, 1fr))",
            gap: 12,
            maxHeight: 360,
            overflow: "auto",
            paddingRight: 4,
          }}
        >
          {AVATAR_URLS.map((url) => {
            const isSel = selected === url;
            const name = (url.split("/").pop() || "");
            return (
              <button
                key={url}
                onClick={() => setSelected(url)}
                title={name}
                style={{
                  width: 84,
                  height: 84,
                  borderRadius: "50%",
                  overflow: "hidden",
                  border: isSel ? "3px solid #22d3ee" : "2px solid #475569",
                  padding: 0,
                  cursor: "pointer",
                  background: "transparent",
                }}
              >
                <img
                  src={url}
                  alt={name}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              </button>
            );
          })}
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 14, justifyContent: "flex-end" }}>
          <button onClick={clear} style={btn("ghost")}>Quitar</button>
          <button onClick={onClose} style={btn("ghost")}>Cerrar</button>
          <button onClick={save} disabled={!selected} style={btn("primary")}>
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}

function btn(variant) {
  const base = {
    padding: "8px 14px",
    borderRadius: 10,
    border: "1px solid transparent",
    cursor: "pointer",
    fontWeight: 600,
  };
  if (variant === "primary")
    return { ...base, background: "#035b6e", color: "#ffffff" }; // color primario
  return { ...base, background: "transparent", color: "#e5e7eb", borderColor: "#334155" };
}
