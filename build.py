#!/usr/bin/env python3
"""개장 전 브리핑 - 뉴스 자동 수집기.

Google News RSS(무료·키 불필요)에서 한국/미국 증시 최신 헤드라인을 모아
data.json으로 저장한다. GitHub Actions에서 매일 실행되며, 표준 라이브러리만 사용.
"""
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))

FEEDS = {
    "kr": "코스피 증시 주식 when:1d",
    "us": "stock market wall street when:1d",
}
FEED_LOCALE = {
    "kr": ("ko", "KR", "KR:ko"),
    "us": ("en-US", "US", "US:en"),
}

# 제목 키워드 -> (칩 클래스, 칩 라벨)
KEYWORDS = {
    "kr": [
        (["실적", "영업이익", "어닝", "순이익", "적자", "흑자"], ("earn", "실적")),
        (["금리", "한은", "연준", "fomc", "인플레", "물가"], ("macro", "금리")),
        (["환율", "원달러", "원/달러", "달러", "외환"], ("fx", "환율")),
        (["외국인", "수급", "순매수", "순매도", "기관"], ("flow", "수급")),
        (["반도체", "삼성전자", "하이닉스", "2차전지", "바이오", "제약", "자동차"], ("sector", "업종")),
    ],
    "us": [
        (["earnings", "profit", "revenue", "guidance", "beats", "misses"], ("earn", "실적")),
        (["fed", "rate", "inflation", "fomc", "powell", "cpi", "jobs"], ("macro", "연준")),
        (["dollar", "yield", "treasury", "bond", "currency"], ("fx", "환율")),
        (["nvidia", "apple", "microsoft", "tesla", "amazon", "ai", "chip", "tech", "meta", "google"], ("earn", "빅테크")),
    ],
}
DEFAULT_CHIP = ("macro", "시황")
PER_MARKET = 6


def classify(title, market):
    low = title.lower()
    for words, chip in KEYWORDS[market]:
        for w in words:
            if w in low:
                return chip
    return DEFAULT_CHIP


def clean_title(title):
    # Google News는 "제목 - 언론사" 형태로 끝나는 경우가 있어 꼬리표 제거
    return re.sub(r"\s+-\s+[^-]+$", "", title).strip()


def to_kst(pubdate):
    try:
        dt = parsedate_to_datetime(pubdate).astimezone(KST)
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return ""


def fetch_market(market):
    lang, gl, ceid = FEED_LOCALE[market]
    q = urllib.parse.quote(FEEDS[market])
    url = f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={gl}&ceid={ceid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (BeforeTheBell bot)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    items = []
    seen = set()
    for it in root.iter("item"):
        title = clean_title((it.findtext("title") or "").strip())
        if not title or title in seen:
            continue
        seen.add(title)
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src_el = it.find("source")
        src = (src_el.text or "").strip() if src_el is not None else "Google News"
        chip, label = classify(title, market)
        items.append({
            "cat": chip,
            "catn": label,
            "t": title,
            "src": src,
            "url": link,
            "time": to_kst(pub),
        })
        if len(items) >= PER_MARKET:
            break
    return items


def main():
    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "markets": {},
    }
    for m in ("kr", "us"):
        try:
            news = fetch_market(m)
        except Exception as e:  # 실패해도 빌드는 계속 (다른 시장/폴백 유지)
            print(f"[warn] {m} fetch failed: {e}")
            news = []
        data["markets"][m] = {"news": news}
        print(f"[ok] {m}: {len(news)} items")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("wrote data.json")


if __name__ == "__main__":
    main()
