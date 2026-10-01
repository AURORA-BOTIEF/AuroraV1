// src/utils/apiConfig.js
// Centralized API configuration to prevent legacy/misconfigured Amplify env vars from breaking API requests.

const RAW_API_URL = import.meta.env.VITE_COURSE_GENERATOR_API_URL;

export const DEFAULT_COURSE_GENERATOR_API_URL = 'https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod';

export const COURSE_GENERATOR_API_URL = (
    RAW_API_URL &&
    !RAW_API_URL.includes('h6ysn7u0') &&
    !RAW_API_URL.includes('z7z5albge3')
) ? RAW_API_URL : DEFAULT_COURSE_GENERATOR_API_URL;

export const API_BASE = COURSE_GENERATOR_API_URL;

export default API_BASE;
