export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export function createApi(token = null, onUnauthorized = () => {}) {
  return async function api(path, options = {}) {
    const {responseType,...requestOptions}=options;
    let response;
    try {
      response = await fetch(path, {
        ...requestOptions,
        headers: {...(token ? {Authorization: `Bearer ${token}`} : {}), ...options.headers},
        cache: 'no-store',
      });
    } catch (error) {
      if (error.name === 'AbortError') throw error;
      throw new ApiError('Unable to connect. Check that the server is running and try again.', 0);
    }
    if(response.ok&&responseType==='blob')return response.blob();
    const data = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 && token) onUnauthorized();
      let message = typeof data?.detail === 'string' ? data.detail : 'Please check your entries and try again.';
      if (Array.isArray(data?.detail)) message = data.detail.map(e => `${e.loc.at(-1)}: ${e.msg}`).join('. ');
      if (response.status >= 500 && !(response.status===503&&typeof data?.detail==='string') && !String(data?.detail||'').startsWith('Slack delivery was not confirmed.')) message = 'Your workspace could not be reached. Please try again.';
      throw new ApiError(message, response.status);
    }
    return data;
  };
}

export function jsonOptions(data, method = 'POST') {
  return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)};
}
