from google import genai
from google.genai import types
import json
import os
import re
from scraper import scrape_company_info
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_PROMPT = """あなたはIndeedの求人票作成の専門家です。企業情報と採用担当者からの依頼文をもとに、求職者にとって魅力的な求人票を作成してください。

【作成ガイドライン】
1. 求職者目線で魅力的なポイントを具体的に強調する
2. 数字・実績・具体例を使って信頼性と訴求力を高める
3. 職場の雰囲気・社風・カルチャーが伝わるよう記述する
4. キャリアアップ・成長機会を明確に示す
5. 仕事内容は「何をするのか」だけでなく「なぜやりがいがあるか」まで記述する
6. 応募資格は「必須」と「歓迎」を明確に分けて書く
7. 読みやすいよう適切に改行・箇条書きを使う

【出力形式】
必ず以下のJSON形式のみで出力してください（前後に説明文・コードブロック記号は不要）:
{
    "company_name": "会社名",
    "job_title": "求人タイトル（具体的で魅力的なもの、30文字以内推奨）",
    "prefecture": "都道府県名（例：東京都）",
    "city": "市区町村名（例：渋谷区）",
    "employment_type": "雇用形態（正社員/契約社員/パート・アルバイト/派遣社員/業務委託 のいずれか）",
    "salary_min": 最低給与の数値（月給なら円、時給なら円。不明な場合はnull）,
    "salary_max": 最高給与の数値（月給なら円、時給なら円。不明な場合はnull）,
    "salary_type": "給与単位（月給/時給/年収 のいずれか）",
    "description": "仕事内容（詳細に、改行や箇条書きを活用して400文字以上）",
    "requirements": "応募資格・必須条件（箇条書きで具体的に）",
    "preferred_skills": "歓迎スキル・経験（箇条書き。なければ空文字）",
    "working_hours": "勤務時間（例：9:00〜18:00（実働8時間））",
    "holidays": "休日・休暇（例：完全週休2日制（土日祝）、年間休日125日など）",
    "benefits": "待遇・福利厚生（交通費・社会保険・各種手当など、箇条書き）",
    "selection_process": "選考プロセス（例：書類選考 → 一次面接 → 最終面接）",
    "appeal_points": ["アピールポイント1（短く印象的に）", "アピールポイント2", "アピールポイント3"]
}"""


def generate_job_posting(
    company_url: str,
    request_text: str,
    application_url: str = "",
    contact_name: str = "",
    contact_phone: str = "",
    contact_email: str = "",
) -> dict:
    company_info = scrape_company_info(company_url)
    scrape_status = "取得成功" if company_info["success"] else f"取得失敗（{company_info.get('error', '不明')}）"

    user_content = f"""## 企業サイトURL
{company_url}

## 企業サイト情報（スクレイピング結果: {scrape_status}）
【サイトタイトル】{company_info.get('title', 'N/A')}
【概要・説明】{company_info.get('meta_description', 'N/A')}
【サイトコンテンツ】
{company_info.get('content', '取得できませんでした') or '取得できませんでした'}

## 採用担当者からの依頼文
{request_text}

## 追加情報
応募先URL: {application_url or '未入力'}
担当者名: {contact_name or '未入力'}
担当者電話番号: {contact_phone or '未入力'}
担当者メールアドレス: {contact_email or '未入力'}

上記の情報をもとに、求職者にとって最大限魅力的な求人票をJSON形式で作成してください。
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=4096,
            temperature=0.7,
        ),
    )
    content = response.text

    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```\s*", "", content)

    json_match = re.search(r"\{[\s\S]*\}", content)
    if not json_match:
        raise ValueError(f"AIからの応答でJSONが見つかりませんでした。応答: {content[:200]}")

    result = json.loads(json_match.group())

    result["company_url"] = company_url
    result["application_url"] = application_url
    result["contact_name"] = contact_name
    result["contact_phone"] = contact_phone
    result["contact_email"] = contact_email
    result["original_request"] = request_text

    if isinstance(result.get("appeal_points"), list):
        result["appeal_points"] = json.dumps(result["appeal_points"], ensure_ascii=False)

    return result
