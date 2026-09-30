import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Veröffentlichungspaket des ETL (JSON, Exporte, Archiv) im Entwicklungsserver bereitstellen.
// In Produktion liefert nginx diese Pfade aus (deploy/nginx).
const BUILD = resolve(__dirname, "../build");
const MOUNTS: Record<string, string> = {
  "/data/": join(BUILD, "veroeffentlichung/data"),
  "/exporte/": join(BUILD, "veroeffentlichung/exporte"),
  "/archiv/": join(BUILD, "archiv"),
};
const TYPES: Record<string, string> = {
  ".json": "application/json", ".pdf": "application/pdf", ".csv": "text/csv; charset=utf-8",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

function veroeffentlichung(): Plugin {
  return {
    name: "mh-veroeffentlichung",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? "").split("?")[0];
        const prefix = Object.keys(MOUNTS).find((p) => url.startsWith(p));
        if (!prefix) return next();
        const root = MOUNTS[prefix];
        const file = normalize(join(root, decodeURIComponent(url.slice(prefix.length))));
        if (!file.startsWith(root) || !existsSync(file) || !statSync(file).isFile()) {
          res.statusCode = 404;
          return res.end();
        }
        res.setHeader("Content-Type", TYPES[extname(file)] ?? "application/octet-stream");
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const intern = mode === "intern";
  return {
    plugins: [react(), veroeffentlichung()],
    define: { __INTERN__: JSON.stringify(intern) },
    build: {
      outDir: intern ? "dist/intern" : "dist/public",
      emptyOutDir: true,
      sourcemap: false,
      assetsInlineLimit: 0, // keine data:-URIs für Assets (strikte CSP)
    },
    server: {
      proxy: { "/api/intern": "http://localhost:8000" },
    },
    test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
  };
});
