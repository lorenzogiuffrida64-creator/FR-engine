"""fal.ai queue client for image edits (Nano Banana 2.1 Edit and the fallback chain).

REST queue: POST https://queue.fal.run/<endpoint> with `Authorization: Key <FAL_KEY>` returns
request_id + status_url + response_url. Poll status_url until COMPLETED, then GET response_url.
"""
from common import CFG, HTTPError, data_uri, http_json, need_env, poll

F = CFG["fal"]


def _auth():
    (key,) = need_env(F["env_key"])
    return {"Authorization": f"Key {key}"}


EDIT_RATIOS = ["21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4", "2:3", "9:16"]


def nearest_ratio(path):
    """The Nano Banana ratio closest to the image at path ("auto" if it can't be read)."""
    import math
    try:
        from PIL import Image
        w, h = Image.open(path).size
    except Exception:
        return "auto"
    return min(EDIT_RATIOS, key=lambda r: abs(math.log((w / h) / (int(r.split(":")[0]) / int(r.split(":")[1])))))


def safety_for(model):
    """Safety fields for this model from config (first id-prefix match), e.g. {"safety_tolerance": "6"}."""
    for prefix, fields in F.get("safety", {}).items():
        if model.startswith(prefix):
            return dict(fields)
    return {}


def edit(model, prompt, images, aspect_ratio="auto"):
    """images: list of local paths (image 1 first). Returns the result dict ({images:[{url,...}], description})."""
    auth = _auth()
    body = {"prompt": prompt, "image_urls": [data_uri(p) for p in images], "num_images": 1,
            "output_format": F["output_format"]}
    if model.startswith("google/nano-banana"):
        # A fixed ratio, the one of image 1: with "auto" an edit once came back landscape and re-framed.
        ratio = nearest_ratio(images[0]) if aspect_ratio == "auto" else aspect_ratio
        body.update({"resolution": F["resolution"], "aspect_ratio": ratio})
    body.update(safety_for(model))
    h = http_json("POST", f"{F['queue_url']}/{model}", headers=auth, body=body, timeout=120)
    status_url = h.get("status_url") or f"{F['queue_url']}/{model}/requests/{h['request_id']}/status"
    response_url = h.get("response_url") or f"{F['queue_url']}/{model}/requests/{h['request_id']}"

    def check():
        s = http_json("GET", status_url, headers=auth)
        if s.get("status") == "COMPLETED":
            return s
        if s.get("status") in ("FAILED", "ERROR", "CANCELLED"):
            raise HTTPError(500, str(s))
        return None

    poll(check, F["poll_seconds"], F["timeout_seconds"])
    return http_json("GET", response_url, headers=auth)


def edit_with_fallback(prompt, images, accept, aspect_ratio="auto"):
    """Try each model in config order. accept(result) -> (ok, reason). Returns (result, model, attempts)."""
    attempts = []
    for model in F["edit_models"]:
        try:
            r = edit(model, prompt, images, aspect_ratio)
            if not r.get("images"):
                attempts.append({"model": model, "ok": False, "reason": f"no image: {r.get('description', '')[:200]}"})
                continue
            ok, reason = accept(r)
            attempts.append({"model": model, "ok": ok, "reason": reason})
            if ok:
                return r, model, attempts
        except (HTTPError, TimeoutError, OSError) as e:
            attempts.append({"model": model, "ok": False, "reason": str(e)[:300]})
    return None, None, attempts
