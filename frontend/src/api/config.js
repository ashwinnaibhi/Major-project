/**
 * HaemoPulse API & Network Configuration
 *
 * Dynamically resolves API and ML endpoints:
 * 1. Checks explicit environment variables (VITE_API_BASE_URL, VITE_API_URL).
 * 2. In production (Cloudflare Pages), enforces explicit HTTPS backend configuration.
 * 3. In local development (localhost / 127.0.0.1), uses http://localhost:8000.
 * 4. When accessed from mobile or other LAN devices (e.g. 192.168.1.x), dynamically
 *    uses http://<current-host>:8000 for development.
 */

export const isLocalHostname = (host) => {
  if (!host) return false;
  return (
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '::1' ||
    host.endsWith('.local') ||
    host.startsWith('192.168.') ||
    host.startsWith('10.') ||
    /^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(host)
  );
};

export const getApiBaseUrl = () => {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL;
  if (configuredUrl && configuredUrl.trim()) {
    return configuredUrl.trim().replace(/\/$/, '');
  }

  // Detect whether we are running in local development
  const isDevMode = Boolean(import.meta.env.DEV);
  const currentHost = typeof window !== 'undefined' && window.location ? window.location.hostname : '';
  const isLocal = !currentHost || isLocalHostname(currentHost);

  if (isDevMode || isLocal) {
    if (currentHost && currentHost !== 'localhost' && currentHost !== '127.0.0.1') {
      return `http://${currentHost}:8000`;
    }
    return 'http://localhost:8000';
  }

  // Production safety guard: Do not silently construct an invalid HTTP url (e.g. http://haemopulse.pages.dev:8000)
  console.error(
    '[HaemoPulse Configuration Error] VITE_API_BASE_URL is not configured in production. ' +
    'Please set VITE_API_BASE_URL in your Cloudflare Pages / hosting dashboard (e.g. https://haemopulse-api.onrender.com).'
  );
  return '';
};

export const getMlServiceUrl = () => {
  const mlConfigured = import.meta.env.VITE_ML_SERVICE_URL || import.meta.env.VITE_ML_API_BASE_URL;
  if (mlConfigured && mlConfigured.trim()) {
    return mlConfigured.trim().replace(/\/$/, '');
  }
  // Unified backend hosts /predict-availability and /metrics directly
  return getApiBaseUrl();
};

export const API_BASE_URL = getApiBaseUrl();
export const ML_SERVICE_URL = getMlServiceUrl();

export default {
  isLocalHostname,
  getApiBaseUrl,
  getMlServiceUrl,
  API_BASE_URL,
  ML_SERVICE_URL,
};
