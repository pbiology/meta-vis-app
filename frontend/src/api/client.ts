import axios, { AxiosError, AxiosInstance } from "axios";

const client: AxiosInstance = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
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
