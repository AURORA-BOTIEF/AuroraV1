// src/utils/auth.js
export function isAdmin(session) {
  if (!session) return false;

  const idGroups = session?.tokens?.idToken?.payload?.['cognito:groups'] ?? [];
  const accessGroups = session?.tokens?.accessToken?.payload?.['cognito:groups'] ?? [];

  // preferir idToken groups si existen, si no tomar accessToken
  const groups = Array.isArray(idGroups) && idGroups.length ? idGroups
               : Array.isArray(accessGroups) && accessGroups.length ? accessGroups
               : [];

  if (!Array.isArray(groups)) return false;

  const norm = groups.map(g => String(g || '').toLowerCase().trim());

  // lista de alias aceptados para rol admin (añade variantes si es necesario)
  const adminAliases = new Set(['admin', 'administrador', 'administradores']);

  return norm.some(g => adminAliases.has(g));
}

// src/utils/authSafe.js
import { fetchAuthSession } from "aws-amplify/auth";

export async function getSessionOrNull() {
  try {
    return await fetchAuthSession({ forceRefresh: false });
  } catch {
    return null;
  }
}

