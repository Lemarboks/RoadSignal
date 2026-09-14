import type { NextConfig } from "next";

const repositoryName = process.env.GITHUB_REPOSITORY?.split("/")[1];
const githubPages = process.env.ROADSIGNAL_GITHUB_PAGES === "true";
const githubPagesBasePath = githubPages
  ? process.env.ROADSIGNAL_PAGES_BASE_PATH ?? (repositoryName && !repositoryName.endsWith(".github.io") ? `/${repositoryName}` : "")
  : "";

if (githubPages && process.env.NEXT_PUBLIC_API_URL?.trim()) {
  const apiUrl = new URL(process.env.NEXT_PUBLIC_API_URL.trim());
  if (apiUrl.protocol !== "https:" || apiUrl.username || apiUrl.password || apiUrl.search || apiUrl.hash ||
    apiUrl.hostname === "localhost" || apiUrl.hostname.endsWith(".localhost") || apiUrl.hostname === "[::1]" || /^127\./.test(apiUrl.hostname)) {
    throw new Error("GitHub Pages requires a public HTTPS NEXT_PUBLIC_API_URL without credentials, query or fragment. Leave it empty for the guest demo.");
  }
}

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  basePath: githubPagesBasePath,
  assetPrefix: githubPagesBasePath,
  trailingSlash: true,
  env: { NEXT_PUBLIC_GITHUB_PAGES: String(githubPages) },
};

export default nextConfig;
