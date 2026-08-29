import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://prospect.ai";

const PUBLIC_PATHS = [
  { path: "/login", priority: 0.9, changeFrequency: "monthly" as const },
  { path: "/register", priority: 0.9, changeFrequency: "monthly" as const },
  { path: "/esqueci-senha", priority: 0.4, changeFrequency: "yearly" as const },
  { path: "/resetar-senha", priority: 0.3, changeFrequency: "yearly" as const },
  { path: "/aceitar-convite", priority: 0.4, changeFrequency: "yearly" as const },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return PUBLIC_PATHS.map(({ path, priority, changeFrequency }) => ({
    url: `${SITE_URL}${path}`,
    lastModified: now,
    changeFrequency,
    priority,
  }));
}
