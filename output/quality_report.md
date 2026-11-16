# Отчёт о качестве: Город и транспорт — короткие видео

Дата сборки: 2026-11-17. Источник: Wikimedia Commons (официальный MediaWiki API).

## Критерии ТЗ

- лицензия: CC0, CC BY, CC BY-SA, Public domain, PD (NC/ND и fair use — нет);
- длительность 5–60 с;
- разрешение не ниже 1280×720 (вертикальные — от 720×1280);
- FPS 24–60;
- без дублей и почти-дублей (pHash по 3 кадрам, порог 10);
- объём 150–250 записей; у каждой — автор и лицензия для атрибуции.

## Воронка

| Этап | Записей | Отсеяно |
|---|---:|---:|
| Кандидатов собрано через API | 800 | — |
| Прошли тех. и юр. критерии (A: метаданные, B: FPS) | 271 | 529 |
| Получены кадры для проверки (C) | 271 | 0 |
| После удаления почти-дублей (C) | 270 | 1 |
| **В итоговом датасете** | **250** | 20 (сверх лимита) |

Итог в рамках ТЗ (150–250): **да**.

### Почему отсеяно (на этапе A у записи может быть несколько причин)

| Значение | Записей | Доля | |
|---|---:|---:|---|
| длительность | 376 | 53 % | `█████████████···········` |
| разрешение | 269 | 38 % | `█████████···············` |
| FPS | 21 | 3 % | `█·······················` |
| сверх максимума ТЗ | 20 | 3 % | `█·······················` |
| тематика вне ТЗ | 10 | 1 % | `························` |
| лицензия | 6 | 1 % | `························` |
| нет автора | 2 | 0 % | `························` |
| почти-дубль | 1 | 0 % | `························` |

Полный список с причиной у каждой записи — `rejected.csv`.

## Распределения в итоговом датасете

### Длительность

| Значение | Записей | Доля | |
|---|---:|---:|---|
| 5–10 с | 20 | 8 % | `██······················` |
| 10–20 с | 69 | 28 % | `███████·················` |
| 20–30 с | 67 | 27 % | `██████··················` |
| 30–45 с | 60 | 24 % | `██████··················` |
| 45–60 с | 34 | 14 % | `███·····················` |

### Разрешение

| Значение | Записей | Доля | |
|---|---:|---:|---|
| 720p | 60 | 24 % | `██████··················` |
| 1080p | 162 | 65 % | `████████████████········` |
| 1440p | 6 | 2 % | `█·······················` |
| 4K (2160p+) | 13 | 5 % | `█·······················` |
| вертикальное (от 720×1280) | 9 | 4 % | `█·······················` |

### Частота кадров

| Значение | Записей | Доля | |
|---|---:|---:|---|
| 24–25 | 85 | 34 % | `████████················` |
| 29,97–30 | 142 | 57 % | `██████████████··········` |
| 48–50 | 10 | 4 % | `█·······················` |
| 59,94–60 | 13 | 5 % | `█·······················` |

### Темы (категории)

| Значение | Записей | Доля | |
|---|---:|---:|---|
| Поезда | 68 | 27 % | `███████·················` |
| Метро | 49 | 20 % | `█████···················` |
| Трамваи | 43 | 17 % | `████····················` |
| Улицы и дорожное движение | 33 | 13 % | `███·····················` |
| Автобусы и троллейбусы | 32 | 13 % | `███·····················` |
| Город, таймлапс | 25 | 10 % | `██······················` |

Разных авторов: 150. Суммарный объём оригиналов: 9,4 ГБ (в датасете — ссылки на файлы; скачивание по запросу).

## Лицензии

| Значение | Записей | Доля | |
|---|---:|---:|---|
| CC BY-SA | 108 | 43 % | `██████████··············` |
| CC BY | 106 | 42 % | `██████████··············` |
| CC0 | 26 | 10 % | `██······················` |
| Public Domain | 10 | 4 % | `█·······················` |

Подробно по версиям:

| Лицензия | Записей |
|---|---:|
| CC BY-SA 4.0 | 77 |
| CC BY 3.0 | 54 |
| CC BY 4.0 | 38 |
| CC0 | 26 |
| CC BY-SA 3.0 | 23 |
| CC BY 2.0 | 14 |
| Public domain | 10 |
| CC BY-SA 2.0 | 7 |
| CC BY-SA 3.0 de | 1 |

Атрибуция полная (автор + лицензия + ссылка на страницу) у 250 из 250 записей. Готовая строка атрибуции — колонка `attribution`. Для CC BY-SA производные работы распространяются на тех же условиях.

## Как проверялось (каскад)

1. **A — метаданные Викисклада, без обращения к файлу**: тип, лицензия (`LicenseShortName`), автор (`Artist`/`Credit`), длительность, ширина и высота.
2. **B — частота кадров**: из заголовка видеопотока, который хранит Викисклад (243 записей итога); если там нет — ffprobe по ссылке, читает только начало файла (7 записей итога).
3. **C — почти-дубли**: 3 кадра на ролик (20/50/80 % длительности) в виде миниатюр 330 px, перцептивный хэш pHash, склейка групп, остаётся запись с лучшим разрешением.
4. **D — ручная выборочная проверка** (ниже) и контактный лист `contact_sheet.jpg`.

## Выборочная ручная проверка (25 случайных записей)

Проверить человеком: открывается ли страница, совпадает ли лицензия и автор, соответствует ли содержание теме «город и транспорт», нет ли водяных знаков/титров на весь кадр.

| # | id | Тема | Файл | Лицензия | Длит., с | Разрешение | FPS | OK? |
|---:|---|---|---|---|---:|---|---:|---|
| 1 | [commons-82201446](https://commons.wikimedia.org/wiki/File:Time_Lapse_video_of_a_3_hour_period_in_Silom_Bangkok_Thailand_by_Don_Ramey_Logan.webm) | Город, таймлапс | Time Lapse video of a 3 hour period in Silom Bangkok Thailan | CC BY-SA 4.0 | 41 | 3840×2160 | 29.97 | ☐ |
| 2 | [commons-178922966](https://commons.wikimedia.org/wiki/File:GO_Train_pulling_in_Guelph_Central_Station_in_Fall_2025.webm) | Поезда | GO Train pulling in Guelph Central Station in Fall 2025.webm | CC BY 4.0 | 30 | 1920×1080 | 29.667 | ☐ |
| 3 | [commons-67529770](https://commons.wikimedia.org/wiki/File:Amtrak_Cascasde_in_Puyallup_WA_2015-06_3.ogv) | Поезда | Amtrak Cascasde in Puyallup WA 2015-06 3.ogv | CC BY-SA 4.0 | 32 | 1280×720 | 29.97 | ☐ |
| 4 | [commons-37966653](https://commons.wikimedia.org/wiki/File:Brisbane_Hyperlapse_2013_(trimmed).ogv) | Город, таймлапс | Brisbane Hyperlapse 2013 (trimmed).ogv | CC BY 3.0 | 20 | 1280×720 | 30 | ☐ |
| 5 | [commons-97519578](https://commons.wikimedia.org/wiki/File:25T_passing_through_Tai_Po_Market_Station_201909211340.webm) | Поезда | 25T passing through Tai Po Market Station 201909211340.webm | CC BY-SA 4.0 | 23 | 1920×1080 | 29.97 | ☐ |
| 6 | [commons-98262254](https://commons.wikimedia.org/wiki/File:Sunset_timelapse_in_Funchal_-_2014.webm) | Город, таймлапс | Sunset timelapse in Funchal - 2014.webm | CC BY 3.0 | 53 | 1920×1080 | 29.97 | ☐ |
| 7 | [commons-27761741](https://commons.wikimedia.org/wiki/File:Lexington_Line_video_vc.ogv) | Метро | Lexington Line video vc.ogv | CC BY-SA 2.0 | 42 | 1280×720 | 29.97 | ☐ |
| 8 | [commons-78696794](https://commons.wikimedia.org/wiki/File:Arrival_of_Cascade_9745.ogv) | Поезда | Arrival of Cascade 9745.ogv | CC BY-SA 4.0 | 30 | 1280×720 | 25 | ☐ |
| 9 | [commons-66773932](https://commons.wikimedia.org/wiki/File:81-765_train_65025-026_arrives_Kievskaya_station.webm) | Метро | 81-765 train 65025-026 arrives Kievskaya station.webm | CC BY 3.0 | 53 | 1280×720 | 30 | ☐ |
| 10 | [commons-13111634](https://commons.wikimedia.org/wiki/File:Calle_Preciados_Madrid.ogv) | Улицы и дорожное движение | Calle Preciados Madrid.ogv | CC BY-SA 3.0 | 44 | 1280×720 | 24 | ☐ |
| 11 | [commons-182136789](https://commons.wikimedia.org/wiki/File:Galaktion_Bridge,_Tbilisi._17_January_2023.webm) | Улицы и дорожное движение | Galaktion Bridge, Tbilisi. 17 January 2023.webm | CC0 | 60 | 2592×1588 | 30 | ☐ |
| 12 | [commons-136571986](https://commons.wikimedia.org/wiki/File:Sandtoft-Bradford-trolleybus-746-long.webm) | Автобусы и троллейбусы | Sandtoft-Bradford-trolleybus-746-long.webm | CC BY-SA 4.0 | 53 | 1920×1080 | 30 | ☐ |
| 13 | [commons-179735290](https://commons.wikimedia.org/wiki/File:Amtrak_Cascades_Talgo_6_train_with_two_SC-44_loco%27s_going_thru_northbound.webm) | Поезда | Amtrak Cascades Talgo 6 train with two SC-44 loco's going th | CC BY 3.0 | 48 | 1280×720 | 30 | ☐ |
| 14 | [commons-62956701](https://commons.wikimedia.org/wiki/File:Tatra_T3_x_4_in_Kiev.webm) | Трамваи | Tatra T3 x 4 in Kiev.webm | CC BY 3.0 | 25 | 1280×720 | 30 | ☐ |
| 15 | [commons-14790802](https://commons.wikimedia.org/wiki/File:Berbera-cityscape-evening.ogv) | Улицы и дорожное движение | Berbera-cityscape-evening.ogv | CC0 | 47 | 1920×1080 | 29.97 | ☐ |
| 16 | [commons-19730113](https://commons.wikimedia.org/wiki/File:Ayalon_Freeway_Azriely_Towers_View_P1150162.ogv) | Улицы и дорожное движение | Ayalon Freeway Azriely Towers View P1150162.ogv | CC BY-SA 3.0 | 10 | 1280×720 | 30 | ☐ |
| 17 | [commons-147953193](https://commons.wikimedia.org/wiki/File:Go_Train_arriving_into_downtown_Toronto.webm) | Поезда | Go Train arriving into downtown Toronto.webm | CC BY 4.0 | 24 | 1920×1080 | 30 | ☐ |
| 18 | [commons-24404256](https://commons.wikimedia.org/wiki/File:Street_traffic.webm) | Автобусы и троллейбусы | Street traffic.webm | CC BY 3.0 | 35 | 1920×1080 | 30 | ☐ |
| 19 | [commons-46927644](https://commons.wikimedia.org/wiki/File:Leti%C5%A1t%C4%9B_Ruzyn%C4%9B,_autobusy_linky_AE_u_v%C3%BDjezdov%C3%A9_z%C3%A1vory.webm) | Автобусы и троллейбусы | Letiště Ruzyně, autobusy linky AE u výjezdové závory.webm | CC BY 4.0 | 23 | 1920×1080 | 25 | ☐ |
| 20 | [commons-36239312](https://commons.wikimedia.org/wiki/File:Toshiba_-_Formaci%C3%B3n_E.webm) | Поезда | Toshiba - Formación E.webm | CC0 | 40 | 1920×1080 | 60 | ☐ |
| 21 | [commons-131772094](https://commons.wikimedia.org/wiki/File:GO_Transit_engine_635_arriving_at_Brampton_Station,_9_October_2020.webm) | Поезда | GO Transit engine 635 arriving at Brampton Station, 9 Octobe | CC BY 4.0 | 23 | 1920×1080 | 29.97 | ☐ |
| 22 | [commons-41788898](https://commons.wikimedia.org/wiki/File:Zvona%C5%99ka,_tramvaje_linky_11_(01).webm) | Трамваи | Zvonařka, tramvaje linky 11 (01).webm | CC BY 4.0 | 16 | 1920×1080 | 25 | ☐ |
| 23 | [commons-56953298](https://commons.wikimedia.org/wiki/File:Arriva_London_LTZ1536_at_Hyde_Park_Corner,_London.webm) | Автобусы и троллейбусы | Arriva London LTZ1536 at Hyde Park Corner, London.webm | CC BY 2.0 | 8 | 1920×1080 | 25 | ☐ |
| 24 | [commons-139261481](https://commons.wikimedia.org/wiki/File:Stadtschleicher_in_G%C3%B6rlitz.webm) | Автобусы и троллейбусы | Stadtschleicher in Görlitz.webm | CC BY-SA 2.0 | 18 | 1920×1080 | 30 | ☐ |
| 25 | [commons-63385417](https://commons.wikimedia.org/wiki/File:MTV-82_VP-1_in_Kharkiv.webm) | Трамваи | MTV-82 VP-1 in Kharkiv.webm | CC BY 3.0 | 27 | 1280×720 | 30 | ☐ |

## Что не проверяется автоматически

- смысловое содержание кадра (что на ролике именно транспорт/город) — только по категориям Викисклада и выборочной ручной проверке;
- корректность лицензии, заявленной загрузившим автором (берётся как указано на Викискладе);
- наличие узнаваемых людей и номеров машин (права на изображение — отдельный вопрос, зависит от юрисдикции и задачи заказчика).
