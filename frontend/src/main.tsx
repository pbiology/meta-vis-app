import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider as OidcAuthProvider } from "react-oidc-context";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { ConfigProvider } from "./context/ConfigContext";
import queryClient from "./queryClient";
import { oidcConfig } from "./oidc";
import "./index.css";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Root element #root not found");

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <OidcAuthProvider {...oidcConfig}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ConfigProvider>
            <AuthProvider>
              <App />
            </AuthProvider>
          </ConfigProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </OidcAuthProvider>
  </React.StrictMode>
);
