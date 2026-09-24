// src/utils/ensureOnboardingOnce.js
import { fetchAuthSession } from "aws-amplify/auth";
import { post } from "aws-amplify/api";

export async function ensureOnboardingOnce() {
  const session = await fetchAuthSession();
  const idToken = session.tokens?.idToken;
  if (!idToken) return;

  const sub = idToken.payload?.sub ?? "";
  const groups = idToken.payload?.["cognito:groups"] ?? [];

  const onceKey = `onboardingDone:${sub}`;
  if (sessionStorage.getItem(onceKey) === "1") return;

  // Si ya pertenece al grupo, no llamamos backend
  if (groups.includes("Participante")) {
    sessionStorage.setItem(onceKey, "1");
    return;
  }

  // 👉 Llamada al REST API Gateway protegido por Cognito
  await post({
    apiName: "AdminPlatformAPI", // 👈 TU API REAL
    path: "/onboarding/me",
    options: {
      headers: {
        Authorization: `Bearer ${idToken.toString()}`
      },
      body: {}
    }
  }).response;

  // 🔁 Forzar refresh para traer cognito:groups al token
  await fetchAuthSession({ forceRefresh: true });

  sessionStorage.setItem(onceKey, "1");
}
