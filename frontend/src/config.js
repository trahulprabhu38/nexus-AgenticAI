/**
 * Backend origin for Nexus (FastAPI + Table Agent).
 *
 * Dev default is 8012 so /table-agent/rank and table_agent registration match
 * the current codebase. Override with REACT_APP_API_URL if needed.
 */
export function getApiBase() {
  const v = process.env.REACT_APP_API_URL;
  if (typeof v === 'string' && v.trim() !== '') {
    return v.trim().replace(/\/$/, '');
  }
  if (process.env.NODE_ENV === 'development') {
    return 'http://127.0.0.1:8000';
  }
  return 'http://127.0.0.1:8000';
}
