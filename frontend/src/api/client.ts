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
          throw error;
        }
      } catch (refreshErr) {
        // Silent refresh failed — fall through to redirect. Re-throw if the
        // refresh succeeded but the caller still needs to see the 401.
        if (refreshErr === error) throw error;
      }
      await userManager.signinRedirect();
    }
    throw error;
  }
);

export default client;
