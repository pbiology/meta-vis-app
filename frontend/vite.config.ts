import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command, mode }) => {
  // loadEnv merges process.env with frontend/.env, .env.<mode>, etc., the
  // same way Vite does for client code. Reading it here lets the dev server
  // fail loud when VITE_API_PROXY_TARGET is missing instead of silently
  // proxying to a non-existent localhost port.
  const env = loadEnv(mode, process.cwd(), '')
  const isDevServer = command === 'serve'
  const target = env.VITE_API_PROXY_TARGET

  if (isDevServer && !target) {
    throw new Error(
      'VITE_API_PROXY_TARGET must be set for the dev server. ' +
        'Copy frontend/.env.dev to frontend/.env, or rely on docker compose ' +
        'to set it via the `environment:` block.'
    )
  }

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      allowedHosts: true,
      proxy: isDevServer
        ? {
            '/api': {
              target,
              changeOrigin: true,
            },
          }
        : undefined,
    },
  }
})
