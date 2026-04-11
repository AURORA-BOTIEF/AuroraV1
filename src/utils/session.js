// src/utils/session.js
import { fetchAuthSession } from "aws-amplify/auth";

export async function getSessionOrNull(force = false) {
  try {
    return await fetchAuthSession({ forceRefresh: force });
  } catch {
    return null;
  }
}
