---
name: saferoute-release-check
description: Validate SafeRoute AI before a pull request, GitHub Pages deployment, exhibition, or assignment submission. Use for release readiness, static-export verification, route-geometry checks, test execution, deployment evidence, or diagnosing whether the showcase is safe to publish.
---

# SafeRoute release check

Run a bounded, evidence-based release gate. Do not publish when a required check fails.

## Workflow

1. Confirm `git status -sb` and identify the intended change scope.
2. Run `scripts/check-release.ps1` from the repository root.
3. Verify `apps/web/out/index.html` references the repository base path when testing Pages.
4. Check that demo routes contain detailed road geometry and share the intended endpoints.
5. Review disclaimers: never describe a score as a guarantee of safety.
6. Confirm offline demo recovery, location-denial recovery, keyboard navigation, and a 390px viewport.
7. Publish through a focused branch and pull request; require passing web and API checks.
8. Verify the deployed URL returns HTTP 200 and contains the expected title and demo-status copy.

## Evidence

Report exact commands, pass/fail results, commit SHA, PR URL, workflow URL, deployment URL, and known warnings. Do not convert an unrun check into a pass.

## Stop conditions

Stop publication for failing tests, broken repository asset paths, missing safety disclaimer, page-level mobile overflow, straight-line fallback routes, or an unreviewed mixed worktree.
