"""Шаг 3. Поиск почти-дублей по кадрам.

Для каждой прошедшей записи берём 3 кадра (20 %, 50 %, 80 % длительности).
Кадры — это маленькие JPEG-миниатюры, которые Викисклад сам строит для видео
(стандартная ширина 330 px, параметр seek), то есть сам ролик не скачиваем.
Если миниатюру получить не удалось — запасной путь: ffmpeg -ss … -frames:v 1
по ссылке на уменьшенную копию ролика (читается только нужный кусок).

По каждому кадру считаем перцептивный хэш (pHash). Две записи — почти-дубль,
если средняя дистанция между их кадрами (с подбором лучшей пары кадров,
чтобы ловить и обрезанные версии) не больше dedup.max_distance.
Группы почти-дублей склеиваются, остаётся запись с лучшим разрешением.

Выход: work/passed_dedup.json, work/rejected_dedup.json, output/previews/*.jpg
"""
import io
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path

import imagehash
import requests
import yaml
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent
WORK, PREV, FRAMES = ROOT / "work", ROOT / "output" / "previews", ROOT / "tmp" / "frames"
THUMB_W = 330  # стандартный размер миниатюр Викисклада


def thumb_url(file_url: str, t: float) -> str:
    # https://upload.wikimedia.org/wikipedia/commons/a/ab/Name.webm ->
    # https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Name.webm/330px-seek%3D12-Name.webm.jpg
    rest = file_url.split("/wikipedia/commons/", 1)[1]
    name = rest.rsplit("/", 1)[1]
    # миниатюры Викисклад отдаёт с отдельного хоста thumb.wikimedia.org
    return f"https://thumb.wikimedia.org/wikipedia/commons/thumb/{rest}/{THUMB_W}px-seek%3D{t:g}-{name}.jpg"


class MediaClient:
    def __init__(self, ua, delay):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = ua
        self.ua, self.delay, self._last = ua, delay, 0.0
        self.n_thumb = self.n_ffmpeg = self.n_wait = 0

    def _pace(self):
        dt = time.monotonic() - self._last
        if dt < self.delay:
            time.sleep(self.delay - dt)
        self._last = time.monotonic()

    def thumb(self, url, tries=6):
        for i in range(tries):
            self._pace()
            try:
                r = self.s.get(url, timeout=60)
            except requests.RequestException:
                time.sleep(5 * (i + 1))
                continue
            if r.status_code == 429:
                wait = max(int(r.headers.get("Retry-After") or 0), 5 * (i + 1))
                self.n_wait += 1
                print(f"    сервер файлов просит подождать {wait} с")
                time.sleep(min(wait, 120))
                continue
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                self.n_thumb += 1
                return Image.open(io.BytesIO(r.content)).convert("RGB")
            return None
        return None

    def ffmpeg_frame(self, url, t, out: Path):
        self._pace()
        cmd = ["ffmpeg", "-v", "error", "-user_agent", self.ua, "-ss", f"{t:.2f}", "-i", url,
               "-frames:v", "1", "-vf", f"scale={THUMB_W}:-2:out_range=full,format=yuvj420p",
               "-q:v", "4", "-y", str(out)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return None
        if p.returncode == 0 and out.exists() and out.stat().st_size > 0:
            self.n_ffmpeg += 1
            return Image.open(out).convert("RGB")
        return None


def small_derivative(rec):
    webms = [d for d in rec.get("derivatives", []) if d.get("type", "").startswith("video/webm")]
    webms.sort(key=lambda d: d.get("height") or 10**6)
    good = [d for d in webms if (d.get("height") or 0) >= 240]
    return (good or webms or [{"src": rec["file_url"]}])[0]["src"]


def frames_for(rec, cfg, mc: MediaClient):
    imgs = []
    for k, frac in enumerate(cfg["dedup"]["frames_at"]):
        t = round(rec["duration_s"] * frac, 1)
        cache = FRAMES / f"{rec['pageid']}_{k}.jpg"
        if cache.exists():
            imgs.append(Image.open(cache).convert("RGB"))
            continue
        img = mc.thumb(thumb_url(rec["file_url"], t))
        if img is None:
            img = mc.ffmpeg_frame(small_derivative(rec), t, cache)
        if img is None:
            return None
        img.save(cache, quality=85)
        imgs.append(img)
    return imgs


def pair_distance(ha, hb):
    """Для каждого кадра A — ближайший кадр B (и наоборот), берём среднее, худшее из двух направлений."""
    d_ab = sum(min(a - b for b in hb) for a in ha) / len(ha)
    d_ba = sum(min(b - a for a in ha) for b in hb) / len(hb)
    return max(d_ab, d_ba)


def main():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    for d in (PREV, FRAMES):
        d.mkdir(parents=True, exist_ok=True)
    recs = json.loads((WORK / "passed_check.json").read_text(encoding="utf-8"))
    pw = cfg["dedup"]["preview_width"]
    # не больше 2 одновременных обращений к серверу файлов (правила Wikimedia для ботов)
    workers = min(int(cfg["dedup"].get("workers", 2)), 2)
    clients = [MediaClient(cfg["api"]["user_agent"], cfg["api"]["media_delay_s"]) for _ in range(workers)]
    local = threading.local()
    pool_ids = iter(range(workers))
    lock = threading.Lock()
    done = [0]
    t0 = time.time()

    def job(r):
        if not hasattr(local, "mc"):
            with lock:
                local.mc = clients[next(pool_ids)]
        imgs = frames_for(r, cfg, local.mc)
        with lock:
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(recs):
                print(f"  [{done[0]}/{len(recs)}] кадры: миниатюр {sum(c.n_thumb for c in clients)}, "
                      f"ffmpeg {sum(c.n_ffmpeg for c in clients)}, {time.time() - t0:.0f} с")
        return imgs

    with ThreadPoolExecutor(max_workers=workers) as ex:
        all_imgs = list(ex.map(job, recs))

    ok, rejected, hashes = [], [], {}
    for i, (r, imgs) in enumerate(zip(recs, all_imgs), 1):
        if not imgs:
            rejected.append({**r, "stage": "C: кадры", "reason": "не удалось получить кадры для проверки"})
            print(f"  [{i}/{len(recs)}] нет кадров: {r['title'][:60]}")
            continue
        hashes[r["pageid"]] = [imagehash.phash(im) for im in imgs]
        mid = imgs[len(imgs) // 2]
        mid = mid.resize((pw, round(mid.height * pw / mid.width)))
        r["preview_frame"] = f"previews/{r['pageid']}.jpg"
        mid.save(PREV / f"{r['pageid']}.jpg", quality=80)
        ok.append(r)

    # точные дубли по SHA-1 и почти-дубли по pHash: объединение в группы (union-find)
    parent = {r["pageid"]: r["pageid"] for r in ok}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    maxd = cfg["dedup"]["max_distance"]
    links = []
    by_id = {r["pageid"]: r for r in ok}
    for a, b in combinations(ok, 2):
        if a["sha1"] and a["sha1"] == b["sha1"]:
            d = 0.0
        else:
            d = pair_distance(hashes[a["pageid"]], hashes[b["pageid"]])
        if d <= maxd:
            links.append((a["pageid"], b["pageid"], round(d, 1)))
            parent[find(a["pageid"])] = find(b["pageid"])

    groups = {}
    for r in ok:
        groups.setdefault(find(r["pageid"]), []).append(r)
    kept = []
    for g in groups.values():
        g.sort(key=lambda r: (r["width"] * r["height"], r["fps"] or 0, r["size_mb"]), reverse=True)
        best = g[0]
        best["near_dups_removed"] = len(g) - 1
        kept.append(best)
        for r in g[1:]:
            d = min((x[2] for x in links if {x[0], x[1]} == {r["pageid"], best["pageid"]}), default=None)
            why = f"почти-дубль записи commons-{best['pageid']} (оставлена: {best['width']}×{best['height']})"
            if d is not None:
                why += f", дистанция pHash {d}"
            rejected.append({**r, "stage": "C: дедупликация", "reason": why})

    (WORK / "passed_dedup.json").write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
    (WORK / "rejected_dedup.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=1), encoding="utf-8")
    (WORK / "dup_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=1), encoding="utf-8")
    n_groups = sum(1 for g in groups.values() if len(g) > 1)
    print(f"Кадры: миниатюр {sum(c.n_thumb for c in clients)}, через ffmpeg {sum(c.n_ffmpeg for c in clients)}, "
          f"ожиданий по 429: {sum(c.n_wait for c in clients)}")
    print(f"Групп почти-дублей: {n_groups}; осталось {len(kept)} из {len(ok)}")


if __name__ == "__main__":
    main()
