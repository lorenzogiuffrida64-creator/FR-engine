"""Higgsfield API client for Soul 2.0 and Soul Cinema (docs.higgsfield.ai).

Auth: `Authorization: Key <id>:<secret>`. Submissions are queued; poll `status_url` until
status is completed / failed / nsfw / canceled. Images come back in `images[].url`.
"""
import uuid
from concurrent.futures import ThreadPoolExecutor

from common import CFG, HTTPError, http_json, need_env, poll

H = CFG["higgsfield"]
TERMINAL = {"completed", "failed", "nsfw", "canceled"}


def _auth():
    kid, secret = need_env(H["env_key_id"], H["env_key_secret"])
    return {"Authorization": f"Key {kid}:{secret}"}


def submit(model_key, prompt, aspect_ratio=None, batch_size=None, seed=None, style_id=None):
    """model_key: 'soul' or 'cinema'. Returns the queued request handle."""
    model = H["models"][model_key]
    body = {"prompt": prompt, "aspect_ratio": aspect_ratio or H["aspect_ratio"],
            "resolution": H["resolution"], "batch_size": batch_size or H["batch_size"], "enhance_prompt": False}
    if seed:
        body["seed"] = seed
    if style_id and model_key == "soul":  # Cinema has a fixed style and ignores style_id
        body["style_id"] = style_id
    headers = dict(_auth(), **{"Idempotency-Key": str(uuid.uuid4())})
    r = http_json("POST", f"{H['base_url']}/{model}", headers=headers, body=body)
    r["model"] = model_key
    return r


def wait(handle):
    url = handle.get("status_url") or f"{H['base_url']}/requests/{handle['request_id']}/status"
    auth = _auth()

    def check():
        r = http_json("GET", url, headers=auth)
        return r if r.get("status") in TERMINAL else None

    return poll(check, H["poll_seconds"], H["timeout_seconds"])


def generate(jobs):
    """jobs: [{model, prompt, aspect_ratio, prompt_id}] → [{...job, status, images:[url], request_id, error}].
    Runs up to max_parallel at once."""
    def run(job):
        try:
            h = submit(job["model"], job["prompt"], job.get("aspect_ratio"), seed=job.get("seed"), style_id=job.get("style_id"))
            r = wait(h)
            return dict(job, status=r["status"], request_id=r.get("request_id"),
                        images=[i["url"] for i in r.get("images", [])])
        except (HTTPError, TimeoutError, OSError) as e:
            return dict(job, status="error", images=[], error=str(e))

    with ThreadPoolExecutor(max_workers=H["max_parallel"]) as ex:
        return list(ex.map(run, jobs))


def styles():
    return http_json("GET", f"{H['base_url']}/v1/text2image/soul-styles/v2", headers=_auth())
