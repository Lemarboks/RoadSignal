# Evidence and traffic-analysis workers

These are internal, CPU-only decision-support services. They are **not fact-checking authorities** and do not establish that a road incident occurred. No live camera, news or traffic feed is connected by these workers.

## Installed components and licenses

| Role | Component | License | Exact revision/version |
| --- | --- | --- | --- |
| `verification` | [DeBERTa-v3-base-mnli-fever-anli](https://huggingface.co/MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli) | MIT, model author's card | `6f5cf0a2b59cabb106aca4c287eed12e357e90eb` |
| `vision` | [RT-DETR R18](https://huggingface.co/PekingU/rtdetr_r18vd), [upstream](https://github.com/lyuwenyu/RT-DETR) | Apache-2.0 | `ac77a11ff0170a41b771c03264987f8ce2b0d753` |
| `vision` | [Supervision ByteTrack implementation](https://github.com/roboflow/supervision/tree/0.27.0), based on [ByteTrack](https://github.com/FoundationVision/ByteTrack) | [MIT](https://github.com/roboflow/supervision/blob/0.27.0/LICENSE.md) | `supervision==0.27.0` |

Supervision 0.27.0 is intentionally pinned to its built-in ByteTrack API. Newer Supervision versions deprecate that API; do not unpin it without migrating and retesting tracking. Package license notices remain in the installed distributions. The Docker image reuses `roadsignal-retrieval:local` (PyTorch 2.8.0 CPU, Transformers 4.56.2), and adds pinned dependencies from `requirements.txt`. Supervision is installed without dependency resolution so headless OpenCV replaces its GUI-enabled OpenCV requirement.

Model downloads use fixed revisions, `trust_remote_code=False` where applicable and safetensors-only weights. Downloads occur during background startup into the existing `/models` cache. `/health` indicates that the process is running; `/ready` returns HTTP 503 until the model and role-specific imports have loaded. A successful image build alone does not mean weights have downloaded or inference passed.

## HTTP contract

Both roles listen on port 8080. Set `MODEL_ROLE=verification` or `MODEL_ROLE=vision` in separate containers. Set a nonempty `WORKER_TOKEN` and pass it as `X-Worker-Token` on every POST/DELETE. Health/readiness endpoints need no token. Keep these workers on a private Docker network; do not publish unauthenticated inference to the Internet. They do not provide end-user authorization or tenancy: the calling application must enforce operator permissions and session ownership.

`POST /verify` accepts:

```json
{
  "claim": "The example road is closed.",
  "evidence": [{
    "text": "Synthetic source text describing the example road.",
    "source_url": "https://example.com/demo-report",
    "observed_at": "2026-09-11T12:00:00Z"
  }]
}
```

Returns `assessment: "textual_consistency_only"`, `sources` with each supplied URL/timestamp and entailment/neutral/contradiction scores, `requires_review: true`, plus limitations. The evidence passage is the NLI premise and the claim is the hypothesis. Scores are not calibrated probabilities of real-world truth. An English NLI model can agree with false or manipulated evidence; repeated copies of one story are not independent sources. No source URL is fetched, no source reliability is inferred, and no automatic incident publication occurs. Operators must check origin, independence, freshness, geography, and corroborating evidence before accepting a report.

Limits: claim 500 characters and 192 model tokens; 1–5 evidence passages, each 3,000 characters; each pair 512 model tokens. Longer evidence is truncated and explicitly flagged. Source URLs have no embedded credentials, use HTTP(S), and are at most 2,048 characters. Optional observation timestamps must include a timezone. The worker does not invent missing timestamps or verify supplied ones.

`POST /frames` accepts:

```json
{
  "session_id": "demo-camera-1",
  "frame_index": 0,
  "image_base64": "BASE64_ENCODED_PNG_OR_JPEG_BYTES",
  "source": "demo",
  "authorization_confirmed": false,
  "frame_rate": 5
}
```

For real, permissioned frames use `source: "authorized"` and `authorization_confirmed: true`. This declaration is not a substitute for access control, camera-owner permission, lawful processing or a retention policy. There is no camera URL/RTSP download endpoint and no arbitrary URL fetching. The calling service chooses and supplies approved frames.

Returns frame size, vehicle boxes/confidence, short-lived `track_id`, counts per class, `source`, `requires_review: true` and `retained_images: false`. Only bicycle, car, motorcycle, bus, truck and train boxes are returned. There is no person identification, number-plate recognition, real-world vehicle identity, calibrated speed, collision detection or verified incident output. Counts mean currently associated boxes in one frame, **not vehicles per hour or unique journeys**. Low-quality imagery, camera movement and occlusions can cause errors. A changed class may get a new ID. Evaluate against labelled examples from each authorized camera before using counts operationally.

Frames must arrive consecutively beginning at index 0, with a constant declared frame rate and provenance per session. Duplicate/out-of-order indices return 409. Send `DELETE /sessions/{session_id}` to reset. There are at most eight sessions, each expiring after 120 seconds idle (a 10-second sweeper removes idle state), with at most 1,800 frames per session; use a new session afterwards. At most 100 detections are considered per frame. Only tracking state is retained in memory; decoded image bytes are discarded after each request. Track IDs are local to a session/class, not durable identifiers.

Image limits: one PNG/JPEG frame, at most 2 MiB decoded bytes, 2,073,600 pixels total and 2,048 pixels per side. Actual request bodies, including chunked bodies, are capped at 3 MiB before JSON parsing. One inference request runs per container; a busy worker returns 429. Callers should use bounded retries and mark failures unavailable, never replace failed observations with invented live values.

## Authenticated RoadSignal API

The public API exposes `GET /api/v1/monitoring/vision/status`, `POST /api/v1/monitoring/vision/frames`, and `DELETE /api/v1/monitoring/vision/sessions/{session_id}`. All require a signed-in user even when general demo authentication is disabled. Drivers and fleet managers may submit only `source: "demo"`; `source: "authorized"` additionally requires an administrator or incident moderator and an explicit permission declaration. Each user's session IDs are hashed into a separate worker namespace, preventing another user's frames or reset request from sharing that session.

The API deliberately has tighter image limits than the internal worker: 512 KiB decoded image and 768 KiB actual request body, including chunked bodies. Submit compressed PNG/JPEG JSON frames; no arbitrary URLs or multipart uploads are accepted. Pixel bounds and complete image decoding are enforced again by the worker. Configured service URLs come only from `VISION_BASE_URL` and `VERIFICATION_BASE_URL`, never request input; redirect following and environment-proxy inheritance are disabled.

`POST /api/v1/monitoring/evidence/compare` accepts the verification request above and requires an administrator or incident moderator. It compares text only and does not create an inbox entry, publish an incident, or change route risk. User-facing responses always retain `requires_review: true`; comparison responses additionally return `incident_published: false`. Worker errors and validation errors are sanitized so source text, images and internal credentials are not echoed in error bodies. An unavailable model returns 503, not invented demo observations.

Optional `MODEL_WORKER_TOKEN_FILE` lets the API read a mounted 32–512-character internal credential and forward it as `X-Worker-Token`; the same credential must be configured as the workers' `WORKER_TOKEN`. Empty means internal network-only workers without that additional shared token. `MONITORING_MODEL_TIMEOUT_SECONDS` defaults to 90 and is bounded to 1–120 seconds. Status probes use a three-second timeout.

## Hardware and smoke checks

Initial budgeting estimates, not measured guarantees: allocate 2 GiB RAM to NLI and 1.5 GiB to vision, with two CPU threads each. NLI weights are roughly 0.7 GiB; RT-DETR R18 weights are about 81 MB. Startup and image processing add substantial runtime memory. CPU throughput depends on the machine; this setup does not promise real-time 30 FPS. On an 8 GiB Docker VM, stage these roles alongside the other models/services rather than starting every optional model at once.

Build from the repository root after the retrieval base image exists:

```powershell
docker build -t roadsignal-verification:local infrastructure/verification
python -m pytest infrastructure/verification/tests -q
```

After a worker's `/ready` reports 200, run `python /service/smoke.py` inside that container. It uses the container's own `WORKER_TOKEN`, if set, without printing it. The NLI smoke performs real model inference on two expressly synthetic statements. The vision smoke performs real RT-DETR inference on two blank synthetic PNG frames and real ByteTrack association on two synthetic vehicle boxes. Successful smoke checks prove model loading and the contract, **not accuracy on real news or local traffic**. No real camera source or notification recipient is contacted.
