
"""OneDrive client for cloud storage integration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from loguru import logger

from app.logging_setup import sanitize_log_text


class OneDriveClient:
    """OneDrive client using Microsoft Graph API."""
    
    BASE_URL = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, access_token: str, refresh_token: str = "", client_id: str = "", client_secret: str = ""):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        })
    
    def _refresh_access_token(self) -> bool:
        """Refresh access token."""
        if not self.refresh_token or not self.client_id:
            return False
        
        try:
            response = requests.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "Files.Read offline_access",
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
            logger.error("onedrive token refresh failed: {}", sanitize_log_text(e))
            return False
    
    def list_files(self, path: str = "/") -> list[dict[str, Any]]:
        """List files at given path."""
        if path == "/":
            url = f"{self.BASE_URL}/me/drive/root/children"
        else:
            url = f"{self.BASE_URL}/me/drive/root:{path}:/children"
        
        try:
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 401:
                if self._refresh_access_token():
                    response = self.session.get(url, timeout=30)
                else:
                    raise Exception("认证失败，请重新获取授权码")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("value", [])
                
                files = []
                for item in items:
                    file_info = {
                        "name": item.get("name", ""),
                        "path": f"{path.rstrip('/')}/{item.get('name', '')}",
                        "file_id": item.get("id", ""),
                        "id": item.get("id", ""),
                        "is_dir": "folder" in item,
                        "size": item.get("size", 0),
                        "type": self._get_file_type(item),
                        "modified": item.get("lastModifiedDateTime", ""),
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
        """Determine file type."""
        if "folder" in item:
            return "directory"
        
        mime = item.get("file", {}).get("mimeType", "").lower()
        if mime.startswith("image/"):
            return "image"
        elif mime.startswith("video/"):
            return "video"
        elif mime.startswith("audio/"):
            return "audio"
        
        name = item.get("name", "").lower()
        ext = Path(name).suffix
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            return "image"
        elif ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            return "video"
        elif ext in (".mp3", ".wav", ".aac", ".ogg"):
            return "audio"
        
        return "other"
    
    def download_file(self, item_id: str, local_path: Path) -> bool:
        """Download file to local path."""
        url = f"{self.BASE_URL}/me/drive/items/{item_id}/content"
        
        response = self.session.get(url, stream=True, timeout=300, allow_redirects=True)
        
        if response.status_code == 200:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            raise Exception(f"下载失败: {response.status_code}")


def get_onedrive_auth_url(client_id: str, redirect_uri: str) -> str:
    """Get OneDrive OAuth authorization URL."""
    return (
        f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=Files.Read offline_access"
    )


def exchange_onedrive_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code for tokens."""
    response = requests.post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "scope": "Files.Read offline_access",
        },
        timeout=30,
    )
    
    if response.status_code == 200:
        data = response.json()
        if "error" in data:
            return {
                "success": False,
                "message": data.get("error_description", "获取令牌失败"),
            }
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
