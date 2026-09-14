type DeploymentInput = { githubPages?: boolean; apiUrl?: string; nodeEnv?: string };

/** A Pages artifact must never send credentials or device requests to localhost. */
export function resolveDeployment({ githubPages = false, apiUrl, nodeEnv }: DeploymentInput) {
  const configured = (apiUrl ?? (nodeEnv === "development" && !githubPages ? "http://localhost:8000" : "")).trim();
  let backendEnabled = Boolean(configured);
  if (githubPages && configured) {
    try {
      const url = new URL(configured);
      const host = url.hostname.toLowerCase();
      backendEnabled = url.protocol === "https:" && !url.username && !url.password && !url.search && !url.hash &&
        host !== "localhost" && !host.endsWith(".localhost") && host !== "[::1]" && !/^127\./.test(host);
    } catch { backendEnabled = false; }
  }
  return {
    githubPages,
    backendEnabled,
    demoOnly: githubPages && !backendEnabled,
    apiUrl: backendEnabled ? configured.replace(/\/+$/, "") : "",
  };
}

export const deployment = resolveDeployment({
  githubPages: process.env.NEXT_PUBLIC_GITHUB_PAGES === "true",
  apiUrl: process.env.NEXT_PUBLIC_API_URL,
  nodeEnv: process.env.NODE_ENV,
});
