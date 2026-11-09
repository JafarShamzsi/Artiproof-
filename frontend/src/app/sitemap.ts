import type { MetadataRoute } from "next";

/**
 * Sitemap for crawler discovery of the marketing surface. Authenticated
 * routes are intentionally absent — they live behind /login and aren't
 * useful for search indexing. Update `lastModified` on each route when
 * its content meaningfully changes; SEO ranking decays without it.
 *
 * The host is read from NEXT_PUBLIC_SITE_URL so the build can target
 * preview / staging / production without hardcoding artiproof.com.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const host = process.env.NEXT_PUBLIC_SITE_URL ?? "https://artiproof.com";
  const now = new Date();

  const routes: Array<{
    path: string;
    changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
    priority: number;
  }> = [
    { path: "/", changeFrequency: "weekly", priority: 1.0 },
    { path: "/pricing", changeFrequency: "monthly", priority: 0.9 },
    { path: "/demo", changeFrequency: "monthly", priority: 0.9 },
    { path: "/methodology", changeFrequency: "monthly", priority: 0.8 },
    { path: "/about", changeFrequency: "monthly", priority: 0.6 },
    { path: "/changelog", changeFrequency: "weekly", priority: 0.6 },
    { path: "/privacy", changeFrequency: "yearly", priority: 0.3 },
    { path: "/terms", changeFrequency: "yearly", priority: 0.3 },
    { path: "/security", changeFrequency: "yearly", priority: 0.3 },
  ];

  return routes.map(({ path, changeFrequency, priority }) => ({
    url: `${host}${path}`,
    lastModified: now,
    changeFrequency,
    priority,
  }));
}
