// Dev-server proxy: the app calls same-origin `/api/*` and ng serve forwards to
// the backend. This avoids CORS entirely and pins the backend to an explicit
// IPv4 address (some machines have another service on IPv6 localhost:8000).
// Override the target in containers via API_PROXY_TARGET (e.g. http://backend:8000).
const target = process.env['API_PROXY_TARGET'] || 'http://127.0.0.1:8000';

module.exports = {
  '/api': {
    target,
    secure: false,
    changeOrigin: true,
    logLevel: 'warn',
  },
};
