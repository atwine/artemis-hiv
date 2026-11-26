import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The browser tests build into their own folder (playwright.config.ts), so they can run beside `npm run dev`.
  distDir: process.env.ARTEMIS_WEB_DIST_DIR || ".next",
  // No dev badge over the footer; build errors still show.
  devIndicators: false,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
