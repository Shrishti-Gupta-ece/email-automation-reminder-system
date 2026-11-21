/** Proxy /api/* to the FastAPI server so the browser never has CORS problems. */
module.exports = {
  async rewrites() {
    return [{ source: '/api/:path*', destination: 'http://127.0.0.1:8000/:path*' }]
  },
}
