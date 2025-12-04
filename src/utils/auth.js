export function isAdmin(session) {
  if (!session) return false;

  const groups =
    session?.tokens?.idToken?.payload?.["cognito:groups"] ??
    session?.tokens?.accessToken?.payload?.["cognito:groups"] ??
    [];

  if (!Array.isArray(groups)) return false;

  const norm = new Set(groups.map((g) => String(g || "").toLowerCase().trim()));

  return norm.has("admin") || norm.has("administrador");
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

