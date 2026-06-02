from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.file_access import resolve_scoped_file, verify_file_token

router = APIRouter(tags=['file'])


@router.get('/api/files/s/{scope}/{rel_path:path}')
def get_signed_file(scope: str, rel_path: str, token: str = Query(default='')):
    normalized = str(rel_path or '').lstrip('/')
    if not verify_file_token(scope, normalized, token):
        raise HTTPException(status_code=403, detail='文件签名无效或已失配')
    try:
        path = resolve_scoped_file(scope, normalized)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail='文件不存在')
    return FileResponse(path)
