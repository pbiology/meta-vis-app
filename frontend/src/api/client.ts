import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { userManager } from "../oidc";

const client: AxiosInstance = axios.create({
  baseURL: "/api/v1",
});

client.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const user = await userManager.getUser();
  if (user?.access_token && !user.expired) {
    config.headers.set("Authorization", `Bearer ${user.access_token}`);
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token rejected by API — try a silent refresh; if that fails, send
      // the user back through Keycloak.
      try {
        const refreshed = await userManager.signinSilent();
        if (refreshed && !refreshed.expired) {
          return Promise.reject(error);
        }
      } catch {
        /* fall through */
      }
      await userManager.signinRedirect();
    }
    return Promise.reject(error);
  }
);

export default client;
