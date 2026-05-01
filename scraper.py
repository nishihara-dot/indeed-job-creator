import requests
from bs4 import BeautifulSoup


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

        for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        meta_desc = ""
        meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", attrs={"property": "og:description"}
        )
        if meta:
            meta_desc = meta.get("content", "")

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
            "url": url,
            "success": True,
        }
    except Exception as e:
        return {
            "title": "",
            "meta_description": "",
            "content": "",
            "url": url,
            "success": False,
            "error": str(e),
        }
