// src/utils/authSafe.js
import { Auth } from 'aws-amplify';

export async function getCurrentUserOrNull() {
  try {
    return await Auth.currentAuthenticatedUser();
  } catch {
    return null;
  }
}
