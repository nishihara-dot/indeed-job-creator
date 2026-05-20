from groq import Groq
import json
import os
import re
from scraper import scrape_company_info
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """あなたはIndeed Japan専門の求人票コピーライターです。企業情報と採用担当者からの依頼文をもとに、求職者が思わずクリックして応募したくなる求人票を作成してください。

【求人タイトルの作り方】
- 30文字以内で最大の訴求力を出すことが最重要
- 給与・待遇の具体的な数字を入れる（例：「月収35万〜」「時給1,500円〜」）
- 働きやすさのキーワードを入れる（例：「週休2日」「残業ほぼなし」「リモートOK」「服装自由」）
- 対象者を明確にする（例：「未経験歓迎」「主婦活躍中」「シニア歓迎」「第二新卒OK」）
- 職種名だけで終わらせない（悪い例：「営業職」→ 良い例：「未経験OK◎年休125日の営業職」）
- 記号（◎◆★▶）を1〜2個使って視覚的に目立たせる

【仕事内容の書き方】
- 冒頭1〜2行で求職者の心をつかむ「フック」を入れる（なぜこの仕事が魅力的か・どんな人が向いているかを一言で）
- 「1日の仕事の流れ」や「具体的な業務例」を箇条書きで示す
- 数字・固有名詞を使って具体性を出す（顧客数・売上規模・チーム人数・実績など）
- 「入社後のキャリアパス」「成長できる環境」を必ず明記する
- 400文字以上で記述する

【応募資格の書き方】
- 【必須】と【歓迎】を明確に分ける
- 必須条件はできるだけ絞り込み、応募ハードルを下げる
- 「〜の意欲がある方」「〜が好きな方」など人柄・志向性も含める

【待遇・福利厚生の書き方】
- 交通費・社会保険・有給・各種手当を具体的な金額や日数で記載
- 「研修制度あり」「資格取得支援」「産休・育休取得実績あり」など働きやすさのエビデンスを入れる
- 箇条書きで見やすく

【アピールポイントの書き方】
- 3〜5個、各15〜25文字程度
- 求職者が「ここで働きたい」と思う一番の理由を短く力強く表現する
- 数字・具体性・感情に訴える言葉を使う（例：「年休125日で趣味も充実」「未経験から1年で店長に」）

【文体・表現のルール】
- 語尾は「〜です」「〜ます」調で統一
- 専門用語は使わず、誰でも読める言葉で書く
- 改行・箇条書きを積極活用して読みやすくする
- ネガティブな表現は使わない（「残業あり」→「業務量に応じて残業あり、手当全額支給」）

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
    recruitment_url: str = "",
    application_url: str = "",
    contact_name: str = "",
    contact_phone: str = "",
    contact_email: str = "",
    target_persona: str = "",
) -> dict:
    company_info = scrape_company_info(company_url)
    scrape_status = "取得成功" if company_info["success"] else f"取得失敗（{company_info.get('error', '不明')}）"

    recruitment_section = ""
    if recruitment_url and recruitment_url.startswith("http"):
        rec_info = scrape_company_info(recruitment_url)
        rec_status = "取得成功" if rec_info["success"] else f"取得失敗（{rec_info.get('error', '不明')}）"
        recruitment_section = f"""
## 採用ページURL
{recruitment_url}

## 採用ページ情報（スクレイピング結果: {rec_status}）
【ページタイトル】{rec_info.get('title', 'N/A')}
【概要・説明】{rec_info.get('meta_description', 'N/A')}
【採用ページコンテンツ】
{rec_info.get('content', '取得できませんでした') or '取得できませんでした'}

※採用ページに記載の給与・勤務地・仕事内容・応募資格などの具体的な数値や条件を優先して使用してください。
"""

    persona_section = f"""
## ターゲット層（ペルソナ）
{target_persona}

このペルソナが「自分のための求人だ」と感じるよう、以下を意識してください：
- タイトル・キャッチコピーにペルソナに刺さるキーワードを入れる
- 仕事内容・アピールポイントの言葉遣いをペルソナに合わせる
- 応募資格の必須条件をペルソナが満たしやすい書き方にする
- ペルソナが重視する条件（時間・給与・環境など）を前面に出す
""" if target_persona else ""

    user_content = f"""## 企業サイトURL
{company_url}

## 企業サイト情報（スクレイピング結果: {scrape_status}）
【サイトタイトル】{company_info.get('title', 'N/A')}
【概要・説明】{company_info.get('meta_description', 'N/A')}
【サイトコンテンツ】
{company_info.get('content', '取得できませんでした') or '取得できませんでした'}
{recruitment_section}
## 採用担当者からの依頼文
{request_text}
{persona_section}
## 追加情報
応募先URL: {application_url or '未入力'}
担当者名: {contact_name or '未入力'}
担当者電話番号: {contact_phone or '未入力'}
担当者メールアドレス: {contact_email or '未入力'}

上記の情報をもとに、求職者にとって最大限魅力的な求人票をJSON形式で作成してください。
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=4096,
        temperature=0.7,
    )
    content = response.choices[0].message.content

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
