// src/amplifySafe.js
import { Amplify } from 'aws-amplify';

function hasAuthEnv() {
  return Boolean(
    import.meta?.env?.VITE_AWS_REGION &&
    import.meta?.env?.VITE_COGNITO_USER_POOL_ID &&
    import.meta?.env?.VITE_COGNITO_APP_CLIENT_ID
  );
}

/**
 * Llama esto una sola vez (por ejemplo en main.jsx/App.jsx).
 * Si no hay variables de Auth, no configura nada y no rompe.
 */
export function configureAmplifySafely() {
  try {
    if (!hasAuthEnv()) return false;

    Amplify.configure({
      Auth: {
        region: import.meta.env.VITE_AWS_REGION,
        userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
        userPoolWebClientId: import.meta.env.VITE_COGNITO_APP_CLIENT_ID,
        mandatorySignIn: false,
      },
    });

    return true;
  } catch {
    return false;
  }
}
