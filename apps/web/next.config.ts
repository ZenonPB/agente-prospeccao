import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Deploy em container (item 3.4 da auditoria): build de produção standalone
  // com server.js mínimo — não depende de node_modules no runtime.
  output: "standalone",
  reactStrictMode: true,
  turbopack: { root: __dirname },
};

export default nextConfig;
