from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import csv
import io
import json
from datetime import datetime, timezone

from database import get_db, engine
import models
from models import JobPosting
from ai_service import generate_job_posting

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Indeed求人作る君", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ローカル開発時はFastAPIが静的ファイルを配信
# PythonAnywhereではダッシュボードのStatic Filesで /static/ を設定するため不要だが
# フォールバックとして残しておく（SERVE_STATIC=false で無効化可能）
import os as _os
if _os.getenv("SERVE_STATIC", "true").lower() != "false":
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------- Pydantic schemas ----------


class GenerateRequest(BaseModel):
    company_url: str
    request_text: str
    application_url: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""


class JobCreate(BaseModel):
    company_name: str
    company_url: Optional[str] = None
    job_title: str
    prefecture: Optional[str] = None
    city: Optional[str] = None
    employment_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_type: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    preferred_skills: Optional[str] = None
    working_hours: Optional[str] = None
    holidays: Optional[str] = None
    benefits: Optional[str] = None
    selection_process: Optional[str] = None
    appeal_points: Optional[str] = None
    application_url: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    original_request: Optional[str] = None


class JobUpdate(JobCreate):
    company_name: Optional[str] = None
    job_title: Optional[str] = None


class ExportRequest(BaseModel):
    job_ids: List[int]


# ---------- helpers ----------


def job_to_dict(job: JobPosting) -> dict:
    return {
        "id": job.id,
        "company_name": job.company_name,
        "company_url": job.company_url,
        "job_title": job.job_title,
        "prefecture": job.prefecture,
        "city": job.city,
        "employment_type": job.employment_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_type": job.salary_type,
        "description": job.description,
        "requirements": job.requirements,
        "preferred_skills": job.preferred_skills,
        "working_hours": job.working_hours,
        "holidays": job.holidays,
        "benefits": job.benefits,
        "selection_process": job.selection_process,
        "appeal_points": job.appeal_points,
        "application_url": job.application_url,
        "contact_name": job.contact_name,
        "contact_phone": job.contact_phone,
        "contact_email": job.contact_email,
        "original_request": job.original_request,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


# ---------- routes ----------


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/api/generate")
def generate(req: GenerateRequest):
    if not req.company_url.startswith("http"):
        raise HTTPException(status_code=400, detail="企業URLはhttp/httpsで始まる必要があります")
    if not req.request_text.strip():
        raise HTTPException(status_code=400, detail="依頼文を入力してください")
    try:
        result = generate_job_posting(
            company_url=req.company_url,
            request_text=req.request_text,
            application_url=req.application_url,
            contact_name=req.contact_name,
            contact_phone=req.contact_phone,
            contact_email=req.contact_email,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(JobPosting).order_by(JobPosting.created_at.desc()).all()
    return [job_to_dict(j) for j in jobs]


@app.post("/api/jobs")
def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    job = JobPosting(**job_data.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job_to_dict(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="求人が見つかりません")
    return job_to_dict(job)


@app.put("/api/jobs/{job_id}")
def update_job(job_id: int, job_data: JobUpdate, db: Session = Depends(get_db)):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="求人が見つかりません")
    for key, value in job_data.model_dump(exclude_none=True).items():
        setattr(job, key, value)
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job_to_dict(job)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="求人が見つかりません")
    db.delete(job)
    db.commit()
    return {"message": "削除しました"}


@app.post("/api/export")
def export_jobs(req: ExportRequest, db: Session = Depends(get_db)):
    jobs = db.query(JobPosting).filter(JobPosting.id.in_(req.job_ids)).all()
    if not jobs:
        raise HTTPException(status_code=404, detail="エクスポート対象の求人が見つかりません")

    output = io.StringIO()
    writer = csv.writer(output)

    # Indeed Japan 公式フォーマット（70列）
    headers = [
        "ステータス", "会社名", "職種名", "職業カテゴリー", "求人キャッチコピー",
        "勤務地（郵便番号）", "勤務地（都道府県・市区町村・町域）", "勤務地（丁目・番地・号）", "勤務地（建物名・階数）",
        "雇用形態", "有料職業紹介に該当",
        "給与形態", "給与（最低額）", "給与（最高額）", "給与（表示形式）",
        "固定残業代の有無", "固定残業代（最低額）", "固定残業代（最高額）", "固定残業代（支払い単位）",
        "固定残業代（時間）", "固定残業代（分）", "固定残業代（超過分の追加支払への同意）",
        "勤務形態", "平均所定労働時間", "平均所定労働時間（分）",
        "社会保険", "社会保険（適用されない理由）",
        "試用期間の有無", "試用期間（期間）", "試用期間（期間の単位）", "試用期間（試用期間中の労働条件）",
        "試用期間中の給与形態", "試用期間中の給与（最低額）", "試用期間中の給与（最高額）", "試用期間中の給与（表示形式）",
        "試用期間中の固定残業代の有無", "試用期間中の固定残業代（最低額）", "試用期間中の固定残業代（最高額）",
        "試用期間中の固定残業代（支払い単位）", "試用期間中の固定残業代（時間）", "試用期間中の固定残業代（分）",
        "試用期間中の固定残業代（超過分の追加支払への同意）",
        "試用期間中の平均所定労働時間", "試用期間中の平均所定労働時間（分）", "試用期間中のその他の条件",
        "募集要項（仕事内容）", "募集要項（アピールポイント）", "募集要項（求める人材）",
        "募集要項（勤務時間・曜日）", "募集要項（休暇・休日）", "募集要項（勤務地の補足）",
        "募集要項（アクセス）", "募集要項（給与の補足）", "募集要項（待遇・福利厚生）", "募集要項（その他）",
        "掲載画像", "タグ", "タグ", "タグ",
        "採用予定人数", "履歴書の有無",
        "応募者に関する情報", "応募者に関する情報", "応募者に関する情報",
        "応募用メールアドレス", "求人問い合わせ先電話番号（半角）",
        "審査用の質問", "自動アプローチ利用設定", "自動アプローチ条件設定", "ユーザー指定ID",
    ]
    writer.writerow(headers)

    for job in jobs:
        # アピールポイントを取得
        appeal_pts = []
        if job.appeal_points:
            try:
                appeal_pts = json.loads(job.appeal_points)
            except Exception:
                appeal_pts = [job.appeal_points]
        catchcopy = appeal_pts[0] if appeal_pts else ""
        appeal_text = "\n".join(appeal_pts)

        # 求める人材（必須＋歓迎）
        requirements_combined = "\n".join(filter(None, [
            job.requirements or "",
            f"【歓迎】\n{job.preferred_skills}" if job.preferred_skills else "",
        ]))

        # 勤務地
        location = "".join(filter(None, [job.prefecture or "", job.city or ""]))

        row = [
            "公開",                          # ステータス
            job.company_name or "",          # 会社名
            job.job_title or "",             # 職種名
            "",                              # 職業カテゴリー
            catchcopy,                       # 求人キャッチコピー
            "",                              # 勤務地（郵便番号）
            location,                        # 勤務地（都道府県・市区町村・町域）
            "",                              # 勤務地（丁目・番地・号）
            "",                              # 勤務地（建物名・階数）
            job.employment_type or "",       # 雇用形態
            "",                              # 有料職業紹介に該当
            job.salary_type or "",           # 給与形態
            job.salary_min or "",            # 給与（最低額）
            job.salary_max or "",            # 給与（最高額）
            "",                              # 給与（表示形式）
            "", "", "", "", "", "", "",      # 固定残業代関連（7列）
            "",                              # 勤務形態
            "", "",                          # 平均所定労働時間
            "", "",                          # 社会保険
            "", "", "", "",                  # 試用期間
            "", "", "", "",                  # 試用期間中の給与
            "", "", "", "", "", "", "",      # 試用期間中の固定残業代（7列）
            "", "",                          # 試用期間中の平均所定労働時間
            "",                              # 試用期間中のその他の条件
            job.description or "",           # 募集要項（仕事内容）
            appeal_text,                     # 募集要項（アピールポイント）
            requirements_combined,           # 募集要項（求める人材）
            job.working_hours or "",         # 募集要項（勤務時間・曜日）
            job.holidays or "",              # 募集要項（休暇・休日）
            "",                              # 募集要項（勤務地の補足）
            "",                              # 募集要項（アクセス）
            "",                              # 募集要項（給与の補足）
            job.benefits or "",              # 募集要項（待遇・福利厚生）
            job.selection_process or "",     # 募集要項（その他）
            "",                              # 掲載画像
            "", "", "",                      # タグ（3列）
            "",                              # 採用予定人数
            "",                              # 履歴書の有無
            "", "", "",                      # 応募者に関する情報（3列）
            job.contact_email or "",         # 応募用メールアドレス
            job.contact_phone or "",         # 求人問い合わせ先電話番号
            "", "", "",                      # 審査用の質問・自動アプローチ設定
            "",                              # ユーザー指定ID
        ]
        writer.writerow(row)

    # Indeed Japan テンプレートはShift-JIS
    csv_bytes = output.getvalue().encode("shift_jis", errors="replace")
    filename = f"indeed_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=shift_jis",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
