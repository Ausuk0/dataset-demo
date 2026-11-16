"""Шаг 4. Итоговая выборка и отчёт о качестве.

Выход (в папке output/):
  dataset.csv         — итоговая таблица метаданных (UTF-8 с BOM, разделитель запятая)
  rejected.csv        — что отсеяно и почему
  contact_sheet.jpg   — сетка превью из случайной выборки
  quality_report.md   — воронка, распределения, лицензии, список для ручной проверки
  summary.json        — те же цифры в машинном виде
"""
import csv
import json
import random
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent
RAW, WORK, OUT = ROOT / "raw", ROOT / "work", ROOT / "output"

COLUMNS = ["id", "title", "file_url", "page_url", "author", "license", "license_url",
           "duration_s", "width", "height", "fps", "size_mb", "category", "tags",
           "preview_frame", "attribution"]

TAG_SKIP = re.compile(
    r"(^CC[- ]|^PD|GFDL|License|licen[cs]e|Self-published|Uploaded|^Files? |^Media |Pages with|"
    r"supported by|Videos by |needing|Flickr|YouTube|Vimeo|^Translat|^Commons|template|"
    r"Quality|Valued|Featured|Video display resolution|^\d{3,4}p|WebM videos|Ogg|Theora|VP[89]|"
    r"Created with|Taken with|Uploaded with|^Videos of \d{4}|^\d{4} in |Copyright)", re.I)


def tags_from(categories: str, n=6):
    out = []
    for c in (categories or "").split("|"):
        c = c.strip()
        if c and not TAG_SKIP.search(c) and c not in out:
            out.append(c)
    return "; ".join(out[:n])


def lic_family(lic: str) -> str:
    u = lic.upper()
    if u.startswith("CC0"):
        return "CC0"
    if u.startswith("CC BY-SA"):
        return "CC BY-SA"
    if u.startswith("CC BY"):
        return "CC BY"
    return "Public Domain"


def reason_bucket(reason: str) -> str:
    r = reason.lower()
    for key, name in (("почти-дубль", "почти-дубль"), ("сверх максимума", "сверх максимума ТЗ"),
                      ("тематика", "тематика вне ТЗ"), ("лиценз", "лицензия"),
                      ("автор", "нет автора"), ("тип файла", "тип файла"),
                      ("короче", "длительность"), ("длиннее", "длительность"),
                      ("разрешение", "разрешение"), ("fps", "FPS"), ("кадр", "нет кадров")):
        if key in r:
            return name
    return "другое"


def bins(values, edges, fmt):
    c = Counter()
    for v in values:
        for lo, hi in zip(edges, edges[1:]):
            if lo <= v < hi or (hi == edges[-1] and v == hi):
                c[fmt(lo, hi)] += 1
                break
    return [(fmt(lo, hi), c[fmt(lo, hi)]) for lo, hi in zip(edges, edges[1:])]


def res_class(w, h):
    s = min(w, h)
    if h > w:
        return "вертикальное (от 720×1280)"
    if s >= 2160:
        return "4K (2160p+)"
    if s >= 1440:
        return "1440p"
    if s >= 1080:
        return "1080p"
    return "720p"


def fps_class(f):
    if f < 26:
        return "24–25"
    if f < 31:
        return "29,97–30"
    if f < 51:
        return "48–50"
    return "59,94–60"


def bar(n, total, width=24):
    k = round(width * n / total) if total else 0
    return "█" * k + "·" * (width - k)


def contact_sheet(recs, cols, rows, path, seed):
    rng = random.Random(seed)
    pick = rng.sample(recs, min(cols * rows, len(recs)))
    cw, ch, cap, pad = 320, 180, 22, 6
    W, H = cols * (cw + pad) + pad, rows * (ch + cap + pad) + pad
    sheet = Image.new("RGB", (W, H), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for i, r in enumerate(pick):
        x, y = pad + (i % cols) * (cw + pad), pad + (i // cols) * (ch + cap + pad)
        im = Image.open(OUT / r["preview_frame"]).convert("RGB")
        # вписываем в 16:9 с обрезкой по центру
        scale = max(cw / im.width, ch / im.height)
        im = im.resize((round(im.width * scale), round(im.height * scale)))
        l, t = (im.width - cw) // 2, (im.height - ch) // 2
        sheet.paste(im.crop((l, t, l + cw, t + ch)), (x, y))
        label = f"{r['id']}  {r['width']}x{r['height']} {r['fps']:g}fps {r['duration_s']:.0f}s"
        d.text((x + 2, y + ch + 4), label, fill=(235, 235, 235), font=font)
    sheet.save(path, quality=88)
    return [r["id"] for r in pick]


def main():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    pj, rp = cfg["project"], cfg["report"]
    OUT.mkdir(exist_ok=True)
    rng = random.Random(pj["seed"])

    n_cand = len(json.loads((RAW / "candidates.json").read_text(encoding="utf-8")))
    rej = json.loads((WORK / "rejected_check.json").read_text(encoding="utf-8"))
    n_rej_check = len(rej)
    n_passed_check = n_cand - n_rej_check
    rej_dedup = json.loads((WORK / "rejected_dedup.json").read_text(encoding="utf-8"))
    rej += rej_dedup
    kept = json.loads((WORK / "passed_dedup.json").read_text(encoding="utf-8"))
    n_after_dedup = len(kept)
    n_nodedup = sum(1 for r in rej_dedup if r["stage"] != "C: дедупликация")

    # Итоговая выборка: если записей больше максимума ТЗ — равномерно по темам
    final = kept
    if len(kept) > pj["target_max"]:
        by_theme = {}
        for r in sorted(kept, key=lambda r: r["pageid"]):
            by_theme.setdefault(r["theme"], []).append(r)
        for v in by_theme.values():
            rng.shuffle(v)
        final, i = [], 0
        while len(final) < pj["target_max"]:
            for v in by_theme.values():
                if i < len(v) and len(final) < pj["target_max"]:
                    final.append(v[i])
            i += 1
        chosen = {r["pageid"] for r in final}
        for r in kept:
            if r["pageid"] not in chosen:
                rej.append({**r, "stage": "D: лимит ТЗ",
                            "reason": f"сверх максимума ТЗ ({pj['target_max']}), не вошло в выборку"})

    final.sort(key=lambda r: (r["theme"], r["title"]))
    # превью оставляем только для записей итогового датасета
    keep_prev = {Path(r["preview_frame"]).name for r in final}
    for f in (OUT / "previews").glob("*.jpg"):
        if f.name not in keep_prev:
            f.unlink()
    rows = []
    for r in final:
        r["id"] = f"commons-{r['pageid']}"
        title = re.sub(r"^File:", "", r["title"])
        lic_url = r["license_url"] or r["page_url"]
        attribution = (f"«{re.sub(r'\.[a-z0-9]+$', '', title)}» — {r['author']}, {r['license']}, "
                       f"via Wikimedia Commons ({r['page_url']})")
        rows.append({"id": r["id"], "title": title, "file_url": r["file_url"], "page_url": r["page_url"],
                     "author": r["author"], "license": r["license"], "license_url": lic_url,
                     "duration_s": r["duration_s"], "width": r["width"], "height": r["height"],
                     "fps": r["fps"], "size_mb": r["size_mb"], "category": r["theme"],
                     "tags": tags_from(r["categories"]), "preview_frame": r["preview_frame"],
                     "attribution": attribution})

    with open(OUT / "dataset.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    rej.sort(key=lambda r: (r["stage"], r["title"]))
    with open(OUT / "rejected.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "page_url", "stage", "reason", "license", "duration_s", "width", "height", "fps"])
        for r in rej:
            w.writerow([f"commons-{r['pageid']}", re.sub(r"^File:", "", r["title"]), r["page_url"], r["stage"],
                        r["reason"], r["license"], r["duration_s"], r["width"], r["height"], r.get("fps", "")])

    sheet_ids = contact_sheet(final, rp["contact_sheet_cols"], rp["contact_sheet_rows"],
                              OUT / "contact_sheet.jpg", pj["seed"])

    # --- цифры для отчёта
    N = len(final)
    stage_counts = Counter(r["stage"] for r in rej)
    reason_counts = Counter()
    for r in rej:
        for part in r["reason"].split("; "):
            reason_counts[reason_bucket(part)] += 1
    first_reason = Counter(reason_bucket(r["reason"].split("; ")[0]) for r in rej if r["stage"].startswith("A"))
    dur_bins = bins([r["duration_s"] for r in final], [5, 10, 20, 30, 45, 60], lambda a, b: f"{a}–{b} с")
    res_c = Counter(res_class(r["width"], r["height"]) for r in final)
    fps_c = Counter(fps_class(r["fps"]) for r in final)
    theme_c = Counter(r["theme"] for r in final)
    lic_c = Counter(r["license"] for r in final)
    lic_f = Counter(lic_family(r["license"]) for r in final)
    fps_src = Counter(r.get("fps_source", "") for r in final)
    authors = len({r["author"] for r in final})
    total_gb = sum(r["size_mb"] for r in final) / 1024
    attr_ok = sum(1 for r in rows if r["author"] and r["license"] and r["page_url"])
    manual = rng.sample(rows, min(rp["manual_check_n"], N))

    summary = {
        "date": date.today().isoformat(),
        "funnel": {"candidates": n_cand, "passed_tech": n_passed_check,
                   "frames_ok": n_passed_check - n_nodedup, "after_dedup": n_after_dedup, "final": N},
        "rejected_by_stage": dict(stage_counts), "rejected_reasons": dict(reason_counts),
        "duration_bins": dur_bins, "resolution": dict(res_c), "fps": dict(fps_c),
        "themes": dict(theme_c), "licenses": dict(lic_c), "license_families": dict(lic_f),
        "authors": authors, "total_gb": round(total_gb, 2), "attribution_complete": attr_ok,
        "fps_source": dict(fps_src), "contact_sheet_ids": sheet_ids,
        "sample_rows": [rows[i] for i in sorted(rng.sample(range(N), min(8, N)))],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    def table(counter_items, total):
        lines = ["| Значение | Записей | Доля | |", "|---|---:|---:|---|"]
        for k, v in counter_items:
            lines.append(f"| {k} | {v} | {100 * v / total:.0f} % | `{bar(v, total)}` |")
        return "\n".join(lines)

    cr = cfg["criteria"]
    order_res = ["720p", "1080p", "1440p", "4K (2160p+)", "вертикальное (от 720×1280)"]
    order_fps = ["24–25", "29,97–30", "48–50", "59,94–60"]
    md = [f"# Отчёт о качестве: {pj['name']}", "",
          f"Дата сборки: {date.today().isoformat()}. Источник: Wikimedia Commons (официальный MediaWiki API).", "",
          "## Критерии ТЗ", "",
          f"- лицензия: {', '.join(a.strip() for a in cr['licenses_allowed'])} (NC/ND и fair use — нет);",
          f"- длительность {cr['duration_min_s']}–{cr['duration_max_s']} с;",
          f"- разрешение не ниже {cr['min_width']}×{cr['min_height']} (вертикальные — от {cr['min_height']}×{cr['min_width']});",
          f"- FPS {cr['fps_min']}–{cr['fps_max']};",
          f"- без дублей и почти-дублей (pHash по 3 кадрам, порог {cfg['dedup']['max_distance']});",
          f"- объём {pj['target_min']}–{pj['target_max']} записей; у каждой — автор и лицензия для атрибуции.", "",
          "## Воронка", "",
          "| Этап | Записей | Отсеяно |", "|---|---:|---:|",
          f"| Кандидатов собрано через API | {n_cand} | — |",
          f"| Прошли тех. и юр. критерии (A: метаданные, B: FPS) | {n_passed_check} | {n_rej_check} |",
          f"| Получены кадры для проверки (C) | {n_passed_check - n_nodedup} | {n_nodedup} |",
          f"| После удаления почти-дублей (C) | {n_after_dedup} | {stage_counts.get('C: дедупликация', 0)} |",
          f"| **В итоговом датасете** | **{N}** | {stage_counts.get('D: лимит ТЗ', 0)} (сверх лимита) |", "",
          f"Итог в рамках ТЗ ({pj['target_min']}–{pj['target_max']}): "
          f"**{'да' if pj['target_min'] <= N <= pj['target_max'] else 'НЕТ'}**.", "",
          "### Почему отсеяно (на этапе A у записи может быть несколько причин)", "",
          table(reason_counts.most_common(), sum(reason_counts.values())), "",
          "Полный список с причиной у каждой записи — `rejected.csv`.", "",
          "## Распределения в итоговом датасете", "",
          "### Длительность", "", table(dur_bins, N), "",
          "### Разрешение", "", table([(k, res_c[k]) for k in order_res if res_c[k]], N), "",
          "### Частота кадров", "", table([(k, fps_c[k]) for k in order_fps if fps_c[k]], N), "",
          "### Темы (категории)", "", table(theme_c.most_common(), N), "",
          f"Разных авторов: {authors}. Суммарный объём оригиналов: {total_gb:.1f}".replace(f"{total_gb:.1f}", f"{total_gb:.1f}".replace(".", ",")) + " ГБ "
          f"(в датасете — ссылки на файлы; скачивание по запросу).", "",
          "## Лицензии", "",
          table(lic_f.most_common(), N), "",
          "Подробно по версиям:", "",
          "| Лицензия | Записей |", "|---|---:|",
          *[f"| {k} | {v} |" for k, v in lic_c.most_common()], "",
          f"Атрибуция полная (автор + лицензия + ссылка на страницу) у {attr_ok} из {N} записей. "
          "Готовая строка атрибуции — колонка `attribution`. Для CC BY-SA производные работы "
          "распространяются на тех же условиях.", "",
          "## Как проверялось (каскад)", "",
          "1. **A — метаданные Викисклада, без обращения к файлу**: тип, лицензия (`LicenseShortName`), "
          "автор (`Artist`/`Credit`), длительность, ширина и высота.",
          "2. **B — частота кадров**: из заголовка видеопотока, который хранит Викисклад "
          f"({fps_src.get('метаданные потока', 0)} записей итога); если там нет — ffprobe по ссылке, "
          f"читает только начало файла ({fps_src.get('ffprobe по ссылке', 0)} записей итога).",
          "3. **C — почти-дубли**: 3 кадра на ролик (20/50/80 % длительности) в виде миниатюр 330 px, "
          "перцептивный хэш pHash, склейка групп, остаётся запись с лучшим разрешением.",
          "4. **D — ручная выборочная проверка** (ниже) и контактный лист `contact_sheet.jpg`.", "",
          f"## Выборочная ручная проверка ({len(manual)} случайных записей)", "",
          "Проверить человеком: открывается ли страница, совпадает ли лицензия и автор, "
          "соответствует ли содержание теме «город и транспорт», нет ли водяных знаков/титров на весь кадр.", "",
          "| # | id | Тема | Файл | Лицензия | Длит., с | Разрешение | FPS | OK? |",
          "|---:|---|---|---|---|---:|---|---:|---|",
          *[f"| {i} | [{r['id']}]({r['page_url']}) | {r['category']} | {r['title'][:60].replace('|', '/')} | "
            f"{r['license']} | {r['duration_s']:.0f} | {r['width']}×{r['height']} | {r['fps']:g} | ☐ |"
            for i, r in enumerate(manual, 1)], "",
          "## Что не проверяется автоматически", "",
          "- смысловое содержание кадра (что на ролике именно транспорт/город) — только по категориям "
          "Викисклада и выборочной ручной проверке;",
          "- корректность лицензии, заявленной загрузившим автором (берётся как указано на Викискладе);",
          "- наличие узнаваемых людей и номеров машин (права на изображение — отдельный вопрос, "
          "зависит от юрисдикции и задачи заказчика).", ""]
    (OUT / "quality_report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Кандидатов {n_cand} -> тех. критерии {n_passed_check} -> после дедупликации {n_after_dedup} -> итог {N}")
    print("Файлы: output/dataset.csv, rejected.csv, contact_sheet.jpg, quality_report.md, summary.json")


if __name__ == "__main__":
    main()
