"""Шаг 1. Сбор кандидатов с Викисклада (Wikimedia Commons) через официальный API.

Обходит категории из config.yaml (с подкатегориями до заданной глубины),
отбирает видеофайлы, затем пачками по 50 запрашивает их технические данные
и лицензию (videoinfo + extmetadata). Результат: raw/candidates.json.

Запуск: .venv\\Scripts\\python.exe collect.py
"""
import json
import random
import sys
import time
from pathlib import Path

import yaml

from commons import Commons

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
VIDEO_EXT = (".webm", ".ogv", ".ogg", ".mpg", ".mpeg")
EXTMETA_FIELDS = ("LicenseShortName|LicenseUrl|License|UsageTerms|AttributionRequired|Copyrighted|"
                  "Artist|Credit|ImageDescription|ObjectName|Categories|DateTimeOriginal")


def load_config():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def excluded(name: str, words) -> bool:
    low = name.lower()
    return any(w.lower() in low for w in words)


def walk_theme(api: Commons, seeds, exclude_words, max_cats=80):
    """Обход категорий темы в ширину. Возвращает {название файла: категория-источник}."""
    files, seen, walked = {}, set(), []
    queue = [(s["category"], s.get("depth", 0)) for s in seeds]
    while queue and len(walked) < max_cats:
        cat, depth = queue.pop(0)
        if cat in seen:
            continue
        seen.add(cat)
        walked.append(cat)
        n_files = 0
        for data in api.query_all(list="categorymembers", cmtitle="Category:" + cat,
                                  cmtype="file|subcat", cmlimit=500):
            for m in data["query"]["categorymembers"]:
                title = m["title"]
                if m["ns"] == 14:
                    sub = title.split(":", 1)[1]
                    if depth > 0 and not excluded(sub, exclude_words):
                        queue.append((sub, depth - 1))
                elif m["ns"] == 6 and title.lower().endswith(VIDEO_EXT):
                    files.setdefault(title, cat)
                    n_files += 1
        print(f"    {cat}: видео {n_files}, всего по теме {len(files)}")
    return files, walked


def fetch_info(api: Commons, titles):
    """Технические данные и лицензия пачками по 50 файлов."""
    out = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        data = api.get(action="query", titles="|".join(chunk), prop="videoinfo",
                       viprop="url|size|mime|mediatype|extmetadata|sha1|derivatives|timestamp",
                       viextmetadatafilter=EXTMETA_FIELDS, viextmetadatalanguage="en")
        for p in data["query"]["pages"]:
            if p.get("missing") or not p.get("videoinfo"):
                continue
            out[p["title"]] = p
        print(f"  данные файлов: {min(i + 50, len(titles))}/{len(titles)}")
    return out


def main():
    cfg = load_config()
    c = cfg["collect"]
    api = Commons(cfg["api"]["user_agent"], cfg["api"]["delay_s"])
    rng = random.Random(cfg["project"]["seed"])
    RAW.mkdir(exist_ok=True)
    t0 = time.time()

    chosen, walked_all = {}, {}
    for theme, seeds in c["themes"].items():
        print(f"Тема «{theme}»")
        files, walked = walk_theme(api, seeds, c["exclude_category_words"])
        walked_all[theme] = walked
        titles = sorted(t for t in files if t not in chosen)
        rng.shuffle(titles)                       # случайная, но воспроизводимая выборка
        for t in titles[:c["per_theme_max"]]:
            chosen[t] = {"theme": theme, "source_category": files[t]}
        print(f"  взято кандидатов: {min(len(titles), c['per_theme_max'])} из {len(titles)}")

    titles = list(chosen)
    if len(titles) > c["max_candidates"]:
        rng.shuffle(titles)
        titles = titles[:c["max_candidates"]]
    print(f"Кандидатов к запросу данных: {len(titles)}")

    info = fetch_info(api, titles)
    candidates = []
    for t in titles:
        if t not in info:
            continue
        p = info[t]
        rec = {"pageid": p["pageid"], "title": t, **chosen[t], "videoinfo": p["videoinfo"][0]}
        cats = rec["videoinfo"].get("extmetadata", {}).get("Categories", {}).get("value", "")
        if excluded(cats, c["exclude_category_words"]):
            rec["excluded_by_category"] = True
        candidates.append(rec)

    (RAW / "candidates.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=1), encoding="utf-8")
    (RAW / "categories_walked.json").write_text(json.dumps(walked_all, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Готово: {len(candidates)} кандидатов -> raw/candidates.json "
          f"({api.requests_made} запросов к API, {time.time() - t0:.0f} с)")


if __name__ == "__main__":
    main()
