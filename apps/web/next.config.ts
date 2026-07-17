import type { NextConfig } from "next";

const repositoryName = process.env.GITHUB_REPOSITORY?.split("/")[1];
const githubPagesBasePath =
  process.env.GITHUB_ACTIONS === "true" && repositoryName
    ? `/${repositoryName}`
    : "";

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  basePath: githubPagesBasePath,
  assetPrefix: githubPagesBasePath,
  trailingSlash: true,
};

export default nextConfig;
