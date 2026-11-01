// src/utils/auth.js
export function isAdmin(session) {
  if (!session) return false;

  // Extraer grupos desde idToken o accessToken
  const idGroups =
    session?.tokens?.idToken?.payload?.["cognito:groups"] ?? [];

  const accessGroups =
    session?.tokens?.accessToken?.payload?.["cognito:groups"] ?? [];

  const groups = idGroups.length ? idGroups : accessGroups;

  if (!Array.isArray(groups)) return false;

  // Normalizar: todo a minúsculas
  const norm = groups.map(g => String(g).toLowerCase().trim());

  // Tu grupo se convierte a: "administrador"
  return norm.includes("administrador");
}
