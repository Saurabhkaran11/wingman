/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export: `npm run build` emits plain HTML/JS that FastAPI serves itself,
  // so an end user never needs Node to RUN Wingman — only to change the frontend.
  output: "export",
  distDir: ".next",
  // FastAPI serves the export from src/wingman/web/static via StaticFiles(html=True),
  // which resolves /path -> /path/index.html. trailingSlash keeps those paths aligned.
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
};
export default nextConfig;
