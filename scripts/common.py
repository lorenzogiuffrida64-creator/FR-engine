"""Shared helpers: config, .env, HTTP, archive and request folders. Standard library + Pillow/numpy only.

Everything client-specific lives in the private folder (default `<repo>/private`, override with
FR_PRIVATE_DIR): archive, mood boards, requests, library, and `config.json` overrides."""
import base64, datetime as dt, json, mimetypes, os, pathlib, re, stat, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIVATE = pathlib.Path(os.environ.get("FR_PRIVATE_DIR") or ROOT / "private").resolve()


def _merge(base, over):
    for k, v in over.items():
        base[k] = _merge(base.get(k, {}), v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return base


CFG = json.loads((ROOT / "config.json").read_text())
if (PRIVATE / "config.json").exists():
    CFG = _merge(CFG, json.loads((PRIVATE / "config.json").read_text()))
REQ = PRIVATE / "requests"
ARCHIVE = PRIVATE / "archive"
LIBRARY = PRIVATE / "library"
UA = {"User-Agent": "fr-engine/1.0"}
SECRET_ENV = ("HF_API_KEY_ID", "HF_API_KEY_SECRET", "FAL_KEY", "FOOTBALL_DATA_TOKEN")
MAX_DOWNLOAD = 60 * 1024 * 1024  # bytes; generated images are a few MB


# ---------- environment ----------

def load_env():
    env = ROOT / ".env"
    if env.exists():
        mode = env.stat().st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):  # readable by other users on this machine
            os.chmod(env, 0o600)
            print("security: .env was readable by other users, permissions set to 600", file=sys.stderr)
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need_env(*names):
    load_env()
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"missing {', '.join(missing)}: add them to .env (see .env.example)")
    return [os.environ[n] for n in names]


def redact(text):
    """Remove any loaded secret from a string before it is printed or logged."""
    text = str(text)
    for n in SECRET_ENV:
        v = os.environ.get(n)
        if v and len(v) >= 6:
            text = text.replace(v, "[redacted]")
    return re.sub(r"(Key|Bearer|Token)\s+[A-Za-z0-9_\-:.]{12,}", r"\1 [redacted]", text)


# ---------- http ----------

class HTTPError(Exception):
    def __init__(self, status, body):
        body = redact(body)
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status, self.body = status, body


def _check_url(url):
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or not p.hostname:
        raise ValueError(f"refusing non-https URL: {redact(url)[:120]}")
    return url


def http_json(method, url, headers=None, body=None, timeout=60):
    _check_url(url)
    data = json.dumps(body).encode() if body is not None else None
    h = dict(UA, **(headers or {}))
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(MAX_DOWNLOAD).decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise HTTPError(e.code, e.read(20000).decode(errors="replace"))


def download(url, dest: pathlib.Path):
    """Save an image from an https URL or a data: URI, capped at MAX_DOWNLOAD and checked to be an image."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("data:"):
        raw = base64.b64decode(url.split(",", 1)[1])
    else:
        req = urllib.request.Request(_check_url(url), headers=UA)  # no auth headers: CDNs get nothing secret
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read(MAX_DOWNLOAD + 1)
    if len(raw) > MAX_DOWNLOAD:
        raise ValueError(f"download larger than {MAX_DOWNLOAD // 2**20} MB, refused")
    if not raw[:4] in (b"\x89PNG", b"RIFF") and raw[:3] != b"\xff\xd8\xff":
        raise ValueError("download is not a PNG/JPEG/WebP image, refused")
    dest.write_bytes(raw)
    return dest


def data_uri(path: pathlib.Path):
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def poll(fn, interval, timeout):
    """Call fn() until it returns a non-None value. interval = [start, max] seconds, backing off."""
    wait, start = interval[0], time.time()
    while True:
        out = fn()
        if out is not None:
            return out
        if time.time() - start > timeout:
            raise TimeoutError(f"no result after {timeout}s")
        time.sleep(wait)
        wait = min(wait * 1.5, interval[1])


# ---------- archive ----------

def slugify(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


def safe_id(value, what="id"):
    """Slugs and request ids become folder names: allow only a-z, 0-9 and '-' (no '..', '/', or spaces)."""
    if not isinstance(value, str) or not SAFE_ID.match(value):
        sys.exit(f"invalid {what} {value!r}: use lowercase letters, digits and '-' only")
    return value


def club(slug):
    safe_id(slug, "club")
    p = ARCHIVE / "clubs" / slug / "club.json"
    if not p.exists():
        sys.exit(f"club {slug!r} not in archive (expected {p})")
    c = json.loads(p.read_text()); c["_dir"] = p.parent
    return c


def player(slug):
    safe_id(slug, "player")
    p = ARCHIVE / "players" / slug / "player.json"
    if not p.exists():
        sys.exit(f"player {slug!r} not in archive (expected {p})")
    d = json.loads(p.read_text()); d["_dir"] = p.parent
    return d


def all_clubs():
    out = []
    for p in sorted((ARCHIVE / "clubs").glob("*/club.json")):
        c = json.loads(p.read_text()); c["_dir"] = p.parent; out.append(c)
    return out


def all_players():
    out = []
    for p in sorted((ARCHIVE / "players").glob("*/player.json")):
        d = json.loads(p.read_text()); d["_dir"] = p.parent; out.append(d)
    return out


def face_files(pl, limit=None):
    files = sorted(x for x in (pl["_dir"] / "faces").glob("*") if x.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    return files[:limit] if limit else files


def protected_words():
    """Names that must never appear in a Soul prompt (identity comes later)."""
    words = set()
    for c in all_clubs():
        words.update([c["name"], c.get("short", "")] + c.get("aliases", []))
        for k in c.get("kits", {}).values():
            if k.get("sponsor"):
                words.add(k["sponsor"])
    for pl in all_players():
        words.update([pl["name"], pl.get("shirt_name", "")] + pl["name"].split()[-1:])
    return sorted(w for w in words if w and len(w) > 2)


# ---------- requests ----------

def today():
    return dt.date.today().isoformat()


def req_dir(rid):
    d = REQ / safe_id(rid, "request id")
    if not (d / "request.json").exists():
        known = sorted(p.name for p in REQ.iterdir() if (p / "request.json").exists()) if REQ.exists() else []
        sys.exit(f"unknown request {rid!r}. Known: {known[-10:]}")
    return d


def load_req(rid):
    return json.loads((req_dir(rid) / "request.json").read_text())


def save_req(r):
    d = REQ / safe_id(r["id"], "request id"); d.mkdir(parents=True, exist_ok=True)
    (d / "request.json").write_text(json.dumps(r, indent=2, ensure_ascii=False))


def read_json(path, default):
    path = pathlib.Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, data):
    pathlib.Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def out(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))
