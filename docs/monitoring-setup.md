# Local monitoring, models and automation

This extends the existing showcase; it does not connect unapproved real feeds.
Use `compose.monitoring.yml` alongside `docker-compose.yml` and `compose.ai.yml`.
The Windows setup helper is `infrastructure/monitoring/setup.ps1`.

## What connects to what

```text
Synthetic GPS clients -> Traccar -> monitoring bridge -> RoadSignal map
Synthetic stations   -> ThingsBoard -> same bridge   -> RoadSignal map
                              RoadSignal stored device timestamps
                                           |
                               n8n scheduled freshness checks
                                           |
                                deduplicated in-app alerts

Authenticated evidence webhook -> DeBERTa text comparison -> operator inbox
Uploaded demo/authorized frames -> RT-DETR + ByteTrack -> per-frame vehicle counts
```

All seven simulated devices retain `source: demo`. The bridge reads positions and
sensor values **back from the actual upstream services**, rather than bypassing
them. Stopping an upstream stops fresh packets; old readings retain their original
timestamps. An offline vehicle and stale sensor are intentional test cases.
GPS corridors and speed samples are illustrative, not physics-calibrated journeys.

The operator inbox records approvals/rejections and their authors. An approval is
an **evidence-review decision only**: it does not verify truth, publish an incident,
alter route-risk scores or dispatch emergency services. NLI examines supplied text;
it does not fetch a source URL or establish source reliability/independence.

## Installation and memory modes

From the repository root in PowerShell:

```powershell
./infrastructure/monitoring/setup.ps1 -Mode monitoring
./infrastructure/monitoring/setup.ps1 -Mode models
```

The first command initializes persistent secrets, GPS devices, sensor devices,
local operator accounts, the API database migration and three published n8n
workflows. Subsequent runs preserve secrets and do not overwrite edited workflows.
Use `-ImportWorkflows` only when deliberately replacing these three supplied
workflows with the repository versions. No unrelated workflows are modified.

The model mode builds the shared CPU runtime first, then installs DeBERTa and
RT-DETR workers, so it also works on a fresh clone. Their exact checkpoints
are revision-pinned; see [worker details](../infrastructure/verification/README.md).
Wait for `/ready`/Docker health before running each worker's `/service/smoke.py`.
A successful smoke test proves execution, **not real-world detection accuracy**.

This laptop has 16 GB system RAM, about 8 GB allocated to Docker, and Intel
integrated graphics. Do not start every profile simultaneously. The setup helper
switches between monitoring/models and the existing Qwen retrieval/Whisper workers,
preserving model caches and data volumes:

```powershell
./infrastructure/monitoring/setup.ps1 -Mode retrieval
```

For local Western Cape routing:

```powershell
./infrastructure/monitoring/setup.ps1 -Mode routing
```

That mode pauses the heavier workers while Valhalla builds its regional graph.
The first build downloads the Western Cape OpenStreetMap extract; later starts
reuse the persisted tiles. The monitoring overlay selects Valhalla by default;
wait for its health check before showcasing local routing. Set
`MONITORING_ROUTE_PROVIDER=open` to retain public OSRM instead. It is a
road-routing graph, not a live traffic feed. While it warms up or outside its
coverage, the existing open-routing fallback applies.
Address lookup still uses the configured public geocoder.

For the offline training toolchain:

```powershell
./infrastructure/monitoring/setup.ps1 -Mode training
```

This installs XGBoost/scikit-learn and shows the trainer's CLI. Supply an approved
real dataset and reviewed manifest under ignored `training-data/` before training.
The validation, geographic/time holdout and calibration gates remain mandatory.
There is no honest substitute using synthetic telemetry. The GPU-only
`gpt-oss-20b` profile also remains disabled on this integrated-graphics machine.

## Local consoles and credentials

| Console | Local address |
| --- | --- |
| RoadSignal | http://localhost:3000 |
| n8n | http://localhost:5678 |
| Traccar | http://localhost:8082 |
| ThingsBoard CE | http://localhost:8080 |
| Jaeger, when tracing is running | http://localhost:16686 |

New consoles bind to `127.0.0.1`, not the LAN. n8n uses HTTP cookies only for this
localhost showcase. Use TLS, proper secrets, database backups and a security
review before any remote exposure. The existing base showcase ports are unchanged.

Random local passwords are stored in the named `integration_secrets` volume and
never printed during installation. To display them **locally for your own login**:

```powershell
docker compose -f docker-compose.yml -f compose.ai.yml -f compose.monitoring.yml --profile monitoring --profile sensors run --rm monitoring-init python /integration/bootstrap.py credentials
```

RoadSignal, n8n and Traccar use `operator@roadsignal.local` with separate passwords.
ThingsBoard uses `tenant@thingsboard.org` for sensor management. Installation
rotates all three built-in ThingsBoard demo passwords. The bridge uses local demo
administrator credentials; a real deployment needs scoped service accounts and a
device-permission/retention design. Do not reuse these credentials elsewhere.

In RoadSignal, sign in with the local operator account, open **Fleet replay**, and
select **Connected demo**. The map now reads the seven devices from the backend.
Below it, **Automation & review** shows freshness alerts, the evidence inbox and
**Traffic frame check**. The blank-frame button executes the actual CPU vision
model using a synthetic image; zero counts are expected. Optional authorized
uploads are restricted to operators and PNG/JPEG files up to 512 KiB and
2,073,600 pixels. No camera or real source is connected by default.

## n8n workflows

| Workflow | Trigger | Result |
| --- | --- | --- |
| `roadsignal-health` | Every minute or authenticated `POST /webhook/roadsignal-device-health` | Deduplicated stale-device/recovery alerts and current device summary |
| `roadsignal-daily-report` | 07:00 Africa/Johannesburg or Manual test in n8n | Latest 31 daily demo summaries, separately archived for operator viewing |
| `roadsignal-evidence` | Authenticated `POST /webhook/roadsignal-evidence` | Supplied-text model comparison, then a pending operator review |

Both webhooks require the generated `Authorization: Bearer ...` header. No secret
is embedded in the versioned JSON; n8n stores it as an encrypted credential.
The evidence body is `{event_id, source: "demo" | "submitted", claim,
evidence: [{text, source_url, observed_at?}]}`. Keep claims under 500 characters,
passages under 3000 characters and at most five passages for the NLI worker.
Model failure still queues the supplied evidence with its error, never a success
claim. Reusing an event ID cannot silently replace the original evidence.

No email/SMS destination, external RSS source, camera stream or device account
has been authorized. Connect approved sources to the intake only after reviewing
their licensing, retention, identity exposure and access rights. Nothing here
sends real emergency notifications or automatically reroutes a driver.

## Persistence and checks

MySQL migration `0004` stores an isolated, transaction-locked monitoring workspace.
Out-of-order packets cannot overwrite fresher ones. Device/run/alert storage has
documented caps; a full review inbox rejects new submissions instead of silently
discarding operator history. Compose named volumes retain n8n workflows, credentials,
GPS history, ThingsBoard telemetry, routing tiles and model caches across restarts.

```powershell
python -m pytest infrastructure/monitoring/test_bridge.py -q
cd apps/api
python -m pytest tests/test_monitoring.py -q
```

ThingsBoard uses its in-memory queue for this single-node PoC; this is not durable
production messaging. [Official ThingsBoard Docker guidance](https://thingsboard.io/docs/installation/docker/)
explains production resource and queue requirements. n8n is **source-available**,
not OSI-open-source; internal self-hosting is governed by its
[Sustainable Use License](https://github.com/n8n-io/n8n/blob/master/LICENSE.md).
Workflow import/publication follows the [official n8n CLI](https://docs.n8n.io/deploy/host-n8n/configure-n8n/use-the-command-line).
Valhalla uses the [official scripted image](https://github.com/valhalla/valhalla/blob/master/docker/README.md)
and [OpenStreetMap France's Western Cape extract](https://download.openstreetmap.fr/extracts/africa/south_africa/).
Map data is © OpenStreetMap contributors, ODbL; preserve attribution when publishing.
