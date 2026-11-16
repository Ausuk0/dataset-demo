"""Шаг 2. Техническая и юридическая проверка кандидатов по критериям ТЗ.

Ничего не скачивает целиком. Каскад:
  A. метаданные Викисклада (уже в raw/candidates.json): тип файла, лицензия,
     автор, длительность, разрешение — отсев без единого обращения к файлу;
  B. для прошедших A — частота кадров (FPS): сначала из заголовка потока,
     который Викисклад хранит в метаданных файла (запрос к API), и только
     если там её нет — ffprobe по ссылке (читает несколько КБ начала файла).
У каждой отклонённой записи сохраняется причина.

Выход: work/passed_check.json, work/rejected_check.json
"""
import json
import re
import subprocess
import sys
import time
from fractions import Fraction
from html import unescape
from pathlib import Path

import yaml

from commons import Commons

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent
RAW, WORK = ROOT / "raw", ROOT / "work"


GENERIC_CREDIT = {"own work", "own", "self-made", "self made", "unknown", "unknown author", "anonymous", ""}


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def em(vi, key):
    return (vi.get("extmetadata", {}).get(key) or {}).get("value", "") or ""


def clean_url(u: str) -> str:
    return u.split("?", 1)[0] if u else u


def license_ok(short: str, cr) -> tuple[bool, str]:
    if not short:
        return False, "лицензия не указана"
    up = short.upper()
    for w in cr["licenses_forbidden_words"]:
        if re.search(r"(^|[\s\-])" + re.escape(w.upper()) + r"($|[\s\-])", up):
            return False, f"лицензия не открытая: {short}"
    s = short + " "
    if any(s.upper().startswith(a.upper()) for a in cr["licenses_allowed"]):
        return True, ""
    return False, f"лицензия не из списка ТЗ: {short}"


def stage_a(rec, cr):
    """Проверки только по метаданным. Возвращает (список причин, нормализованная запись)."""
    vi = rec["videoinfo"]
    reasons = []
    w, h = int(vi.get("width") or 0), int(vi.get("height") or 0)
    dur = float(vi.get("duration") or 0)
    mime = vi.get("mime", "")
    lic = strip_html(em(vi, "LicenseShortName"))
    author = strip_html(em(vi, "Artist"))
    credit = strip_html(em(vi, "Credit"))
    # «Own work», «Unknown» и т. п. в поле «Источник» — это не автор, атрибуцию по ним не сделать
    if not author and credit.lower().strip(" .") not in GENERIC_CREDIT:
        author = credit
    if author.lower().strip(" .") in GENERIC_CREDIT:
        author = ""
    if rec.get("excluded_by_category"):
        reasons.append("тематика вне ТЗ (анимация/ИИ/игры/ДТП по категориям)")
    low_title = rec["title"].lower()
    bad = [w for w in cr.get("exclude_title_words", []) if w.lower() in low_title]
    if bad:
        reasons.append(f"тематика вне ТЗ (по названию: {', '.join(bad)})")
    if mime not in cr["mime_allowed"]:
        reasons.append(f"тип файла {mime}")
    ok, why = license_ok(lic, cr)
    if not ok:
        reasons.append(why)
    if cr.get("require_author") and not author:
        reasons.append("нет автора/источника для атрибуции")
    if dur < cr["duration_min_s"]:
        reasons.append(f"короче {cr['duration_min_s']} с ({dur:.1f} с)")
    elif dur > cr["duration_max_s"]:
        reasons.append(f"длиннее {cr['duration_max_s']} с ({dur:.1f} с)")
    long_side, short_side = max(w, h), min(w, h)
    if long_side < cr["min_width"] or short_side < cr["min_height"]:
        reasons.append(f"разрешение ниже {cr['min_width']}×{cr['min_height']} ({w}×{h})")
    norm = {
        "pageid": rec["pageid"],
        "title": rec["title"],
        "theme": rec["theme"],
        "source_category": rec["source_category"],
        "file_url": clean_url(vi.get("url", "")),
        "page_url": vi.get("descriptionurl", ""),
        "author": author[:200],
        "license": lic,
        "license_url": em(vi, "LicenseUrl"),
        "attribution_required": em(vi, "AttributionRequired"),
        "duration_s": round(dur, 2),
        "width": w, "height": h,
        "size_mb": round(int(vi.get("size") or 0) / 1048576, 2),
        "mime": mime,
        "sha1": vi.get("sha1", ""),
        "categories": em(vi, "Categories"),
        "description": strip_html(em(vi, "ImageDescription"))[:300],
        "derivatives": vi.get("derivatives", []),
    }
    return reasons, norm


def walk(obj):
    """Плоский обход вложенного формата metadata MediaWiki (списки name/value)."""
    if isinstance(obj, list):
        for x in obj:
            if isinstance(x, dict) and "name" in x and "value" in x:
                yield str(x["name"]), x["value"]
                yield from walk(x["value"])
            else:
                yield from walk(x)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k), v
            yield from walk(v)


def fps_from_metadata(meta) -> float | None:
    vals = {}
    for k, v in walk(meta):
        if not isinstance(v, (list, dict)):
            vals.setdefault(k.lower(), v)
    try:
        if "frn" in vals and "frd" in vals and float(vals["frd"]):
            return float(vals["frn"]) / float(vals["frd"])
        for key in ("frame_rate", "framerate", "fps"):
            if key in vals and float(vals[key]) > 0:
                return float(vals[key])
    except (TypeError, ValueError):
        return None
    return None


def parse_rate(s: str) -> float | None:
    try:
        f = Fraction(s)
        return float(f) if f > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def ffprobe_fps(url, ua, cache, delay, tries=4):
    if url in cache:
        return cache[url]
    cmd = ["ffprobe", "-v", "error", "-user_agent", ua, "-select_streams", "v:0",
           "-show_entries", "stream=codec_name,width,height,r_frame_rate,avg_frame_rate",
           "-of", "json", url]
    for i in range(tries):
        time.sleep(delay)
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if p.returncode == 0:
            st = (json.loads(p.stdout).get("streams") or [{}])[0]
            avg, r = parse_rate(st.get("avg_frame_rate", "")), parse_rate(st.get("r_frame_rate", ""))
            fps = avg if avg and avg <= 240 else (r if r and r <= 240 else None)
            cache[url] = {"fps": fps, "codec": st.get("codec_name"), "w": st.get("width"), "h": st.get("height")}
            return cache[url]
        if "429" in p.stderr:
            wait = 15 * (i + 1)
            print(f"    файловый сервер просит подождать, жду {wait} с")
            time.sleep(wait)
            continue
        cache[url] = {"fps": None, "error": p.stderr.strip()[-200:]}
        return cache[url]
    return {"fps": None, "error": "429 после повторов"}


def main():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    cr = cfg["criteria"]
    WORK.mkdir(exist_ok=True)
    cands = json.loads((RAW / "candidates.json").read_text(encoding="utf-8"))
    print(f"Кандидатов: {len(cands)}")

    passed_a, rejected = [], []
    for rec in cands:
        reasons, norm = stage_a(rec, cr)
        if reasons:
            rejected.append({**norm, "stage": "A: метаданные", "reason": "; ".join(reasons)})
        else:
            passed_a.append(norm)
    print(f"Этап A (метаданные): прошло {len(passed_a)}, отсеяно {len(rejected)}")

    # Этап B: FPS. Метаданные потоков — через API пачками по 50.
    api = Commons(cfg["api"]["user_agent"], cfg["api"]["delay_s"])
    meta_cache_p = RAW / "stream_metadata.json"
    meta_cache = json.loads(meta_cache_p.read_text(encoding="utf-8")) if meta_cache_p.exists() else {}
    need = [r["title"] for r in passed_a if r["title"] not in meta_cache]
    for i in range(0, len(need), 50):
        data = api.get(action="query", titles="|".join(need[i:i + 50]), prop="videoinfo", viprop="metadata")
        for p in data["query"]["pages"]:
            if p.get("videoinfo"):
                meta_cache[p["title"]] = p["videoinfo"][0].get("metadata")
        print(f"  метаданные потоков: {min(i + 50, len(need))}/{len(need)}")
    meta_cache_p.write_text(json.dumps(meta_cache, ensure_ascii=False), encoding="utf-8")

    probe_cache_p = RAW / "ffprobe_cache.json"
    probe_cache = json.loads(probe_cache_p.read_text(encoding="utf-8")) if probe_cache_p.exists() else {}
    passed, n_meta, n_probe = [], 0, 0
    for r in passed_a:
        fps = fps_from_metadata(meta_cache.get(r["title"]))
        src = "метаданные потока"
        if fps and fps > 120:
            # у WebM без DefaultDuration библиотека Викисклада пишет 1000 или 30000 к/с —
            # это не настоящая частота, перепроверяем ffprobe
            fps = None
        if fps:
            n_meta += 1
        else:
            res = ffprobe_fps(r["file_url"], cfg["api"]["user_agent"], probe_cache, cfg["api"]["media_delay_s"])
            probe_cache_p.write_text(json.dumps(probe_cache, ensure_ascii=False), encoding="utf-8")
            fps, src = res.get("fps"), "ffprobe по ссылке"
            n_probe += 1
            print(f"  ffprobe {n_probe}: {r['title'][:60]} -> {fps}")
        r["fps"] = round(fps, 3) if fps else None
        r["fps_source"] = src
        if not fps:
            rejected.append({**r, "stage": "B: FPS", "reason": "FPS не удалось определить"})
        elif not (cr["fps_min"] - 0.5 <= fps <= cr["fps_max"] + 0.5):
            rejected.append({**r, "stage": "B: FPS", "reason": f"FPS вне {cr['fps_min']}–{cr['fps_max']} ({fps:.2f})"})
        else:
            passed.append(r)
    print(f"Этап B (FPS): FPS из метаданных {n_meta}, через ffprobe {n_probe}; прошло {len(passed)}")

    (WORK / "passed_check.json").write_text(json.dumps(passed, ensure_ascii=False, indent=1), encoding="utf-8")
    (WORK / "rejected_check.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Итого после тех. проверки: {len(passed)} из {len(cands)}")


if __name__ == "__main__":
    main()
