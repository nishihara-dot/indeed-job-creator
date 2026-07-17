"""
Jobbudyの求人一覧Excelを Atally インポート形式（job_template・64列・日本語ヘッダー）の
CSVに直接変換するモジュール。

- Jobbudyの元Excel項目から Atally 64列へ直接マッピング（Indeedを経由しない）
  → 昇給・賞与・最寄り駅・社風・職場環境などAtally固有項目まで埋まる
- bulk_convert.py と同様に openpyxl read_only でストリーミング読み込み、
  メモリ上で (ファイル名, bytes) のCSVリストを返す
- 大量件数でも扱えるよう chunk_size 件ごとに分割
"""
import csv
import io
import re
import math

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

CHUNK_SIZE = 5000  # AtallyのCSV取込を想定した分割上限

# Atally job_template 64列（日本語ヘッダー）
ATALLY_HEADERS = [
    "求人タイトル", "仕事内容", "応募要件", "職種カテゴリ（大）", "職種カテゴリ（小）", "採用区分",
    "給与下限（円）", "給与上限（円）", "給与形態", "給与補足", "昇給", "賞与",
    "都道府県", "市区町村", "勤務地", "詳細住所", "最寄り駅", "アクセス", "転勤の有無",
    "雇用形態", "勤務時間", "リモート", "残業時間", "契約期間", "休日", "休日詳細", "手当",
    "試用期間", "試用期間条件", "選考フロー", "必要書類", "選考期間",
    "社風", "職場環境", "従業員数", "設立年", "業種", "アピールポイント", "備考",
    "紹介許可", "手数料タイプ", "手数料", "紹介条件", "求人種別", "派遣元（雇用主）企業名",
    "ペルソナ_対象年齢下限", "ペルソナ_対象年齢上限", "ペルソナ_経験年数下限", "ペルソナ_経験年数上限",
    "ペルソナ_求めるスキル", "ペルソナ_対象勤務地", "ペルソナ_対象職種", "ペルソナ_就業状態",
    "ペルソナ_学歴条件", "ペルソナ_対象業界", "ペルソナ_希望年収下限", "ペルソナ_希望年収上限",
    "ペルソナ_求める資格", "ペルソナ_マネジメント経験", "ペルソナ_最大転職回数",
    "ペルソナ_人物像", "ペルソナ_NG条件", "ペルソナ_理想の候補者", "ペルソナ_ブースト係数",
]

# 職種カテゴリ（大）の推定：業界（大分類）／職種名のキーワードから
_MAJOR_CATEGORY_RULES = [
    ("営業", ["営業", "MR"]),
    ("IT・Web・通信", ["IT", "通信", "エンジニア", "SE", "プログラマ", "web", "Web", "システム"]),
    ("クリエイティブ・デザイン", ["デザイン", "デザイナー", "クリエイ", "イラスト", "編集", "ライター", "映像"]),
    ("企画・管理・事務", ["企画", "マーケ", "人事", "総務", "法務", "経理", "財務", "会計", "事務",
                        "秘書", "受付", "広報", "購買", "調達", "管理"]),
    ("販売・サービス・飲食", ["販売", "接客", "サービス", "美容", "理容", "エステ", "セラピスト",
                          "飲食", "調理", "ホール", "店長", "ホテル", "警備", "清掃"]),
    ("医療・介護・福祉", ["医療", "看護", "薬剤", "介護", "福祉", "ケア", "療法士", "歯科", "保育"]),
    ("建築・土木・不動産", ["建築", "土木", "施工", "設計", "不動産", "宅建", "現場"]),
    ("製造・技術", ["製造", "機械", "電気", "電子", "生産", "品質", "設備", "工場", "オペレータ"]),
    ("物流・運輸・ドライバー", ["物流", "運輸", "ドライバー", "配送", "倉庫", "運送", "運行"]),
    ("教育・保育", ["教育", "講師", "教員", "トレーナー", "インストラクター"]),
    ("金融・専門職", ["金融", "銀行", "証券", "保険", "会計士", "税理士", "弁護士", "コンサル"]),
]


def _isna(v):
    if v is None:
        return True
    if isinstance(v, float):
        try:
            if math.isnan(v):
                return True
        except (TypeError, ValueError):
            pass
    s = str(v).strip()
    return s == "" or s.lower() == "nan"


def _s(v):
    """安全に文字列化（NaN/None→空文字、数値の .0 を除去）"""
    if _isna(v):
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


def _num(v):
    """カンマ・「円」を除いた整数へ。失敗時は空文字"""
    if _isna(v):
        return ""
    try:
        f = float(str(v).replace(",", "").replace("円", "").strip())
        return int(f) if f == int(f) else f
    except (ValueError, TypeError):
        return ""


def _title_from_job_code(raw):
    """求人タイトル列（会社名/地域/求人コード_報酬タイプ）から職種部分を抽出"""
    if not raw:
        return ""
    last = raw.split("/")[-1]
    return re.sub(r"_入社.{0,10}報酬.*$", "", last).strip()


def _major_category(small, gyokai):
    for major, keywords in _MAJOR_CATEGORY_RULES:
        if any(kw in small for kw in keywords) or any(kw in gyokai for kw in keywords):
            return major
    return "その他"


def _referral_allow(row):
    fee = _s(row.get("協力会社紹介料（固定）")) or _s(row.get("協力会社紹介料（下限）")) or _s(row.get("協力会社紹介料（上限）"))
    return "true" if fee else "false"


def _referral_type(row):
    if _s(row.get("協力会社紹介料（固定）")):
        return "fixed"
    if _s(row.get("協力会社紹介料（下限）")) or _s(row.get("協力会社紹介料（上限）")):
        return "percentage"
    return ""


def _referral_fee(row):
    fixed = _s(row.get("協力会社紹介料（固定）"))
    if fixed:
        return fixed
    lo = _s(row.get("協力会社紹介料（下限）"))
    hi = _s(row.get("協力会社紹介料（上限）"))
    if lo or hi:
        return f"{lo}〜{hi}".strip("〜")
    return ""


def _build_atally_row(r):
    """Jobbudy行(dict) → Atally 64列(list)"""
    def c(name):
        return _s(r.get(name))

    title = c("職種名") or c("職種") or _title_from_job_code(c("求人タイトル"))
    description = c("業務内容(詳細)") or c("業務内容(概要)") or c("業務内容")

    req_parts = [c("必要な経験・スキル"), c("必要な学歴・経験・スキル"), c("必要な免許・資格"), c("その他必須条件")]
    requirements = "\n".join(p for p in req_parts if p)

    prefecture = c("エリア名（都道府県）")
    city = c("エリア名（市区町村）")
    location = prefecture + city
    detail_address = (c("就業先住所1") + c("就業先住所2")).strip()

    work_hours = c("就業時間") or c("勤務時間")
    salary_min = _num(r.get("給与（下限）"))
    salary_max = _num(r.get("給与（上限）"))

    sel_parts = []
    if c("書類選考"):
        sel_parts.append(f"書類選考：{c('書類選考')}")
    if c("面接回数"):
        sel_parts.append(f"面接：{c('面接回数')}回")
    selection_process = "\n".join(sel_parts)

    industry_raw = c("事業内容") or c("業界（大分類）")
    industry = industry_raw[:200]

    small_cat = c("職業カテゴリー") or title
    gyokai = c("業界（大分類）") or c("業界（中分類）")

    employment_type = c("雇用形態")
    recruitment_kind = "人材派遣" if employment_type == "派遣社員" else "人材紹介"

    notes = c("求人特記事項")

    return [
        title,                                   # 求人タイトル
        description,                             # 仕事内容
        requirements,                            # 応募要件
        _major_category(small_cat, gyokai),      # 職種カテゴリ（大）
        small_cat,                               # 職種カテゴリ（小）
        "中途",                                   # 採用区分
        salary_min,                              # 給与下限（円）
        salary_max,                              # 給与上限（円）
        c("給与形態"),                            # 給与形態
        c("給与備考") or c("年収備考"),            # 給与補足
        c("昇給"),                                # 昇給
        c("賞与"),                                # 賞与
        prefecture,                              # 都道府県
        city,                                    # 市区町村
        location,                                # 勤務地
        detail_address,                          # 詳細住所
        c("最寄り駅") or c("最寄駅"),              # 最寄り駅
        c("アクセス") or c("交通アクセス"),        # アクセス
        c("転勤") or c("転勤の有無"),              # 転勤の有無
        employment_type,                         # 雇用形態
        work_hours,                              # 勤務時間
        c("勤務スタイル") or c("リモート"),        # リモート
        c("月平均時間外勤務（時）") or c("残業時間"),  # 残業時間
        c("契約期間"),                            # 契約期間
        c("休日"),                                # 休日
        c("休日（備考）"),                        # 休日詳細
        c("福利厚生（手当）") or c("その他福利厚生"),  # 手当
        c("試用期間"),                            # 試用期間
        c("試用期間条件変更内容"),                 # 試用期間条件
        selection_process,                       # 選考フロー
        "",                                      # 必要書類
        "",                                      # 選考期間
        c("職場の雰囲気"),                        # 社風
        c("一日の流れ"),                          # 職場環境
        c("部署人数") or c("従業員数"),            # 従業員数
        c("設立"),                                # 設立年
        industry,                                # 業種
        c("求人の特徴"),                          # アピールポイント
        notes,                                   # 備考
        _referral_allow(r),                      # 紹介許可
        _referral_type(r),                       # 手数料タイプ
        _referral_fee(r),                        # 手数料
        "",                                      # 紹介条件
        recruitment_kind,                        # 求人種別
        c("会社名"),                              # 派遣元（雇用主）企業名
        c("年齢（下限）"),                        # ペルソナ_対象年齢下限
        c("年齢（上限）"),                        # ペルソナ_対象年齢上限
        "",                                      # ペルソナ_経験年数下限
        "",                                      # ペルソナ_経験年数上限
        c("資格スキル") or c("必要な経験・スキル"),  # ペルソナ_求めるスキル
        prefecture,                              # ペルソナ_対象勤務地
        small_cat,                               # ペルソナ_対象職種
        "",                                      # ペルソナ_就業状態
        "",                                      # ペルソナ_学歴条件
        industry,                                # ペルソナ_対象業界
        "",                                      # ペルソナ_希望年収下限
        "",                                      # ペルソナ_希望年収上限
        c("必要な免許・資格"),                     # ペルソナ_求める資格
        "",                                      # ペルソナ_マネジメント経験
        "",                                      # ペルソナ_最大転職回数
        "",                                      # ペルソナ_人物像
        "",                                      # ペルソナ_NG条件
        c("あれば尚可な経験・資格等"),             # ペルソナ_理想の候補者
        "1.0",                                   # ペルソナ_ブースト係数
    ]


def _iter_input_rows(job_bytes):
    """入力Excelを openpyxl read_only でストリーミングし、行dictを yield"""
    wb = openpyxl.load_workbook(io.BytesIO(job_bytes), read_only=True, data_only=True)
    try:
        ws = wb.active
        row_iter = ws.iter_rows(values_only=True)
        header = [str(c).strip() if c is not None else "" for c in next(row_iter)]
        for values in row_iter:
            if all(v is None or (isinstance(v, str) and v.strip() == "") for v in values):
                continue
            yield dict(zip(header, values))
    finally:
        wb.close()


def _chunk_to_csv_bytes(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(ATALLY_HEADERS)
    writer.writerows(rows)
    # AtallyのCSV取込はBOM無しUTF-8を要求（BOMが付くと先頭ヘッダー「求人タイトル」が一致しない）
    return buf.getvalue().encode("utf-8")


def convert_jobbudy_to_atally(job_bytes, source_filename="求人一覧", chunk_size=CHUNK_SIZE):
    """
    Jobbudyの求人一覧Excelバイト列を Atally 64列形式に変換した分割CSV群を返す。

    戻り値:
        files: list[(filename, data: bytes)]  ... UTF-8 BOM付きCSV
        stats: dict  ... {"total", "converted", "skipped", "parts"}
    """
    if openpyxl is None:
        raise RuntimeError("openpyxl が未インストールです。`pip install openpyxl` を実行してください。")

    stem = re.sub(r"\.(xlsx|xls|csv)$", "", source_filename, flags=re.IGNORECASE) or "求人一覧"

    total = 0
    converted = 0
    files = []
    chunk = []

    def flush():
        if not chunk:
            return
        data = _chunk_to_csv_bytes(chunk)
        files.append((f"{stem}_atally_part{len(files) + 1:03d}.csv", data))
        chunk.clear()

    for row in _iter_input_rows(job_bytes):
        total += 1
        chunk.append(_build_atally_row(row))
        converted += 1
        if len(chunk) >= chunk_size:
            flush()
    flush()

    stats = {"total": total, "converted": converted, "skipped": 0, "parts": len(files)}
    return files, stats
