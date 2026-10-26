/**
 * HaemoPulse API & Network Configuration
 *
 * Dynamically resolves API and ML endpoints:
 * 1. In production (Cloudflare Workers/Pages, Vercel, or any HTTPS host), ensures
 *    requests target the active production backend (https://haemopulse-backend.onrender.com).
 * 2. In local development (localhost / 127.0.0.1), targets the local backend (port 8080 / 8000).
 * 3. Prevents mixed-content security blocks and local IP leaks on public HTTPS deployments.
 */

export const PRODUCTION_BACKEND_URL = 'https://haemopulse-backend.onrender.com';

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
  const currentHost = typeof window !== 'undefined' && window.location ? window.location.hostname : '';
  const currentProtocol = typeof window !== 'undefined' && window.location ? window.location.protocol : '';
  const isLocal = isLocalHostname(currentHost);

  const configuredUrl = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '').trim();

  // If running in production (public HTTPS domain e.g. workers.dev, pages.dev, vercel.app)
  if (!isLocal || currentProtocol === 'https:') {
    if (configuredUrl && configuredUrl.startsWith('https://')) {
      return configuredUrl.replace(/\/$/, '');
    }
    return PRODUCTION_BACKEND_URL;
  }

  // Local development mode
  if (configuredUrl) {
    return configuredUrl.replace(/\/$/, '');
  }

  if (currentHost && currentHost !== 'localhost' && currentHost !== '127.0.0.1') {
    return `http://${currentHost}:8080`;
  }
  return 'http://127.0.0.1:8080';
};

export const getMlServiceUrl = () => {
  const mlConfigured = (import.meta.env.VITE_ML_SERVICE_URL || import.meta.env.VITE_ML_API_BASE_URL || '').trim();
  const currentHost = typeof window !== 'undefined' && window.location ? window.location.hostname : '';
  const currentProtocol = typeof window !== 'undefined' && window.location ? window.location.protocol : '';
  const isLocal = isLocalHostname(currentHost);

  if (!isLocal || currentProtocol === 'https:') {
    if (mlConfigured && mlConfigured.startsWith('https://')) {
      return mlConfigured.replace(/\/$/, '');
    }
    return getApiBaseUrl();
  }

  if (mlConfigured) {
    return mlConfigured.replace(/\/$/, '');
  }
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
  PRODUCTION_BACKEND_URL,
};
