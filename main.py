from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
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

    headers = [
        "求人タイトル",
        "会社名",
        "勤務地（都道府県）",
        "勤務地（市区町村）",
        "雇用形態",
        "給与（下限）",
        "給与（上限）",
        "給与単位",
        "仕事内容",
        "応募資格",
        "歓迎スキル・経験",
        "勤務時間",
        "休日・休暇",
        "待遇・福利厚生",
        "選考プロセス",
        "応募URL",
        "担当者名",
        "担当者電話番号",
        "担当者メール",
        "会社URL",
        "作成日",
    ]
    writer.writerow(headers)

    for job in jobs:
        writer.writerow(
            [
                job.job_title or "",
                job.company_name or "",
                job.prefecture or "",
                job.city or "",
                job.employment_type or "",
                job.salary_min or "",
                job.salary_max or "",
                job.salary_type or "",
                job.description or "",
                job.requirements or "",
                job.preferred_skills or "",
                job.working_hours or "",
                job.holidays or "",
                job.benefits or "",
                job.selection_process or "",
                job.application_url or "",
                job.contact_name or "",
                job.contact_phone or "",
                job.contact_email or "",
                job.company_url or "",
                job.created_at.strftime("%Y-%m-%d") if job.created_at else "",
            ]
        )

    csv_bytes = output.getvalue().encode("utf-8-sig")
    filename = f"indeed_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
