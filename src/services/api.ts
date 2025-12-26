import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

// Log API URL configuration for debugging
console.log('[API Config] VITE_API_URL from env:', import.meta.env.VITE_API_URL);
console.log('[API Config] Final API_URL:', API_URL);
console.log('[API Config] Full baseURL:', `${API_URL}/api`);

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Log the full request URL
  const fullUrl = config.baseURL ? `${config.baseURL}${config.url || ''}` : config.url;
  console.log(`[API Request] ${config.method?.toUpperCase()} ${fullUrl}`);
  return config;
});

// Add response interceptor to log protocol (HTTP/HTTPS)
api.interceptors.response.use(
  (response) => {
    // Extract protocol from request URL
    const requestUrl = response.config.url || '';
    const baseURL = response.config.baseURL || '';
    const fullUrl = baseURL ? `${baseURL}${requestUrl}` : requestUrl;
    const protocol = fullUrl.startsWith('https://') ? 'HTTPS' : 'HTTP';
    const protocolPrefix = fullUrl.split('://')[0] || 'http';
    
    console.log(`[API Response] Protocol: ${protocol} (${protocolPrefix}://)`);
    console.log(`[API Response] ${response.config.method?.toUpperCase()} ${fullUrl} - Status: ${response.status}`);
    
    return response;
  },
  (error) => {
    // Log error responses with protocol info
    if (error.config) {
      const requestUrl = error.config.url || '';
      const baseURL = error.config.baseURL || '';
      const fullUrl = baseURL ? `${baseURL}${requestUrl}` : requestUrl;
      const protocol = fullUrl.startsWith('https://') ? 'HTTPS' : 'HTTP';
      const protocolPrefix = fullUrl.split('://')[0] || 'http';
      
      console.error(`[API Error] Protocol: ${protocol} (${protocolPrefix}://)`);
      console.error(`[API Error] ${error.config.method?.toUpperCase()} ${fullUrl} - Status: ${error.response?.status || 'N/A'}`);
    }
    return Promise.reject(error);
  }
);

export default api;

