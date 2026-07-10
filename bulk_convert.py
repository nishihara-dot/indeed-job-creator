"""
Jobbudyの求人一覧Excel（【求人一覧】○○○○（全求人）.xlsx等）を
Indeed一括アップロード用テンプレート形式に変換するモジュール。

- 変換ロジックは既存の indeed_converter_fixed.py を踏襲
- ディスクに書かず、メモリ上で (ファイル名, bytes) のリストを返す
- Indeedの上限に合わせて chunk_size 件（既定999）ごとに分割
"""
import io
import re
from pathlib import Path

# pandas/openpyxl は重量級のため、未導入環境でもアプリ本体が起動できるよう遅延インポート。
# 変換実行時にのみ必要。未導入なら convert_jobbudy_to_indeed() 呼び出し時に明示エラーを返す。
try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

BASE_DIR = Path(__file__).parent
TEMPLATE_PATH = BASE_DIR / "indeed_template.xlsx"
CHUNK_SIZE = 999

# 職業紹介事業者（自社）情報 — 募集要項（その他）に付与する定型文
AGENCY_NAME = "株式会社コノ街デザイン"
AGENCY_ADDRESS = "沖縄県豊見城市字豊崎3-59"
BRAND_LINE = "【ブランド名】 コノ街お仕事カフェ　:　https://konomachi-cafe.jp/"
DEFAULT_APPLY_EMAIL = "nishihara@toyopla.jp"

# 都道府県のみ指定時に補完する県庁所在地
_CITY_MAP = {
    "北海道": "札幌市", "青森県": "青森市", "岩手県": "盛岡市", "宮城県": "仙台市",
    "秋田県": "秋田市", "山形県": "山形市", "福島県": "福島市", "茨城県": "水戸市",
    "栃木県": "宇都宮市", "群馬県": "前橋市", "埼玉県": "さいたま市", "千葉県": "千葉市",
    "東京都": "千代田区", "神奈川県": "横浜市", "新潟県": "新潟市", "富山県": "富山市",
    "石川県": "金沢市", "福井県": "福井市", "山梨県": "甲府市", "長野県": "長野市",
    "岐阜県": "岐阜市", "静岡県": "静岡市", "愛知県": "名古屋市", "三重県": "津市",
    "滋賀県": "大津市", "京都府": "京都市", "大阪府": "大阪市", "兵庫県": "神戸市",
    "奈良県": "奈良市", "和歌山県": "和歌山市", "鳥取県": "鳥取市", "島根県": "松江市",
    "岡山県": "岡山市", "広島県": "広島市", "山口県": "山口市", "徳島県": "徳島市",
    "香川県": "高松市", "愛媛県": "松山市", "高知県": "高知市", "福岡県": "福岡市",
    "佐賀県": "佐賀市", "長崎県": "長崎市", "熊本県": "熊本市", "大分県": "大分市",
    "宮崎県": "宮崎市", "鹿児島県": "鹿児島市", "沖縄県": "那覇市",
}

# 差別的・NGとなり得る表現の置き換え
_NG_REPLACEMENTS = {
    "体力に自信": "体力を活かせる",
    "体力のある": "活動的な",
    "若い": "活気のある",
    "若手": "意欲的な",
    "元気な": "活気のある",
    "明るい方": "前向きな方",
    "容姿": "",
    "美人": "",
    "イケメン": "",
}

_SALARY_TYPE_MAP = {
    "時給": "時給", "日給": "日給", "週給": "週給", "月給": "月給",
    "月給日給制": "月給", "年俸": "年俸", "完全歩合": "完全歩合",
}

_EMPLOYMENT_TYPE_MAP = {
    "正社員": "正社員", "契約社員": "契約社員",
    "アルバイト・パート": "アルバイト・パート", "パート・アルバイト": "アルバイト・パート",
    "派遣社員": "派遣社員", "業務委託": "業務委託",
    "インターン": "インターン", "ボランティア": "ボランティア", "新卒": "新卒",
}

_WORK_STYLE_MAP = {
    "固定時間制": "固定時間制", "固定": "固定時間制",
    "シフト制": "シフト制", "シフト": "シフト制",
    "フレックス": "フレックスタイム制度", "フレックスタイム制": "フレックスタイム制度",
    "フレックスタイム制度": "フレックスタイム制度",
    "変形労働時間制": "変形労働時間制",
    "裁量労働制": "専門業務型裁量労働制", "専門業務型裁量労働制": "専門業務型裁量労働制",
    "企画業務型裁量労働制": "企画業務型裁量労働制",
    "事業場外みなし労働時間制": "事業場外みなし労働時間制",
    "高度プロフェッショナル制度": "高度プロフェッショナル制度",
}

_CATEGORY_MAP = {
    "IT・通信": "web/オープンSE",
    "製造": "製造オペレーター/ラインマネージャー",
    "建設": "建築施工管理",
    "サービス": "その他営業",
    "医療・福祉": "看護師",
    "営業": "その他営業",
    "事務": "一般事務",
    "販売": "販売/フロアスタッフ（スーパー/ホームセンター）",
    "接客": "飲食ホール/フロアスタッフ",
    "飲食": "飲食ホール/フロアスタッフ",
    "物流": "物流企画/管理",
    "運輸": "配送/宅配/セールスドライバー",
    "金融": "その他金融専門職",
    "不動産": "不動産法人営業",
    "教育": "講師/トレーナー（パソコン/IT/OA）",
    "保育": "保育士",
}


def _clean_discriminatory_text(text):
    """差別的・NGとなり得る表現を置き換える"""
    if pd.isna(text):
        return text
    text_str = str(text)
    for ng_word, replacement in _NG_REPLACEMENTS.items():
        if ng_word in text_str:
            text_str = text_str.replace(ng_word, replacement)
    return text_str


def _num(val):
    """カンマ・「円」を除いた数値に変換。失敗時は None"""
    try:
        return float(str(val).replace(",", "").replace("円", "").strip())
    except (ValueError, TypeError):
        return None


def _load_template_columns():
    """テンプレートの列名（重複除去済み）と生の列名を返す"""
    df_template = pd.read_excel(TEMPLATE_PATH, header=0)
    raw = df_template.columns.tolist()
    clean = []
    for col in raw:
        base = re.sub(r"\.\d+$", "", str(col))
        if base not in clean:
            clean.append(base)
    return clean


def _convert_row(row, cols):
    """1求人（Jobbudy行）→ Indeedテンプレート1行(dict)"""
    d = {c: pd.NA for c in cols}

    def has(col):
        return col in cols

    def get(col):
        return row.get(col)

    def notna(col):
        return pd.notna(row.get(col))

    # ---- 直接マッピング ----
    if has("会社名") and notna("会社名"):
        d["会社名"] = get("会社名")

    if has("職種名") and notna("職種名"):
        d["職種名"] = str(get("職種名")).strip()[:100]

    if has("求人キャッチコピー") and notna("業務内容(概要)"):
        cc = str(get("業務内容(概要)")).strip().replace("\n", "").replace("\r", "")
        d["求人キャッチコピー"] = _clean_discriminatory_text(cc)[:256]

    if has("勤務地（郵便番号）"):
        zc = get("就業先郵便番号") if notna("就業先郵便番号") else (
            get("郵便番号") if notna("郵便番号") else None)
        if zc is not None:
            d["勤務地（郵便番号）"] = str(zc).strip().replace("-", "").replace("−", "")

    if has("募集要項（仕事内容）") and notna("業務内容"):
        d["募集要項（仕事内容）"] = _clean_discriminatory_text(get("業務内容"))

    if has("募集要項（休暇・休日）") and notna("休日"):
        d["募集要項（休暇・休日）"] = get("休日")

    if has("募集要項（勤務時間・曜日）"):
        wh = get("就業時間") if notna("就業時間") else (get("勤務時間") if notna("勤務時間") else None)
        if wh is not None:
            d["募集要項（勤務時間・曜日）"] = wh

    if has("募集要項（求める人材）"):
        req = get("必要な経験・スキル") if notna("必要な経験・スキル") else (
            get("必要な学歴・経験・スキル") if notna("必要な学歴・経験・スキル") else None)
        if req is not None:
            d["募集要項（求める人材）"] = _clean_discriminatory_text(req)

    if has("募集要項（待遇・福利厚生）") and notna("その他福利厚生"):
        d["募集要項（待遇・福利厚生）"] = get("その他福利厚生")

    # ---- 給与形態 ----
    if has("給与形態"):
        d["給与形態"] = _SALARY_TYPE_MAP.get(str(get("給与形態")).strip(), "月給")

    # ---- 給与（最低額・最高額）整合 ----
    min_sal = _num(get("給与（下限）")) if notna("給与（下限）") else None
    max_sal = _num(get("給与（上限）")) if notna("給与（上限）") else None
    if min_sal is not None and max_sal is not None:
        if min_sal > max_sal:
            min_sal, max_sal = max_sal, min_sal
        if min_sal == max_sal:
            max_sal = None
    elif min_sal is None and max_sal is not None:
        min_sal, max_sal = max_sal, None
    if has("給与（最低額）") and min_sal is not None:
        d["給与（最低額）"] = min_sal
    if has("給与（最高額）") and max_sal is not None:
        d["給与（最高額）"] = max_sal

    # ---- 給与（表示形式） ----
    if has("給与（表示形式）"):
        if min_sal is not None and max_sal is not None and min_sal < max_sal:
            d["給与（表示形式）"] = "範囲で表示"
        else:
            d["給与（表示形式）"] = "固定額を表示"

    # ---- 雇用形態 ----
    employment_type = ""
    if has("雇用形態"):
        employment_type = _EMPLOYMENT_TYPE_MAP.get(str(get("雇用形態") or "").strip(), "契約社員")
        d["雇用形態"] = employment_type

    # ---- 勤務地 ----
    if has("勤務地（都道府県・市区町村・町域）"):
        pref = str(get("エリア名（都道府県）")).strip() if notna("エリア名（都道府県）") else ""
        city = str(get("エリア名（市区町村）")).strip() if notna("エリア名（市区町村）") else ""
        if pref and not city:
            city = _CITY_MAP.get(pref, pref.replace("県", "市").replace("府", "市").replace("都", "区"))
        combined = f"{pref} {city}".strip()
        if combined:
            d["勤務地（都道府県・市区町村・町域）"] = combined

    # 派遣社員は市区町村まで、それ以外は丁目・番地／建物名も設定
    if employment_type != "派遣社員":
        if has("勤務地（丁目・番地・号）") and notna("就業先住所1"):
            d["勤務地（丁目・番地・号）"] = str(get("就業先住所1"))
        if has("勤務地（建物名・階数）") and notna("就業先住所2"):
            d["勤務地（建物名・階数）"] = str(get("就業先住所2"))

    # ---- 募集要項（その他）：職業紹介事業者の定型文 ----
    if has("募集要項（その他）"):
        other_info = []
        for col_name in ["会社HP", "求人特記事項", "設立", "従業員数", "資本金"]:
            if notna(col_name):
                other_info.append(f"{col_name}: {get(col_name)}")

        intro = [BRAND_LINE, "【事業内容】 人材派遣・職業紹介", ""]
        job_id = get("求人ID")
        job_id_str = ""
        if pd.notna(job_id):
            job_id_str = str(int(job_id)) if isinstance(job_id, (int, float)) else str(job_id).strip()
        if job_id_str and job_id_str != "nan":
            intro.append(f"この求人（求人ID：{job_id_str}）は職業紹介事業者による紹介求人です。")
        else:
            intro.append("この求人は職業紹介事業者による紹介求人です。")
        intro += ["", "【職業紹介事業者】", f"会社名：{AGENCY_NAME}", f"所在地：{AGENCY_ADDRESS}", "",
                  "【紹介先企業】"]
        company_name = str(get("会社名")) if notna("会社名") else ""
        intro.append(f"会社名：{company_name}")

        pref = str(get("エリア名（都道府県）")) if notna("エリア名（都道府県）") else ""
        city = str(get("エリア名（市区町村）")) if notna("エリア名（市区町村）") else ""
        addr1 = str(get("就業先住所1")) if notna("就業先住所1") else ""
        addr2 = str(get("就業先住所2")) if notna("就業先住所2") else ""
        location = "".join(p for p in [pref, city, addr1, addr2] if p)
        intro.append(f"所在地：{location}")

        if other_info:
            d["募集要項（その他）"] = "\n".join(other_info) + "\n\n" + "\n".join(intro)
        else:
            d["募集要項（その他）"] = "\n".join(intro)

    # ---- 募集要項（アピールポイント） ----
    if has("募集要項（アピールポイント）"):
        appeal = []
        for col_name in ["企業理念・ビジョン", "企業理念・ビジョンの説明", "求人の特徴"]:
            if notna(col_name):
                appeal.append(f"{col_name}: {get(col_name)}")
        if appeal:
            d["募集要項（アピールポイント）"] = "\n".join(appeal)

    # ---- 固定値 ----
    if has("ステータス"):
        d["ステータス"] = "募集中"
    if has("有料職業紹介に該当"):
        d["有料職業紹介に該当"] = "はい"
    if has("履歴書の有無"):
        d["履歴書の有無"] = "必須"

    # ---- 勤務形態 ----
    if has("勤務形態"):
        if notna("勤務形態"):
            d["勤務形態"] = _WORK_STYLE_MAP.get(str(get("勤務形態")), "固定時間制")
        else:
            d["勤務形態"] = "固定時間制"

    # ---- 社会保険 ----
    insurance_str = str(get("求人加入保険")) if notna("求人加入保険") else ""
    if employment_type in ["正社員", "契約社員", "派遣社員", "新卒"]:
        insurance_list = ["雇用保険", "労災保険", "健康保険", "厚生年金"]
    else:
        if insurance_str:
            insurance_list = [ins for ins in ["雇用保険", "労災保険", "健康保険", "厚生年金"]
                              if ins in insurance_str]
        else:
            insurance_list = ["雇用保険", "労災保険", "健康保険", "厚生年金"]
    all_insurance_applied = len(insurance_list) == 4
    if has("社会保険"):
        d["社会保険"] = ",".join(insurance_list) if insurance_list else pd.NA
    if has("社会保険（適用されない理由）"):
        if notna("社会保険（適用されない理由）"):
            d["社会保険（適用されない理由）"] = str(get("社会保険（適用されない理由）")).replace("\n", "").replace("\r", "")[:256]
        elif not all_insurance_applied:
            d["社会保険（適用されない理由）"] = "勤務条件により一部適用対象外"

    # ---- 固定残業代・試用期間（デフォルト） ----
    salary_type_converted = str(d.get("給与形態") or "")
    if salary_type_converted != "時給" and has("固定残業代の有無"):
        d["固定残業代の有無"] = "なし"
    if has("試用期間の有無"):
        d["試用期間の有無"] = "なし"

    # ---- 平均所定労働時間（時給は設定しない） ----
    if has("平均所定労働時間") and salary_type_converted != "時給":
        valid_emp = ["正社員", "アルバイト・パート", "派遣社員", "契約社員", "インターン", "ボランティア", "新卒"]
        valid_sal = ["日給", "週給", "月給", "年俸"]
        if employment_type in valid_emp or salary_type_converted in valid_sal:
            if notna("平均所定労働時間"):
                d["平均所定労働時間"] = get("平均所定労働時間")
            elif salary_type_converted == "日給":
                d["平均所定労働時間"] = 8
            elif salary_type_converted == "週給":
                d["平均所定労働時間"] = 40
            else:
                d["平均所定労働時間"] = 160

    # ---- 職業カテゴリー ----
    if has("職業カテゴリー"):
        if notna("職業カテゴリー"):
            d["職業カテゴリー"] = str(get("職業カテゴリー"))
        else:
            orig_cat = str(get("業界（大分類）") or "")
            d["職業カテゴリー"] = _CATEGORY_MAP.get(orig_cat, "その他営業")

    # ---- 審査用の質問 ----
    if has("審査用の質問") and notna("書類選考") and str(get("書類選考")) == "あり":
        d["審査用の質問"] = "- type: 書類選考\n  dealbreaker: はい"

    # ---- 応募用メールアドレス ----
    if has("応募用メールアドレス"):
        d["応募用メールアドレス"] = get("応募用メールアドレス") if notna("応募用メールアドレス") else DEFAULT_APPLY_EMAIL

    # ---- 採用予定人数 ----
    if has("採用予定人数"):
        if notna("採用予定人数"):
            try:
                count = int(float(get("採用予定人数")))
                if 1 <= count <= 10:
                    d["採用予定人数"] = str(count)
                elif count > 10:
                    d["採用予定人数"] = "11人以上"
                else:
                    d["採用予定人数"] = "1"
            except (ValueError, TypeError):
                recruit_str = str(get("採用予定人数")).strip()
                d["採用予定人数"] = "常時募集" if ("常時" in recruit_str or "随時" in recruit_str) else "1"
        else:
            d["採用予定人数"] = "1"

    return d


def _zipcode_is_dummy(row):
    """郵便番号が0000000のダミー行か判定"""
    for col in ("就業先郵便番号", "郵便番号"):
        if col in row and pd.notna(row.get(col)):
            zc = str(row.get(col)).strip().replace("-", "").replace("−", "")
            if zc == "0" * 7:
                return True
    return False


def convert_jobbudy_to_indeed(job_bytes: bytes, source_filename: str = "求人一覧",
                              chunk_size: int = CHUNK_SIZE):
    """
    Jobbudyの求人一覧Excelバイト列を受け取り、Indeed形式に変換した
    分割済みxlsxファイル群を返す。

    戻り値:
        files: list[(filename: str, data: bytes)]
        stats: dict  ... {"total": 元件数, "converted": 変換件数, "skipped": スキップ数, "parts": 分割数}
    """
    if pd is None:
        raise RuntimeError(
            "pandas / openpyxl が未インストールです。"
            "サーバーで `pip install pandas openpyxl` を実行してください。"
        )
    df_jobs = pd.read_excel(io.BytesIO(job_bytes))
    cols = _load_template_columns()

    total = len(df_jobs)
    skipped = 0
    rows = []
    for _, row in df_jobs.iterrows():
        row_dict = row.to_dict()
        if _zipcode_is_dummy(row_dict):
            skipped += 1
            continue
        rows.append(_convert_row(row_dict, cols))

    df_out = pd.DataFrame(rows, columns=cols)
    df_out.drop_duplicates(inplace=True)
    converted = len(df_out)

    # ソースファイル名から拡張子を除いた stem を出力名に使う
    stem = re.sub(r"\.(xlsx|xls|csv)$", "", source_filename, flags=re.IGNORECASE) or "求人一覧"

    num_chunks = max(1, (converted + chunk_size - 1) // chunk_size)
    files = []
    for i in range(num_chunks):
        chunk = df_out.iloc[i * chunk_size:(i + 1) * chunk_size]
        buf = io.BytesIO()
        chunk.to_excel(buf, index=False, engine="openpyxl")
        files.append((f"{stem}_indeed_part{i + 1:03d}.xlsx", buf.getvalue()))

    stats = {"total": total, "converted": converted, "skipped": skipped, "parts": num_chunks}
    return files, stats
