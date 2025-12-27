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
  console.log(`[API Request] ${config.method?.toUpperCase()} ${fullUrl}`, config.data ? { data: config.data } : '');
  return config;
});

// Add response interceptor to log responses and errors
api.interceptors.response.use(
  (response) => {
    const fullUrl = response.config.baseURL ? `${response.config.baseURL}${response.config.url || ''}` : response.config.url;
    console.log(`[API Response] ${response.config.method?.toUpperCase()} ${fullUrl}`, {
      status: response.status,
      data: response.data,
    });
    return response;
  },
  (error) => {
    const fullUrl = error.config?.baseURL ? `${error.config.baseURL}${error.config?.url || ''}` : error.config?.url;
    console.error(`[API Error] ${error.config?.method?.toUpperCase()} ${fullUrl}`, {
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      message: error.message,
    });
    return Promise.reject(error);
  }
);

export default api;

