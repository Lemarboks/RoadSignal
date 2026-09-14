# Monitoring and evidence verification

## Available in this showcase

Open **Fleet → Fleet replay**, or **Dashboard → Open fleet replay**.

- Four synthetic trackers: two moving, one parked, one offline with a retained last position.
- Select a map marker or a device in the list to inspect sample speed, coordinates, GPS accuracy, battery and packet age.
- Play/pause, reset, 1×/4× playback and fit-network controls. The three-minute replay stops at the end; it does not teleport vehicles back to the start.
- Three synthetic street stations with air/road temperature, rain rate, visibility, vehicle flow and mean traffic speed. One station deliberately stays stale.
- All samples carry `source: demo`. These values do not enter real incident storage, duplicate verification, the weather feed or safety scoring.
- Playback pauses while the panel is offscreen or the document is hidden. Reduced-motion preferences disable autoplay and positional interpolation; users can explicitly play the discrete updates.
- Existing MapLibre street maps and the interactive schematic fallback both support device selection. Public street tiles are not live traffic observations.

The default mode is a lightweight browser replay. Positions use illustrative bundled Cape Town corridors, not each driver's assigned journey or physically integrated sample speeds. Replay state resets when the Fleet page is remounted; its packet ages describe replay time. The optional **Connected demo** mode uses the new Traccar/ThingsBoard bridge and real service timestamps, while retaining synthetic-data labels. See [monitoring installation and n8n setup](monitoring-setup.md). No physical sensors, camera streams or external news feeds are connected by default.

## Open-source candidates for real monitoring

The following components now have local Docker integrations and explicit validation boundaries; see [installation and runtime modes](monitoring-setup.md). They are **not validated production models or sources of real observations**. Software/weight licenses and input-data rights need separate review for a deployment.

| Task | Candidate | What it contributes | What it cannot establish |
| --- | --- | --- | --- |
| Compare a reported claim with retrieved text | [DeBERTa-v3-base-mnli-fever-anli](https://huggingface.co/MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli), model card lists MIT | English premise/claim entailment, contradiction and neutral classifications | Whether the premise itself is true, current, independent or about the correct place |
| Find related reports | Existing Qwen embeddings + reranker | Retrieve semantically similar incident reports | Similarity is not corroboration; ten copied articles are still one source |
| Detect and track vehicles in authorized video | [RT-DETR](https://github.com/lyuwenyu/RT-DETR) + [ByteTrack](https://github.com/FoundationVision/ByteTrack) | Object detections and associated tracks; inputs for calibrated line-crossing counts and queue analysis | Automatic proof of a collision, identity or intent; reliable road speed without camera/scene calibration |
| Receive real vehicle positions | [Traccar](https://github.com/traccar/traccar) | Open-source tracking server and device protocol support | A source of GPS positions without connected devices or simulator clients |
| Ingest street sensor telemetry | [ThingsBoard Community Edition](https://github.com/thingsboard/thingsboard) | Device management, telemetry collection and visualization | Measurements without calibrated hardware or a licensed sensor-data provider |

For object detection, evaluate the exact checkpoint on local day/night/rain footage and check class coverage. Tracking also needs occlusion testing, camera geometry, timestamp quality and rules for dropped frames. Avoid identifying faces or number plates when anonymous traffic counts will do. For text, the proposed NLI model is English; other supported languages require separately evaluated candidates. No benchmark in an upstream model card validates South African incident verification by itself.

## A defensible verification workflow

1. Ingest only approved feeds or user-provided evidence. Store canonical source URL, publisher, source timestamp, ingestion timestamp, claimed event time/location and reuse rights.
2. Check freshness and location. Keep publication time separate from the time the incident happened. Archive old reports instead of treating them as current road conditions.
3. Group duplicate and syndicated material with the existing Qwen retrieval. Count independent originating sources, not raw article count.
4. Use an NLI model to propose support/contradiction/insufficient-evidence labels against the retrieved passages. Preserve those passages and source links for review. Do not turn model confidence into a truth percentage.
5. Correlate authorized, sufficiently fresh camera/sensor/operator evidence where available. Missing telemetry is unknown, not proof that a road is safe.
6. Have an authorized operator approve any verified status. Preserve conflicting evidence, provenance and an audit trail. A sensor threshold or model output must not dispatch emergency services or automatically publish a verified incident.

The n8n evidence webhook implements supplied-text comparison and an authenticated operator inbox. It does not fetch external feeds or implement automatic verified-incident publication. Existing incident assistance still drafts categories and finds possible duplicates. Adding real feeds requires source access, a retention/consent plan and validation—not just another model download.

## What real street-level readings need

Air temperature, road-surface temperature, rain, visibility and vehicle counts are different measurements. A deployed station needs the relevant instruments, known coordinates, calibration metadata, units, timestamps, authenticated transport and stale/quality flags. A model cannot manufacture missing observations. Keep Open-Meteo corridor estimates, physical station measurements and demo samples in separate source-labelled channels.

## Verification commands

```sh
cd apps/web
node node_modules/vitest/vitest.mjs run lib/demo-telemetry.test.ts
# With the updated Docker showcase running (PowerShell):
$env:PLAYWRIGHT_EXTERNAL_SERVER='1'
node node_modules/@playwright/test/cli.js test e2e/monitoring.spec.ts --workers=2
```

Tests exercise distance-based interpolation, deterministic replay, frozen stale data, playback controls, offline and reduced-motion behavior, keyboard selection, mobile overflow and automated accessibility checks. These are software checks, not sensor/model accuracy claims.
