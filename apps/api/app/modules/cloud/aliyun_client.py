
"""Aliyun Drive client for cloud storage integration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from loguru import logger

from app.logging_setup import sanitize_log_text


class AliyunDriveClient:
    """Aliyun Drive client using Open API."""
    
    BASE_URL = "https://openapi.aliyundrive.com"
    
    def __init__(self, access_token: str, refresh_token: str = ""):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        })
    
    def _refresh_access_token(self) -> bool:
        """Refresh access token using refresh token."""
        if not self.refresh_token:
            return False
        
        try:
            response = requests.post(
                "https://auth.aliyundrive.com/v2/account/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                timeout=30,
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token", "")
                self.refresh_token = data.get("refresh_token", "")
                self.session.headers["Authorization"] = f"Bearer {self.access_token}"
                return True
            
            return False
        except Exception as e:
            logger.error("aliyun token refresh failed: {}", sanitize_log_text(e))
            return False
    
    def list_files(self, path: str = "/", parent_file_id: str = "root") -> list[dict[str, Any]]:
        """List files at given path."""
        url = f"{self.BASE_URL}/adrive/v1.0/openFile/list"
        
        payload = {
            "drive_id": "me",
            "parent_file_id": parent_file_id,
            "limit": 100,
            "order_by": "name",
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code == 401:
                if self._refresh_access_token():
                    response = self.session.post(url, json=payload, timeout=30)
                else:
                    raise Exception("认证失败，请重新获取授权码")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                
                files = []
                for item in items:
                    file_info = {
                        "name": item.get("name", ""),
                        "path": f"{path.rstrip('/')}/{item.get('name', '')}",
                        "file_id": item.get("file_id", ""),
                        "is_dir": item.get("type") == "folder",
                        "size": item.get("size", 0),
                        "type": self._get_file_type(item),
                        "modified": item.get("updated_at", ""),
                    }
                    files.append(file_info)
                
                return files
            else:
                raise Exception(f"请求失败: {response.status_code}")
                
        except requests.exceptions.Timeout:
            raise Exception("连接超时")
        except requests.exceptions.ConnectionError:
            raise Exception("连接失败")
        except Exception as e:
            if isinstance(e, Exception):
                raise
            raise Exception(f"错误: {str(e)}")
    
    def _get_file_type(self, item: dict) -> str:
        """Determine file type from item."""
        if item.get("type") == "folder":
            return "directory"
        
        mime = item.get("mime_type", "").lower()
        if mime.startswith("image/"):
            return "image"
        elif mime.startswith("video/"):
            return "video"
        elif mime.startswith("audio/"):
            return "audio"
        
        # Try from extension
        name = item.get("name", "").lower()
        ext = Path(name).suffix
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            return "image"
        elif ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            return "video"
        elif ext in (".mp3", ".wav", ".aac", ".ogg"):
            return "audio"
        
        return "other"
    
    def get_download_url(self, file_id: str) -> str:
        """Get download URL for file."""
        url = f"{self.BASE_URL}/adrive/v1.0/openFile/getDownloadUrl"
        
        payload = {
            "drive_id": "me",
            "file_id": file_id,
        }
        
        response = self.session.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("url", "")
        else:
            raise Exception(f"获取下载链接失败: {response.status_code}")
    
    def download_file(self, file_id: str, local_path: Path) -> bool:
        """Download file to local path."""
        download_url = self.get_download_url(file_id)
        
        if not download_url:
            raise Exception("无法获取下载链接")
        
        response = requests.get(download_url, stream=True, timeout=300)
        
        if response.status_code == 200:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            raise Exception(f"下载失败: {response.status_code}")


def get_aliyun_auth_url(client_id: str, redirect_uri: str) -> str:
    """Get Aliyun Drive OAuth authorization URL."""
    return (
        f"https://auth.aliyundrive.com/v2/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=user:base,file:all:read"
    )


def exchange_aliyun_code(client_id: str, client_secret: str, code: str) -> dict[str, Any]:
    """Exchange authorization code for tokens."""
    response = requests.post(
        "https://auth.aliyundrive.com/v2/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        },
        timeout=30,
    )
    
    if response.status_code == 200:
        data = response.json()
        return {
            "success": True,
            "access_token": data.get("access_token", ""),
            "refresh_token": data.get("refresh_token", ""),
        }
    else:
        return {
            "success": False,
            "message": f"获取令牌失败: {response.status_code}",
        }
