// src/amplify.js
import { Amplify } from 'aws-amplify';

/**
 * Usa TUS variables actuales:
 * - VITE_COGNITO_DOMAIN (puede traer https://, se normaliza)
 * - VITE_COGNITO_CLIENT_ID
 * - (opcional pero recomendado) VITE_COGNITO_USER_POOL_ID o VITE_USER_POOL_ID
 * - (opcional) VITE_AWS_REGION; si falta, se deriva del dominio
 * - VITE_REDIRECT_URI y/o VITE_REDIRECT_URI_TESTING
 */
const domainRaw = import.meta.env.VITE_COGNITO_DOMAIN || '';
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID || '';
const userPoolId =
  import.meta.env.VITE_COGNITO_USER_POOL_ID ||
  import.meta.env.VITE_USER_POOL_ID ||
  '';

const identityPoolId = import.meta.env.VITE_IDENTITY_POOL_ID || '';

const derivedRegion = (() => {
  const m = String(domainRaw).match(/auth\.([a-z0-9-]+)\.amazoncognito\.com/i);
  return m ? m[1] : undefined;
})();
const region = import.meta.env.VITE_AWS_REGION || derivedRegion || 'us-east-1';

const redirectSignIn =
  (location.hostname.includes('test') && import.meta.env.VITE_REDIRECT_URI_TESTING) ||
  import.meta.env.VITE_REDIRECT_URI ||
  `${window.location.origin}/`;

const redirectSignOut = redirectSignIn;
const domain = String(domainRaw).replace(/^https?:\/\//, '');

const missing = [];
if (!domain) missing.push('VITE_COGNITO_DOMAIN');
if (!clientId) missing.push('VITE_COGNITO_CLIENT_ID');
if (!userPoolId) {
  // No rompemos, pero avisamos. Con fallback manual igual funcionará el login.
  console.warn('[Amplify] Falta VITE_COGNITO_USER_POOL_ID (recomendado para manejar el retorno OAuth)');
}

if (missing.length) {
  console.error('[Amplify] Faltan variables VITE_ requeridas:', missing);
} else {
  Amplify.configure({
    Auth: {
      region,
      userPoolId,
      userPoolWebClientId: clientId,
      identityPoolId,
      oauth: {
        domain,
        scope: ['openid', 'email', 'profile', 'aws.cognito.signin.user.admin'],
        redirectSignIn,
        redirectSignOut,
        responseType: 'code',
      },
    },
    API: {
      endpoints: [
        {
          name: "CourseGeneratorAPI",
          endpoint: import.meta.env.VITE_COURSE_GENERATOR_API_URL || "https://z7z5albge3.execute-api.us-east-1.amazonaws.com/Prod",
          region: region
        }
      ]
    }
  });
}

export function hostedUiAuthorizeUrl() {
  if (!domain || !clientId) return null;
  const redirect = encodeURIComponent(redirectSignIn);
  const scope = encodeURIComponent('openid email profile');
  return `https://${domain}/oauth2/authorize?client_id=${clientId}&response_type=code&redirect_uri=${redirect}&scope=${scope}`;
}

export default Amplify;

