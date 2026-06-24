#!/bin/sh
# Injects runtime env vars into the SPA before nginx starts.
# Variables written here override anything baked in at build time.
cat > /usr/share/nginx/html/config.js <<EOF
window.__ENV__ = {
  VITE_OIDC_AUTHORITY: "${VITE_OIDC_AUTHORITY:-}",
  VITE_OIDC_CLIENT_ID: "${VITE_OIDC_CLIENT_ID:-}",
  VITE_OIDC_REDIRECT_URI: "${VITE_OIDC_REDIRECT_URI:-}",
  VITE_OIDC_POST_LOGOUT_REDIRECT_URI: "${VITE_OIDC_POST_LOGOUT_REDIRECT_URI:-}",
};
EOF
