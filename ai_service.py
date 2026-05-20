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

# 会社名候補をサイトタイトル・メタから抽出するパターン
_CORP_SUFFIXES = re.compile(
    r'(株式会社|有限会社|合同会社|社団法人|財団法人|グループ|ホールディングス|HD|Holdings|Group|Co\.,?\s*Ltd\.?|Corporation|Corp\.?|Inc\.?)'
)


def _extract_company_names(company_info: dict) -> list[str]:
    """スクレイピング結果から社名候補を抽出する。"""
    candidates = set()
    for key in ('title', 'meta_description'):
        text = company_info.get(key, '') or ''
        # 法人格・グループ名の前後を含む単語を抽出
        for m in _CORP_SUFFIXES.finditer(text):
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 10)
            chunk = text[start:end].strip()
            # 句読点・記号で区切って短いフラグメントを候補にする
            for part in re.split(r'[\s｜|/・\-「」【】（）()　]', chunk):
                part = part.strip()
                if len(part) >= 3:
                    candidates.add(part)
    return list(candidates)


def _scrub_client_name(result: dict, company_info: dict, haken_company_name: str) -> None:
    """生成結果から派遣先社名を除去し、業種表現に置き換える（保険処理）。"""
    names = _extract_company_names(company_info)
    if not names:
        return

    text_fields = ['job_title', 'description', 'requirements', 'preferred_skills',
                   'working_hours', 'holidays', 'benefits', 'selection_process']
    replacement = '就業先企業'

    for field in text_fields:
        val = result.get(field)
        if not isinstance(val, str):
            continue
        for name in names:
            if name and name in val:
                val = val.replace(name, replacement)
        result[field] = val

    # appeal_points はリスト or JSON文字列
    ap = result.get('appeal_points')
    if isinstance(ap, list):
        result['appeal_points'] = [
            _replace_names(item, names, replacement) for item in ap
        ]
    elif isinstance(ap, str):
        for name in names:
            if name:
                ap = ap.replace(name, replacement)
        result['appeal_points'] = ap

    # company_name は派遣元名で上書き
    if haken_company_name:
        result['company_name'] = haken_company_name


def _replace_names(text: str, names: list[str], replacement: str) -> str:
    for name in names:
        if name:
            text = text.replace(name, replacement)
    return text


def generate_job_posting(
    company_url: str,
    request_text: str,
    recruitment_url: str = "",
    application_url: str = "",
    contact_name: str = "",
    contact_phone: str = "",
    contact_email: str = "",
    target_persona: str = "",
    employment_type: str = "",
    haken_company_name: str = "",
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

    if employment_type == "派遣社員":
        haken_name_instruction = f'company_name には必ず派遣元会社名「{haken_company_name}」を使用してください。' if haken_company_name else "company_name には派遣元（登録先）会社名を使用してください。"
        site_title = company_info.get('title', '')
        avoid_hint = f'特に「{site_title}」に含まれる企業名・グループ名・ブランド名は一切使用禁止です。' if site_title else ''
        haken_section = f"""
## 【派遣求人・絶対厳守ルール】
この求人は「派遣社員」の求人です。就業先（派遣先）企業の名称は求人票に一切掲載できません。

━━ 禁止事項（違反したら求人票として使えません） ━━
・job_title、description、requirements、preferred_skills、working_hours、holidays、benefits、selection_process、appeal_points — 全フィールドに派遣先の社名・グループ名・略称・ブランド名を書かないこと
・{avoid_hint}
・「当社」「弊社」という表現も、文脈上派遣先を指す場合は使用禁止

━━ 代わりに使う表現（業種＋規模感で表現する） ━━
良い例：「大手自動車メーカー」「東証プライム上場の食品メーカー」「都内の有名ホテル」「年商1,000億超の商社」「全国展開の大手小売チェーン」「業界トップクラスのIT企業」
NG例：スクレイピングで取得した実際の社名・グループ名・ブランド名をそのまま使う

━━ company_name フィールドの扱い ━━
{haken_name_instruction}

━━ description の書き方 ━━
・冒頭で「大手〇〇企業での就業チャンス！」のように業種・規模を強調する
・職場環境・業務内容・魅力は具体的に書いてよい（社名だけ伏せる）
・「安定した大手企業でじっくり長期就業できます」「ネームバリューある職場でスキルを磨けます」などの訴求を入れる

━━ 出力前の最終チェック ━━
出力するJSON全体を見直し、派遣先の社名・グループ名が含まれていたら必ず業種表現に置き換えてから出力すること。
"""
    else:
        haken_section = f"\n## 雇用形態\n{employment_type}\n" if employment_type else ""

    user_content = f"""## 企業サイトURL
{company_url}

## 企業サイト情報（スクレイピング結果: {scrape_status}）
【サイトタイトル】{company_info.get('title', 'N/A')}
【概要・説明】{company_info.get('meta_description', 'N/A')}
【サイトコンテンツ】
{company_info.get('content', '取得できませんでした') or '取得できませんでした'}
{recruitment_section}{haken_section}
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

    # 派遣求人：後処理で派遣先社名を除去（AIが指示に従わなかった場合の保険）
    if employment_type == "派遣社員":
        _scrub_client_name(result, company_info, haken_company_name)

    result["company_url"] = company_url
    result["application_url"] = application_url
    result["contact_name"] = contact_name
    result["contact_phone"] = contact_phone
    result["contact_email"] = contact_email
    result["original_request"] = request_text

    if isinstance(result.get("appeal_points"), list):
        result["appeal_points"] = json.dumps(result["appeal_points"], ensure_ascii=False)

    return result
