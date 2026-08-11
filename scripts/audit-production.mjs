import { spawnSync } from "node:child_process";

const pnpmExecutable = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const result = spawnSync(pnpmExecutable, ["audit", "--prod", "--json"], {
  encoding: "utf8",
  shell: false,
});

if (result.error) {
  console.error(`Unable to run pnpm audit: ${result.error.message}`);
  process.exit(2);
}

let report;
try {
  report = JSON.parse(result.stdout);
} catch {
  console.error("pnpm audit did not return valid JSON.");
  console.error(result.stderr || result.stdout);
  process.exit(2);
}

const severities = new Set(["high", "critical"]);
const advisories = Object.values(report.advisories ?? {});
const productionFindings = [];

for (const advisory of advisories) {
  if (!severities.has(advisory.severity)) continue;

  const paths = (advisory.findings ?? []).flatMap((finding) => finding.paths ?? []);
  const webPaths = paths.filter((dependencyPath) =>
    dependencyPath.split(">")[0].startsWith("apps__web"),
  );

  if (webPaths.length > 0) {
    productionFindings.push({
      id: advisory.github_advisory_id ?? advisory.id,
      module: advisory.module_name,
      severity: advisory.severity,
      title: advisory.title,
      paths: webPaths,
      url: advisory.url,
    });
  }
}

if (productionFindings.length > 0) {
  console.error(JSON.stringify({ productionFindings }, null, 2));
  console.error(
    `${productionFindings.length} high/critical advisory record(s) affect the deployed web graph.`,
  );
  process.exit(1);
}

console.log("No high or critical advisories affect the deployed web dependency graph.");
console.log(
  `${advisories.length} total monorepo advisory record(s) were evaluated with path reachability.`,
);
