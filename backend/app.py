from __future__ import annotations
import re, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
DATA.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)
TERMS_VERSION = "1.0"
MIN_LISTEN_SEC = 45
MIN_RATINGS = 3
engine = create_engine(f"sqlite:///{DATA / 'contest.db'}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vk_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="U")
class Track(Base):
    __tablename__ = "tracks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_vk_id: Mapped[str] = mapped_column(String(32), index=True)
    artist: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(200))
    lyrics: Mapped[str] = mapped_column(Text, default="")
    lyrics_draft: Mapped[str] = mapped_column(Text, default="")
    lyrics_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    filename: Mapped[str] = mapped_column(String(260))
    status: Mapped[str] = mapped_column(String(20), default="draft")
class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vk_id: Mapped[str] = mapped_column(String(32))
    track_id: Mapped[str] = mapped_column(String(36), ForeignKey("tracks.id"))
    terms_version: Mapped[str] = mapped_column(String(16))
    rights_ok: Mapped[bool] = mapped_column(Boolean)
    publish_ok: Mapped[bool] = mapped_column(Boolean)
    split_ok: Mapped[bool] = mapped_column(Boolean)
class Listen(Base):
    __tablename__ = "listens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vk_id: Mapped[str] = mapped_column(String(32), index=True)
    track_id: Mapped[str] = mapped_column(String(36), index=True)
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("vk_id", "track_id"),)
class Vote(Base):
    __tablename__ = "votes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vk_id: Mapped[str] = mapped_column(String(32), index=True)
    track_id: Mapped[str] = mapped_column(String(36), index=True)
    lyrics: Mapped[int] = mapped_column(Integer)
    hook: Mapped[int] = mapped_column(Integer)
    music: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("vk_id", "track_id"),)
Base.metadata.create_all(engine)
app = FastAPI(title="VK Song Contest")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
def db_session():
    s = SessionLocal()
    try: yield s
    finally: s.close()
def current_vk(x_user_id: Optional[str] = Header(default=None), x_user_name: Optional[str] = Header(default=None), s: Session = Depends(db_session)):
    if not x_user_id or not re.fullmatch(r"[0-9]{1,16}", x_user_id):
        raise HTTPException(401, "Need X-User-Id")
    if not s.scalar(select(User).where(User.vk_id == x_user_id)):
        s.add(User(vk_id=x_user_id, name=x_user_name or x_user_id)); s.commit()
    return x_user_id
def _sums(s, tid):
    row = s.execute(select(func.coalesce(func.sum(Vote.lyrics),0), func.coalesce(func.sum(Vote.hook),0), func.coalesce(func.sum(Vote.music),0), func.count(Vote.id)).where(Vote.track_id==tid)).one()
    return {"lyrics": int(row[0]), "hook": int(row[1]), "music": int(row[2]), "votes": int(row[3]), "total": int(row[0]+row[1]+row[2])}
def _given(s, vk): return s.scalar(select(func.count(Vote.id)).where(Vote.vk_id==vk)) or 0
def refresh(s, vk):
    given = _given(s, vk)
    for t in s.scalars(select(Track).where(Track.owner_vk_id==vk)).all():
        if t.status == "rejected": continue
        ok = s.scalar(select(Consent).where(Consent.track_id==t.id)) and t.lyrics_confirmed and t.filename
        t.status = "draft" if not ok else ("active" if given >= MIN_RATINGS else "pending")
    s.commit()
def out(s, t, vk):
    sums = _sums(s, t.id) if t.status=="active" else {"lyrics":0,"hook":0,"music":0,"votes":0,"total":0}
    listen = s.scalar(select(Listen).where(Listen.vk_id==vk, Listen.track_id==t.id))
    vote = s.scalar(select(Vote).where(Vote.vk_id==vk, Vote.track_id==t.id))
    return {"id": t.id, "artist": t.artist, "title": t.title, "status": t.status, "owner": t.owner_vk_id==vk,
        "lyrics": t.lyrics if (t.lyrics_confirmed or t.owner_vk_id==vk) else "", "lyrics_draft": t.lyrics_draft if t.owner_vk_id==vk else "",
        "lyrics_confirmed": t.lyrics_confirmed, "duration_sec": 0, "scores": sums, "my_listen_sec": listen.seconds if listen else 0,
        "my_vote": {"lyrics": vote.lyrics, "hook": vote.hook, "music": vote.music} if vote else None,
        "can_vote": t.status=="active" and t.owner_vk_id!=vk and not vote and (listen.seconds if listen else 0) >= MIN_LISTEN_SEC}
class VoteIn(BaseModel):
    lyrics: int = Field(ge=1, le=10); hook: int = Field(ge=1, le=10); music: int = Field(ge=1, le=10)
class LyricsIn(BaseModel):
    lyrics: str
class ListenIn(BaseModel):
    seconds: int = Field(ge=0, le=3600)
class ConsentIn(BaseModel):
    rights_ok: bool; publish_ok: bool; split_ok: bool
@app.get("/api/me")
def me(vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    given = _given(s, vk)
    return {"vk_id": vk, "ratings_given": given, "need_ratings": max(0, MIN_RATINGS-given), "min_listen_sec": MIN_LISTEN_SEC, "terms_version": TERMS_VERSION,
            "tracks": [out(s,t,vk) for t in s.scalars(select(Track).where(Track.owner_vk_id==vk)).all()]}
@app.get("/api/tracks")
def lst(vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    items = [out(s,t,vk) for t in s.scalars(select(Track).where(Track.status=="active")).all()]
    items.sort(key=lambda x: x["scores"]["total"], reverse=True)
    return {"items": items}
@app.get("/api/tracks/{tid}")
def one(tid: str, vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    t = s.get(Track, tid)
    if not t: raise HTTPException(404)
    if t.status!="active" and t.owner_vk_id!=vk: raise HTTPException(403)
    return out(s,t,vk)
@app.post("/api/tracks")
async def up(artist: str = Form(...), title: str = Form(...), file: UploadFile = File(...), vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    ext = Path(file.filename or "").suffix.lower() or ".mp3"
    raw = await file.read()
    tid = str(uuid.uuid4()); fname = f"{tid}{ext}"
    (UPLOADS / fname).write_bytes(raw)
    t = Track(id=tid, owner_vk_id=vk, artist=artist.strip()[:160], title=title.strip()[:200], filename=fname, status="draft",
              lyrics_draft="[черновик]\nВставьте текст и подтвердите.")
    s.add(t); s.commit(); return out(s,t,vk)
@app.post("/api/tracks/{tid}/consent")
def cons(tid: str, body: ConsentIn, vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    t = s.get(Track, tid)
    if not t or t.owner_vk_id!=vk: raise HTTPException(404)
    if not (body.rights_ok and body.publish_ok and body.split_ok): raise HTTPException(400, "Нужны все галочки")
    s.add(Consent(vk_id=vk, track_id=tid, terms_version=TERMS_VERSION, **body.model_dump())); s.commit(); refresh(s, vk); return out(s, s.get(Track,tid), vk)
@app.post("/api/tracks/{tid}/lyrics")
def lyr(tid: str, body: LyricsIn, vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    t = s.get(Track, tid)
    if not t or t.owner_vk_id!=vk: raise HTTPException(404)
    if len(body.lyrics.strip())<20: raise HTTPException(400, "Короткий текст")
    t.lyrics = t.lyrics_draft = body.lyrics.strip(); t.lyrics_confirmed = True; s.commit(); refresh(s, vk); return out(s,t,vk)
@app.post("/api/tracks/{tid}/transcribe")
def tr(tid: str, vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    t = s.get(Track, tid)
    if not t or t.owner_vk_id!=vk: raise HTTPException(404)
    t.lyrics_draft = f"[автотекст]\n{t.artist} — {t.title}\nКуплет\nЯ записал этот трек\nПрипев\nЭто хук, поправь"; s.commit()
    return {"lyrics_draft": t.lyrics_draft}
@app.get("/api/tracks/{tid}/audio")
def audio(tid: str, vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    t = s.get(Track, tid)
    if not t: raise HTTPException(404)
    p = UPLOADS / t.filename
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p, media_type="audio/mpeg", filename=t.filename)
@app.post("/api/tracks/{tid}/listen")
def lis(tid: str, body: ListenIn, vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    t = s.get(Track, tid)
    if not t or t.status!="active": raise HTTPException(404)
    if t.owner_vk_id==vk: raise HTTPException(400)
    row = s.scalar(select(Listen).where(Listen.vk_id==vk, Listen.track_id==tid))
    if not row:
        row = Listen(vk_id=vk, track_id=tid, seconds=0); s.add(row)
    row.seconds = max(row.seconds, body.seconds); s.commit()
    return {"seconds": row.seconds, "enough": row.seconds >= MIN_LISTEN_SEC}
@app.post("/api/tracks/{tid}/vote")
def vote(tid: str, body: VoteIn, vk: str = Depends(current_vk), s: Session = Depends(db_session)):
    t = s.get(Track, tid)
    if not t or t.status!="active": raise HTTPException(404)
    if t.owner_vk_id==vk: raise HTTPException(400, "Свой трек")
    if s.scalar(select(Vote).where(Vote.vk_id==vk, Vote.track_id==tid)): raise HTTPException(400, "Уже оценили")
    listen = s.scalar(select(Listen).where(Listen.vk_id==vk, Listen.track_id==tid))
    if not listen or listen.seconds < MIN_LISTEN_SEC: raise HTTPException(400, "Сначала 45 сек")
    s.add(Vote(vk_id=vk, track_id=tid, **body.model_dump())); s.commit(); refresh(s, vk); return out(s,t,vk)
@app.get("/api/offer")
def offer():
    p = ROOT.parent / "docs" / "OFFER_v1.md"
    return {"version": TERMS_VERSION, "markdown": p.read_text(encoding="utf-8") if p.exists() else "Оферта 85/5/10"}
FE = ROOT.parent / "frontend"
if FE.exists():
    app.mount("/", StaticFiles(directory=str(FE), html=True), name="ui")
