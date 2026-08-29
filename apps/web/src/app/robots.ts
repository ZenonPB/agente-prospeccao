import type { MetadataRoute } from "next";

const PUBLIC_PATHS = ["/login", "/register", "/esqueci-senha", "/resetar-senha", "/aceitar-convite"];

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://prospect.ai";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: PUBLIC_PATHS,
        disallow: ["/"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
