from anthropic import Anthropic
import json
import os
import re
from scraper import scrape_company_info
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """あなたはIndeed Japanで年間10万件以上の求人票を手がけてきたトップクラスの求人コピーライターです。クリック率・応募率を最大化する求人票を作成してください。

━━━━━━━━━━━━━━━━━━━━
【最優先】求人タイトルの作り方
━━━━━━━━━━━━━━━━━━━━
タイトルは応募数を決定する最重要要素です。以下を厳守してください。

■ 絶対NGのタイトル（これを出力したら失敗）
❌「営業スタッフ募集」→ 何も伝わらない
❌「一般事務 正社員」→ どこにでもある
❌「〇〇株式会社 ドライバー」→ 会社名は不要
❌「経験者歓迎 ITエンジニア」→ 弱い・ありきたり
❌「介護職 パート」→ 職種と雇用形態だけ

■ 高応募率タイトルの公式（この型に当てはめる）
型A：[ターゲット]OK◎ [給与/待遇の数字] [職種]
　例：未経験OK◎月収28万〜 カスタマーサポート

型B：[職種]★[最大の魅力] [ターゲット]歓迎
　例：調剤薬局事務★残業ほぼなし 主婦・Wワーク歓迎

型C：[数字で表した魅力]◆[職種]（[ターゲット]活躍中）
　例：年休125日◆法人営業（第二新卒・異業種から活躍中）

型D：[働き方の特徴]！[職種]/[ターゲット]も安心
　例：週3〜OK！販売スタッフ/扶養内・Wワークも安心

型E：[職種] [数字の魅力]+[ターゲットに刺さるワード]
　例：保育士 月給25万〜＋賞与3ヶ月 残業月10h以下

■ タイトルに必ず1つ以上入れる要素
・数字（月収・時給・年休・残業時間・賞与月数など）
・ターゲット層（未経験OK/主婦歓迎/シニア活躍/週3〜/扶養内OKなど）
・記号（◎◆★♪▶ のいずれか1〜2個）

■ペルソナが設定されている場合のタイトル調整
・主婦・ブランク→「時短OK」「扶養内OK」「週3〜」「ブランク歓迎」を入れる
・シニア・ミドル→「50代活躍中」「経験者優遇」「長期歓迎」を入れる
・未経験・新卒→「未経験OK」「研修充実」「第二新卒歓迎」を入れる
・キャリアアップ重視→「月収〇〇万〜」「リーダー候補」「スキルアップ支援」を入れる

━━━━━━━━━━━━━━━━━━━━
【仕事内容の書き方】
━━━━━━━━━━━━━━━━━━━━
- 冒頭1〜2文：「〜が好きな人にピッタリの仕事です」「〜を通じて社会に貢献できます」など感情に響くフックから始める
- 具体的な1日の流れ・業務例を箇条書きで記載
- 数字・規模感を入れる（担当顧客数・チーム人数・売上規模など）
- キャリアパス・成長機会を必ず書く
- 400文字以上で記述する

━━━━━━━━━━━━━━━━━━━━
【応募資格】
━━━━━━━━━━━━━━━━━━━━
- 【必須】と【歓迎】を明確に分ける
- 必須条件は最小限に絞り込み、応募ハードルを下げる
- 「〜に興味がある方」「〜が好きな方」など人柄・マインドも入れる

━━━━━━━━━━━━━━━━━━━━
【待遇・福利厚生】
━━━━━━━━━━━━━━━━━━━━
- 交通費・社会保険・各種手当を具体的な金額や日数で記載
- 「産休・育休取得実績あり」「資格取得費用全額支援」などエビデンスを入れる
- 箇条書きで見やすく

━━━━━━━━━━━━━━━━━━━━
【アピールポイント（キャッチコピー）】
━━━━━━━━━━━━━━━━━━━━
- 3〜5個、各20文字以内で力強く
- ❌「働きやすい環境です」→ ✅「残業月平均8hで趣味も充実」
- ❌「成長できます」→ ✅「未経験から最短6ヶ月でリーダーに」
- ❌「福利厚生充実」→ ✅「育休取得率100%・時短勤務OK」
- 数字・具体的事実・感情ワードを組み合わせる

━━━━━━━━━━━━━━━━━━━━
【文体ルール】
━━━━━━━━━━━━━━━━━━━━
- 語尾は「です・ます」調で統一
- 改行・箇条書きを積極活用
- ネガティブ表現は言い換える（「残業あり」→「残業手当全額支給、月平均〇〇h」）

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

【重要な指示】
上記の情報をもとにJSON形式で求人票を作成してください。

特に job_title（求人タイトル）は最も重要です。
システムプロンプトの「高応募率タイトルの公式」の型A〜Eのいずれかを必ず使用し、
数字・ターゲットワード・記号を含む、思わずクリックしたくなるタイトルにしてください。
「〇〇募集」「〇〇スタッフ」だけの凡庸なタイトルは絶対に避けてください。
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_content},
        ],
    )
    content = response.content[0].text

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
