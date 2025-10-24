from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4
from urllib.parse import unquote

import subprocess

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"

# Event yang ingin ditangani (supaya log tetap bersih)
WHITELIST = {"printing", "file_upload", "session_start", "session_end", "error"}

EVENT_ACTIONS = {
    "session_end": "toWeb.bat",
}

SESSION_LOCK = Lock()
SESSION_STATE: dict[str, str | None] = {
    "status": "idle",
    "last_event": None,
    "started_at": None,
    "completed_at": None,
    "asset_path": None,
    "asset_token": None,
    "share_url": None,
    "error": None,
}

def decode_params(qs: dict) -> dict:
    return {k: unquote(v) for k, v in qs.items()}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def get_session_state() -> dict:
    with SESSION_LOCK:
        return dict(SESSION_STATE)


def mutate_session_state(**changes) -> dict:
    with SESSION_LOCK:
        SESSION_STATE.update(changes)
        return dict(SESSION_STATE)


def build_script_cmd(script_name: str) -> list[str] | None:
    script_path = (SCRIPTS_DIR / script_name).resolve()
    if not script_path.exists():
        log(f"Script not found: {script_path}")
        mutate_session_state(error=f"Script missing: {script_name}")
        return None
    return ["cmd", "/c", str(script_path)]


def run_action(cmd: list[str]) -> None:
    """
    Jalankan aplikasi secara non-blocking.
    Hindari subprocess.run() agar server tidak menunggu aplikasi selesai.
    """
    try:
        subprocess.Popen(cmd, shell=False)
        log(f"Started app: {cmd}")
    except Exception as e:
        log(f"ERROR start app {cmd}: {e}")


def schedule_script(script_name: str, background: BackgroundTasks) -> None:
    cmd = build_script_cmd(script_name)
    if cmd:
        background.add_task(run_action, cmd)


@app.post("/session/start")
async def start_session(background: BackgroundTasks):
    """
    Mulai sesi baru dari UI. Jalankan toBooth.bat lalu ubah status menjadi in_progress.
    """
    with SESSION_LOCK:
        if SESSION_STATE.get("status") == "in_progress":
            current = dict(SESSION_STATE)
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "state": current,
                    "message": "Session already in progress",
                },
            )

        SESSION_STATE.update(
            status="in_progress",
            last_event="session_start_manual",
            started_at=datetime.now().isoformat(),
            completed_at=None,
            asset_path=None,
            asset_token=None,
            share_url=None,
            error=None,
        )
        snapshot = dict(SESSION_STATE)

    schedule_script("toBooth.bat", background)

    return {"ok": True, "state": snapshot}


@app.post("/session/reset")
async def reset_session():
    """
    Reset status sesi supaya bisa memulai ulang dari UI (misalnya tombol retake).
    """
    with SESSION_LOCK:
        SESSION_STATE.update(
            status="idle",
            last_event="manual_reset",
            started_at=None,
            completed_at=None,
            asset_path=None,
            asset_token=None,
            share_url=None,
            error=None,
        )
        snapshot = dict(SESSION_STATE)
    return {"ok": True, "state": snapshot}


@app.get("/session/status")
async def session_status():
    """
    Endpoint polling oleh SPA untuk mengecek progres.
    """
    snapshot = get_session_state()
    asset_path = snapshot.get("asset_path")
    asset_token = snapshot.get("asset_token")
    if asset_path and asset_token:
        path_obj = Path(asset_path)
        if path_obj.is_file():
            snapshot["asset_url"] = f"/session/asset?token={asset_token}"
        else:
            snapshot["asset_url"] = None
        snapshot["asset_name"] = path_obj.name
    else:
        snapshot["asset_url"] = None
        snapshot["asset_name"] = None
    snapshot["share_url"] = snapshot.get("share_url") or None
    return {"ok": True, "state": snapshot}


@app.get("/session/asset")
async def session_asset(token: str | None = None):
    """
    Berikan file hasil sesi terakhir. Token opsional untuk cache-busting di frontend.
    """
    state = get_session_state()
    asset_path = state.get("asset_path")
    asset_token = state.get("asset_token")

    if not asset_path or not asset_token:
        raise HTTPException(status_code=404, detail="No photo available yet.")

    if token and token != asset_token:
        raise HTTPException(status_code=404, detail="Photo token mismatch.")

    path = Path(asset_path)
    if not path.is_file():
        mutate_session_state(error="Asset file missing on disk.")
        raise HTTPException(status_code=404, detail="Photo file not found.")

    return FileResponse(
        path,
        filename=path.name,
        media_type="image/jpeg",
    )


@app.get("/hook")
async def hook(request: Request, background: BackgroundTasks):
    qs_raw = dict(request.query_params)
    qs = decode_params(qs_raw)

    event = qs.get("event_type", "")
    if WHITELIST and event not in WHITELIST:
        # skip event lain agar terminal tidak bising
        return {"ok": True, "ignored": event}

    # Cetak log ringkas
    log("-" * 60)
    log(f"EVENT={event}")
    for k in sorted(qs.keys()):
        log(f"{k} = {qs[k]}")

    # Ambil parameter umum sebagai hint asset/share
    asset_hint = qs.get("param1") or qs.get("path") or qs.get("file")
    if asset_hint:
        asset_hint = asset_hint.strip()

    share_hint = qs.get("param2") or qs.get("share_url")
    if share_hint:
        share_hint = share_hint.strip()

    base_updates = {"last_event": event}
    if asset_hint:
        base_updates["asset_path"] = asset_hint
    if share_hint:
        base_updates["share_url"] = share_hint

    state_after_base = mutate_session_state(**base_updates)

    if event == "session_start":
        mutate_session_state(
            status="in_progress",
            error=None,
        )
    elif event == "error":
        mutate_session_state(
            status="error",
            error=qs.get("message") or "Unknown DSLRBooth error",
        )
    elif event == "session_end":
        final_path = asset_hint or state_after_base.get("asset_path")
        final_share = share_hint or state_after_base.get("share_url")
        token = uuid4().hex if final_path else None
        snapshot = mutate_session_state(
            status="completed",
            completed_at=datetime.now().isoformat(),
            asset_path=final_path,
            asset_token=token,
            share_url=final_share,
            error=None,
        )
        log(f"Session completed: {snapshot}")

    # Tentukan aksi dari mapping
    action = EVENT_ACTIONS.get(event)
    if action:
        schedule_script(action, background)

    return {"ok": True, "event_type": event}


if __name__ == "__main__":
    try:
        import uvicorn  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Uvicorn is required to run the FastAPI server. Install it with 'pip install uvicorn[standard]'."
        ) from exc

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
