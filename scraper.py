import re
import requests
from bs4 import BeautifulSoup

# 「株式会社○○」「○○株式会社」等の社名を拾うパターン
_COMPANY_RE = re.compile(
    r'(?:[\wぁ-んァ-ヶ一-龥ー＆&・]{1,25}(?:株式会社|有限会社|合同会社|合資会社|一般社団法人|一般財団法人)'
    r'|(?:株式会社|有限会社|合同会社|合資会社|一般社団法人|一般財団法人)[\wぁ-んァ-ヶ一-龥ー＆&・]{1,25})'
)


def _extract_company_hint(soup) -> str:
    """フッター削除前のsoupから、正式な会社名の候補を1つ抽出する。
    優先度: コピーライト表記 > フッター内の社名 > og:site_name。"""
    # 1. コピーライト表記（© / Copyright ... 株式会社○○）は最も信頼できる
    body_text = soup.get_text(separator=" ", strip=True)
    for m in re.finditer(r'(?:©|Copyright|COPYRIGHT|\(c\)|Ⓒ)[^\n。]{0,80}', body_text):
        cm = _COMPANY_RE.search(m.group())
        if cm:
            return cm.group().strip()

    # 2. フッター内の社名
    footer = soup.find("footer")
    if footer:
        cm = _COMPANY_RE.search(footer.get_text(separator=" ", strip=True))
        if cm:
            return cm.group().strip()

    # 3. og:site_name（法人格を含む場合のみ社名として採用）
    site_name = soup.find("meta", attrs={"property": "og:site_name"})
    if site_name and site_name.get("content"):
        c = site_name["content"].strip()
        if _COMPANY_RE.search(c):
            return _COMPANY_RE.search(c).group().strip()

    # 4. ページ全体から最初に見つかる社名（最後の手段）
    cm = _COMPANY_RE.search(body_text)
    return cm.group().strip() if cm else ""


def scrape_company_info(url: str) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        meta_desc = ""
        meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", attrs={"property": "og:description"}
        )
        if meta:
            meta_desc = meta.get("content", "")

        # 社名ヒントはフッター（コピーライト）を含む状態で抽出しておく
        company_name_hint = _extract_company_hint(soup)

        # 本文抽出のため不要要素を除去
        for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
            tag.decompose()

        # Try to get main content from semantic elements first
        main_text = ""
        for selector in ["main", "article", "#about", ".about", "#company", ".company-info"]:
            elem = soup.select_one(selector)
            if elem:
                main_text = elem.get_text(separator="\n", strip=True)[:4000]
                break

        if not main_text and soup.body:
            main_text = soup.body.get_text(separator="\n", strip=True)[:4000]

        return {
            "title": title,
            "meta_description": meta_desc,
            "content": main_text,
            "company_name_hint": company_name_hint,
            "url": url,
            "success": True,
        }
    except Exception as e:
        return {
            "title": "",
            "meta_description": "",
            "content": "",
            "company_name_hint": "",
            "url": url,
            "success": False,
            "error": str(e),
        }
