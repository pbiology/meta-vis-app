import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

const CSRF_COOKIE_NAME = "csrf_token";
const CSRF_HEADER_NAME = "X-CSRF-Token";

function readCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp("(?:^|; )" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "=([^;]*)")
  );
  return match ? decodeURIComponent(match[1]) : null;
}

const client: AxiosInstance = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
});

client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = readCookie(CSRF_COOKIE_NAME);
  if (token) {
    config.headers.set(CSRF_HEADER_NAME, token);
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("username");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default client;
