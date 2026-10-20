import { useCallback, useEffect, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

/**
 * Load the same district/taluk catalog used by backend validation.
 * The API marks the catalog as non-authoritative so it isn't mistaken for an
 * official administrative boundary source.
 */
export default function useLocationOptions() {
  const [districts, setDistricts] = useState([]);
  const [taluksByDistrict, setTaluksByDistrict] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [source, setSource] = useState('');
  const [authoritative, setAuthoritative] = useState(false);

  const refresh = useCallback(async (signal) => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/locations`, { signal });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Could not load district and taluk options.');
      }
      setDistricts(Array.isArray(data.districts) ? data.districts : []);
      setNotice(typeof data.notice === 'string' ? data.notice : '');
      setSource(typeof data.source === 'string' ? data.source : '');
      setAuthoritative(data.authoritative === true);
      setTaluksByDistrict(data.taluks_by_district && typeof data.taluks_by_district === 'object'
        ? data.taluks_by_district
        : {});
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Could not load location options.');
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  return { districts, taluksByDistrict, loading, error, notice, source, authoritative, refresh };
}
