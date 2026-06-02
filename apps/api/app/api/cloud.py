
"""Cloud storage API endpoints."""
from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.cloud.webdav_client import WebDAVClient, test_webdav_connection
from app.modules.cloud.aliyun_client import AliyunDriveClient
from app.modules.cloud.baidu_client import BaiduNetdiskClient
from app.modules.cloud.onedrive_client import OneDriveClient
from app.settings import settings
from app.db import session_scope
from app.models import Asset

router = APIRouter()


class CloudConnectIn(BaseModel):
    storage_type: str
    name: str = ""
    config: dict[str, Any]


class CloudConnectOut(BaseModel):
    success: bool
    message: str
    storage_id: Optional[int] = None


class CloudListIn(BaseModel):
    storage_type: str
    config: dict[str, Any]
    path: str = "/"


class CloudFileItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int = 0
    type: str = "other"
    modified: str = ""
    file_id: str = ""
    id: str = ""
    fs_id: int = 0


class CloudListOut(BaseModel):
    files: list[CloudFileItem]
    current_path: str


class CloudImportIn(BaseModel):
    storage_type: str
    config: dict[str, Any]
    remote_path: str
    file_id: str = ""
    kind: str = "image"


class CloudImportOut(BaseModel):
    success: bool
    message: str
    asset_id: Optional[int] = None


_BLOCKED_HOSTS = {"localhost"}
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _validate_public_webdav_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="服务器地址不能为空")
    parsed = urlparse(raw)
    scheme = str(parsed.scheme or "").strip().lower()
    if scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="WebDAV 仅支持 http/https 地址")
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        raise HTTPException(status_code=400, detail="WebDAV 地址缺少主机名")
    if host in _BLOCKED_HOSTS:
        raise HTTPException(status_code=400, detail="不允许访问本机或内网 WebDAV 地址")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return raw
    for network in _BLOCKED_NETWORKS:
        if addr in network:
            raise HTTPException(status_code=400, detail="不允许访问本机或内网 WebDAV 地址")
    return raw


def _get_client(storage_type: str, config: dict[str, Any]):
    """Get cloud client based on storage type."""
    if storage_type == "webdav":
        url = _validate_public_webdav_url(config.get("url", ""))
        username = config.get("username", "")
        password = config.get("password", "")
        return WebDAVClient(url, username, password)
    
    elif storage_type == "aliyun":
        access_token = config.get("access_token", "")
        refresh_token = config.get("refresh_token", "")
        if not access_token:
            raise HTTPException(status_code=400, detail="访问令牌不能为空")
        return AliyunDriveClient(access_token, refresh_token)
    
    elif storage_type == "baidu":
        access_token = config.get("access_token", "")
        refresh_token = config.get("refresh_token", "")
        if not access_token:
            raise HTTPException(status_code=400, detail="访问令牌不能为空")
        return BaiduNetdiskClient(access_token, refresh_token)
    
    elif storage_type == "onedrive":
        access_token = config.get("access_token", "")
        refresh_token = config.get("refresh_token", "")
        client_id = config.get("client_id", "")
        client_secret = config.get("client_secret", "")
        if not access_token:
            raise HTTPException(status_code=400, detail="访问令牌不能为空")
        return OneDriveClient(access_token, refresh_token, client_id, client_secret)
    
    else:
        raise HTTPException(status_code=400, detail=f"不支持的存储类型: {storage_type}")


def _download_from_storage(body: CloudImportIn, remote_path: str, local_path: Path) -> None:
    client = _get_client(body.storage_type, body.config)
    if body.storage_type == "webdav":
        cast(WebDAVClient, client).download_file(remote_path, local_path)
        return
    if body.storage_type == "aliyun":
        file_id = str(body.file_id or "").strip()
        if not file_id:
            raise HTTPException(status_code=400, detail="阿里云盘需要文件ID")
        cast(AliyunDriveClient, client).download_file(file_id, local_path)
        return
    if body.storage_type == "baidu":
        file_id = str(body.file_id or "").strip()
        if not file_id:
            raise HTTPException(status_code=400, detail="百度网盘需要文件ID")
        cast(BaiduNetdiskClient, client).download_file(int(file_id), local_path)
        return
    if body.storage_type == "onedrive":
        file_id = str(body.file_id or "").strip()
        if not file_id:
            raise HTTPException(status_code=400, detail="OneDrive需要文件ID")
        cast(OneDriveClient, client).download_file(file_id, local_path)
        return
    raise HTTPException(status_code=400, detail=f"不支持的存储类型: {body.storage_type}")


@router.post("/api/cloud/test", response_model=CloudConnectOut)
def test_cloud_connection(body: CloudConnectIn):
    """Test cloud storage connection."""
    try:
        if body.storage_type == "webdav":
            result = test_webdav_connection(
                body.config.get("url", ""),
                body.config.get("username", ""),
                body.config.get("password", ""),
            )
            return CloudConnectOut(
                success=result["success"],
                message=result["message"],
            )
        elif body.storage_type in ("aliyun", "baidu", "onedrive"):
            # For OAuth-based storage, try to list root
            client = _get_client(body.storage_type, body.config)
            files = client.list_files("/")
            return CloudConnectOut(
                success=True,
                message=f"连接成功，找到 {len(files)} 个文件",
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的存储类型: {body.storage_type}")
    except Exception as e:
        return CloudConnectOut(
            success=False,
            message=str(e),
        )


@router.post("/api/cloud/list", response_model=CloudListOut)
def list_cloud_files(body: CloudListIn):
    """List files in cloud storage."""
    try:
        client = _get_client(body.storage_type, body.config)
        files = client.list_files(body.path)
        return CloudListOut(
            files=[CloudFileItem(**f) for f in files],
            current_path=body.path,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/cloud/import", response_model=CloudImportOut)
def import_from_cloud(body: CloudImportIn):
    """Import file from cloud storage to library."""
    try:
        # Determine file extension from path
        remote_path = body.remote_path
        ext = Path(remote_path).suffix.lower()
        
        # Determine kind
        kind = body.kind
        if kind == "auto":
            if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                kind = "image"
            elif ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
                kind = "video"
            elif ext in (".mp3", ".wav", ".aac", ".ogg"):
                kind = "audio"
            else:
                kind = "other"
        elif kind == "image" and ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            raise HTTPException(status_code=400, detail="当前图片素材页只允许导入图片文件")
        elif kind == "video" and ext not in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            raise HTTPException(status_code=400, detail="当前视频素材页只允许导入视频文件")
        elif kind == "audio" and ext not in (".mp3", ".wav", ".aac", ".ogg"):
            raise HTTPException(status_code=400, detail="当前音频素材页只允许导入音频文件")
        
        # Download to library
        filename = Path(remote_path).name
        local_dir = settings.assets_dir / "library" / kind
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / filename
        
        # Avoid overwriting
        counter = 1
        while local_path.exists():
            stem = Path(remote_path).stem
            local_path = local_dir / f"{stem}_{counter}{ext}"
            counter += 1
        
        _download_from_storage(body, remote_path, local_path)
        
        # Create asset record
        rel_path = str(local_path.relative_to(settings.assets_dir))
        
        with session_scope() as session:
            asset = Asset(
                kind=kind,
                rel_path=rel_path,
                mime=f"{kind}/{ext.lstrip('.')}",
                tag="library",
                meta_json=json.dumps({
                    "source": "cloud",
                    "cloud_type": body.storage_type,
                    "original_path": remote_path,
                }),
            )
            session.add(asset)
            session.flush()
            session.refresh(asset)
            
            return CloudImportOut(
                success=True,
                message=f"导入成功: {filename}",
                asset_id=asset.id,
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(e))
