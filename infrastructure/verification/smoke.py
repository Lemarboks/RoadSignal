"""Run real inference on explicitly synthetic text / blank frames, never news."""
import argparse
import base64
import io
import json
import os
import urllib.request


def call(base_url, path, payload=None):
    headers = {"Content-Type": "application/json"}
    if os.getenv("WORKER_TOKEN"):
        headers["X-Worker-Token"] = os.environ["WORKER_TOKEN"]
    request = urllib.request.Request(base_url.rstrip("/") + path,
                                     data=json.dumps(payload).encode() if payload else None, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    ready = call(args.url, "/ready")
    if ready["role"] == "verification":
        result = call(args.url, "/verify", {
            "claim": "The example road is closed.",
            "evidence": [
                {"text": "In this synthetic example, the example road is closed.", "source_url": "https://example.com/demo-closed"},
                {"text": "In this synthetic example, the example road is open and is not closed.", "source_url": "https://example.com/demo-open"},
            ],
        })
        assert result["requires_review"] is True
        assert result["sources"][0]["scores"]["entailment"] > result["sources"][0]["scores"]["contradiction"]
        assert result["sources"][1]["scores"]["contradiction"] > result["sources"][1]["scores"]["entailment"]
        print(json.dumps({"smoke": "passed", "role": ready["role"], "synthetic": True, "result": result}))
    else:
        from PIL import Image
        import uuid
        image = Image.new("RGB", (320, 180), (100, 100, 100))
        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        payload = {"session_id": "smoke-" + uuid.uuid4().hex, "source": "demo", "frame_index": 0,
                   "image_base64": base64.b64encode(encoded.getvalue()).decode()}
        result = call(args.url, "/frames", payload)
        assert result["source"] == "demo" and result["retained_images"] is False
        assert not result["tracks"], "Blank synthetic frame should not contain vehicles"
        payload["frame_index"] = 1
        result = call(args.url, "/frames", payload)
        # Exercise real ByteTrack association with explicitly synthetic boxes;
        # the blank frame correctly exercises real RT-DETR with zero vehicles.
        from server import track_detections
        session = {"frame_rate": 5, "trackers": {}}
        first = track_detections(session, [{"label": "car", "score": 0.95, "bbox": [10, 10, 80, 70]}])
        second = track_detections(session, [{"label": "car", "score": 0.95, "bbox": [12, 10, 82, 70]}])
        assert len(first) == len(second) == 1 and first[0]["track_id"] == second[0]["track_id"]
        print(json.dumps({"smoke": "passed", "role": ready["role"], "synthetic": True,
                          "bytetrack_same_id": True, "result": result}))


if __name__ == "__main__":
    main()
