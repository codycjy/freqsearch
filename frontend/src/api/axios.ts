import axios from 'axios';

// 使用相对路径，自动适配当前域名和端口
const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const axiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);
