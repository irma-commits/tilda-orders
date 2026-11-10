"""Проверяет RSS-ленты бирж и присылает в Telegram новые заказы по Тильде."""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEEDS = {
    "FL.ru": "https://www.fl.ru/rss/all.xml",
    "Freelancehunt": "https://freelancehunt.com/projects.rss",
}

# Слова, по которым отбираются заказы (без учета регистра)
KEYWORDS = re.compile(r"t[iy]lda|тиль?д|тільд|zero[\s-]?block|зеро[\s-]?блок", re.I)

SEEN_FILE = "seen.json"
SEEN_LIMIT = 3000
DRY_RUN = "--dry" in sys.argv


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (orders-rss-reader)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def item_id(link):
    # FL.ru: /projects/5528596/..., Freelancehunt: .../1663773.html
    m = re.search(r"/projects?/(\d+)", link) or re.search(r"/(\d+)\.html", link)
    return m.group(1) if m else link.split("?")[0]


def send(text):
    token = os.environ["TG_TOKEN"]
    chat = os.environ["TG_CHAT_ID"]
    data = urllib.parse.urlencode({
        "chat_id": chat, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=30)


def main():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            seen = json.load(f)
    except FileNotFoundError:
        seen = []
    seen_set = set(seen)

    found = 0
    for source, url in FEEDS.items():
        try:
            root = ET.fromstring(fetch(url))
        except Exception as e:
            print(f"{source}: ошибка загрузки: {e}")
            continue
        for item in reversed(root.findall("./channel/item")):
            link = (item.findtext("link") or "").strip()
            key = f"{source}:{item_id(link)}"
            if key in seen_set:
                continue
            seen.append(key)
            seen_set.add(key)
            title = clean(item.findtext("title"))
            desc = clean(item.findtext("description"))
            if not KEYWORDS.search(title + " " + desc):
                continue
            found += 1
            short = desc[:600] + ("…" if len(desc) > 600 else "")
            msg = (f"<b>{html.escape(title)}</b>\n<i>{source}</i>\n\n"
                   f"{html.escape(short)}\n\n<a href=\"{html.escape(link)}\">Открыть заказ</a>")
            if DRY_RUN:
                print("---\n" + msg)
            else:
                send(msg)

    print(f"Новых заказов по Тильде: {found}")
    if not DRY_RUN:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(seen[-SEEN_LIMIT:], f, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
