// src/amplify.js
import { Amplify, Logger } from 'aws-amplify';

// solo INFO en dev, ERROR en prod
Logger.LOG_LEVEL = import.meta.env.DEV ? 'INFO' : 'ERROR';
/**
 * AWS Amplify v6 Configuration
 * Uses environment variables:
 * - VITE_COGNITO_DOMAIN (can include https://, will be normalized)
 * - VITE_COGNITO_CLIENT_ID
 * - VITE_COGNITO_USER_POOL_ID or VITE_USER_POOL_ID
 * - VITE_AWS_REGION (optional, derived from domain if missing)
 * - VITE_REDIRECT_URI and/or VITE_REDIRECT_URI_TESTING
 * - VITE_IDENTITY_POOL_ID (optional)
 * - VITE_HTTP_API_URL (for custom HTTP API Gateway)
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
  console.warn('[Amplify] Missing VITE_COGNITO_USER_POOL_ID (recommended for OAuth handling)');
}

if (missing.length) {
  if (import.meta.env.DEV) {
    console.error('[Amplify] Missing required VITE_ variables:', missing);
  }
} else {
  if (import.meta.env.DEV) {
    console.log('[Amplify] Configuring with:', {
      region,
      userPoolId: userPoolId ? '***' : '(missing)',
      identityPoolId: identityPoolId ? '***' : '(not set)',
      apiEndpoint: import.meta.env.VITE_COURSE_GENERATOR_API_URL ? '***' : '(default)',
      httpApi: import.meta.env.VITE_HTTP_API_URL ? '***' : '(not set)',
    });
  }

    // === ✅ AWS Amplify v6 configuration ===
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId: clientId,
        identityPoolId,
        storage: window.sessionStorage, // Forzar sessionStorage para evitar problemas entre pestañas
        loginWith: {
          oauth: {
            domain,
            scopes: ['openid', 'email', 'profile', 'aws.cognito.signin.user.admin'],
            redirectSignIn: [redirectSignIn],
            redirectSignOut: [redirectSignOut],
            responseType: 'code',
          }
        }
      }
    },
    API: {
      REST: {
        CourseGeneratorAPI: {
          endpoint: import.meta.env.VITE_COURSE_GENERATOR_API_URL || "https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod",
          region: region
        },
        // 👇 Nueva API registrada (HTTP API Gateway)
        SeminariosAPI: {
          endpoint: import.meta.env.VITE_HTTP_API_URL || "https://rvyg5dnnh4.execute-api.us-east-1.amazonaws.com/dev",
          region: region
        }
      }
    }
  }, {
    ssr: false
  });
}

export function hostedUiAuthorizeUrl() {
  if (!domain || !clientId) return null;
  const redirect = encodeURIComponent(redirectSignIn);
  const scope = encodeURIComponent('openid email profile');
  return `https://${domain}/oauth2/authorize?client_id=${clientId}&response_type=code&redirect_uri=${redirect}&scope=${scope}`;
}

export default Amplify;

