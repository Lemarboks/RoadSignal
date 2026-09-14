# Local open-source intelligence

RoadSignal adds incident aggregation and review assistance to its existing routing workflow. Route safety scores still come from the deterministic engine. Model output never submits an incident, changes a score, merges reports, or starts an emergency response.

## What is implemented

The Fleet workspace has a browser replay and a connected Traccar/ThingsBoard demonstration. See [monitoring setup](monitoring-setup.md) for n8n, local text/vision workers, regional routing and memory-saving service modes. All vehicle and sensor inputs remain synthetic; no live source credentials are required.

| Component | Integration | Availability |
| --- | --- | --- |
| H3 | Incident-count map layer, cell statistics and data provenance | Included in the API; no model download |
| Qwen3-Embedding-0.6B | Similar-report candidates after distance/time filtering | Optional CPU `retrieval` profile |
| Qwen3-Reranker-0.6B | Reorder a bounded set of potential duplicate reports | Optional CPU `rerank` profile |
| gpt-oss-20b | Structured incident classification and selection of saved route evidence | Optional `llm-gpu` profile or your own compatible server |
| Whisper / faster-whisper | Audio file transcription into an editable report | Optional CPU `voice` profile |
| OpenTelemetry + Jaeger | API and inference traces without report/audio contents | Optional `tracing` profile |
| XGBoost | Offline candidate training, calibration, temporal/geographic evaluation | Installed Docker training toolchain; an approved real dataset is still required |
| Valhalla | Local Western Cape road graph with OSRM fallback | `routing` profile in the monitoring overlay; persistent regional tiles |
| DeBERTa NLI | Supplied-text support/contradiction comparison | CPU `verification` profile; not a truth verifier |
| RT-DETR + ByteTrack | Bounded frame detection and anonymous track association | CPU `vision` profile; no camera feed connected |
| Traccar + ThingsBoard CE | Four demo GPS trackers and three demo street stations | `monitoring` + `sensors` profiles |
| n8n | Freshness alerts, daily summaries and operator evidence intake | Local `monitoring` profile; source-available, not OSI open source |

Phoenix was suggested during planning, but its Elastic License restricts some hosting uses. The implemented tracing stack uses OpenTelemetry and Jaeger instead. Model weights and software have separate licenses; permissive weights do not imply that their complete training datasets are open.

## Start the showcase

The ordinary four-service stack works without any models:

```sh
docker compose up -d --build
```

For this machine (8 GB allocated to Docker, Intel integrated graphics), use the [monitoring setup helper](monitoring-setup.md) to switch workloads. For a retrieval-only installation, the earlier command remains:

```sh
docker compose -f docker-compose.yml -f compose.ai.yml --profile retrieval --profile tracing up -d --build
```

Open the app at http://localhost:3000 and Jaeger at http://localhost:16686. Sign in to use incident assistance. Guest mode supports viewing map counts; expensive inference requires an authenticated session.

The first start downloads model weights into named Docker volumes. `/health` means a worker is running; `/ready` only succeeds after its weights load. The app reports unavailable or loading models honestly and retains keyword-based review assistance when generation/retrieval is offline. The app's service status comes from `/api/v1/assistant/status`.

The local overlay mounts the worker source read-only so code fixes can be picked up by restarting a worker without reinstalling its model runtime. Keep the checkout available while running this showcase. The Docker images also include the source for deployments that do not use this local mount.

Add voice when needed:

```sh
docker compose -f docker-compose.yml -f compose.ai.yml --profile voice up -d --build whisper
```

Whisper defaults to the multilingual `small` model with CPU int8 inference. Files are limited to 10 MiB and 90 seconds of decoded audio. The transcript must be reviewed before applying it to a report. Accuracy must be tested with local accents, place names and the languages the deployment supports; language coverage is not a quality guarantee.

The reranker is a separate process to make its memory cost explicit:

```sh
docker compose -f docker-compose.yml -f compose.ai.yml --profile rerank up -d reranker
```

Each Qwen worker is capped at 3 GB and two CPUs; voice at 1.5 GB. Limits are ceilings, not reservations. Avoid starting all model workers together on an 8 GB Docker allocation: initial downloads, loading and quantization use more memory than idle inference. Stop an optional worker when switching workloads with `docker compose -f docker-compose.yml -f compose.ai.yml stop reranker` (or `whisper`). Existing app/database volumes are preserved.

## Generation on suitable hardware

The gpt-oss profile needs a supported NVIDIA GPU/runtime and sufficient GPU/system memory. It is not suitable for this machine's integrated GPU. On a compatible host, set `AI_ENABLED=true` in `.env`, then run:

```sh
docker compose -f docker-compose.yml -f compose.ai.yml --profile llm-gpu up -d llm api
```

Alternatively set `AI_BASE_URL` to your own OpenAI-compatible server and `AI_MODEL` to its served model name. Only administrator-configured URLs are used; endpoints are never taken from report text. No paid OpenAI API is required. Source material stays within the configured services.

Generation uses a strict response schema, followed by application validation. Route explanations assemble their final numeric statements from saved evidence; the model can select evidence IDs, not rewrite values. Invalid responses and timeouts fall back to a deterministic explanation. Incident classification is a proposal, while the original report text remains editable.

## Routing and future risk modeling

The monitoring overlay provisions Valhalla and downloads the Western Cape OpenStreetMap extract into a persistent regional graph. It selects that local provider by default; `MONITORING_ROUTE_PROVIDER=open` selects public OSRM instead. The adapter includes coordinate/geometry validation and fallback handling. It does not implement a custom risk-costed road graph: safety ranking still happens after route alternatives are generated. Integrating arbitrary risk penalties into Valhalla edges requires a separate map-data pipeline.

For a future trained candidate, read [data and model governance](data-and-model-governance.md). The offline command is:

```sh
cd apps/api
python -m pip install -r requirements-training.txt
python -m app.risk.training --manifest /path/to/reviewed-manifest.json --output-dir /path/to/new-artifact-directory --geographic-holdout "held-out-area"
```

The reviewed manifest must satisfy the existing dataset schema/licensing/hash/coverage gate and include a `training_review` object with `approved: true`, `reviewer`, timezone-aware `reviewed_at`, `collection_methodology`, `privacy_basis`, `sample_size_rationale` and `feature_leakage_review`. The command separates a geographic holdout, uses chronological training/calibration/test splits with an outcome-horizon gap, calibrates predictions and compares them with the baseline. An approved manifest does not by itself establish a model is safe for deployment.

The supplied demonstration data deliberately fails the training gate. No trained risk model is claimed or enabled. The Fleet panel now has an explicit blank-demo-frame test and operator-authorized image intake for local RT-DETR analysis. No dashcam stream is connected; detections do not publish incidents or change safety scores.

## Verification and operations

```sh
cd apps/api
python -m pytest
python scripts/evaluate-assistant.py
```

Assistant tests cover authentication, invalid structured output, unsupported evidence, duplicate gates, model outages and upload limits. The frozen assistant examples exercise the deterministic contract; testing with mocks or fallback outputs is not a benchmark of downloaded models. Evaluate live candidates against reviewed South African examples before enabling generation for real operational decisions.

Jaeger binds its UI to loopback and keeps a bounded in-memory trace history; traces disappear on restart. Do not treat it as durable audit storage. Existing application audit storage remains separate. The AI compose overlay targets the local showcase, not the hardened production network; production needs explicit network membership, access control, retention and compatible worker hardware.

## Upstream documentation and licenses

- [H3, Apache 2.0](https://h3geo.org/docs/)
- [Qwen embeddings, Apache 2.0](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) and [Qwen reranker, Apache 2.0](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)
- [gpt-oss-20b, Apache 2.0](https://developers.openai.com/api/docs/models/gpt-oss-20b) and [vLLM serving](https://docs.vllm.ai/en/v0.11.0/serving/openai_compatible_server.html)
- [Whisper, MIT](https://github.com/openai/whisper) and [faster-whisper, MIT](https://github.com/SYSTRAN/faster-whisper)
- [Jaeger, Apache 2.0](https://github.com/jaegertracing/jaeger) and [OpenTelemetry, Apache 2.0](https://github.com/open-telemetry/opentelemetry-python)
- [Valhalla, MIT](https://github.com/valhalla/valhalla) and [XGBoost, Apache 2.0](https://github.com/dmlc/xgboost)
- [Phoenix Elastic License](https://github.com/Arize-ai/phoenix/blob/main/LICENSE)
