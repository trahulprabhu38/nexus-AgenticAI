/**
 * Backend origin for Nexus (FastAPI).
 *
 * In Docker production: REACT_APP_API_URL=/api (nginx proxies to backend:8000)
 * In local dev: defaults to http://127.0.0.1:8000
 */
export function getApiBase() {
  const v = process.env.REACT_APP_API_URL;
  if (typeof v === 'string' && v.trim() !== '') {
    return v.trim().replace(/\/$/, '');
  }
  if (process.env.NODE_ENV === 'development') {
    return 'http://127.0.0.1:8000';
  }
  return '/api';
}
