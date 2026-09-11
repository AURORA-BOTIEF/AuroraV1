// src/aws-exports.js
const awsExports = {
  Auth: {
    region: 'us-east-1',
    userPoolId: 'us-east-1_B7QVYyDGp',
    userPoolWebClientId: '67qhvmopav8qp6blthh7vmql82',   // <- NUEVO
    mandatorySignIn: true,
    authenticationFlowType: 'USER_SRP_AUTH',
    storage: window.localStorage,

    oauth: {
      // Amplify espera el dominio SIN protocolo
      domain: import.meta.env.VITE_COGNITO_DOMAIN.replace(/^https?:\/\//, ''),

      // 🔐 Fuerza el clientId correcto
      clientId: '67qhvmopav8qp6blthh7vmql82',

      scope: ['email', 'openid', 'phone', 'profile'],

      // URLs EXACTAS registradas en Cognito
      redirectSignIn: import.meta.env.VITE_REDIRECT_URI,       // p. ej. https://testing.d28h59guct50tx.amplifyapp.com
      redirectSignOut: import.meta.env.VITE_REDIRECT_URI,      // igual a la de arriba

      // Idealmente solo 'code' (PKCE). Si hoy necesitas implícita, mantenla
      responseType: 'code',
    },
  },
};

export default awsExports;
