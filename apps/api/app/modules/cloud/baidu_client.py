
"""Baidu Netdisk client for cloud storage integration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from loguru import logger


class BaiduNetdiskClient:
    """Baidu Netdisk client using Open API."""
    
    BASE_URL = "https://pan.baidu.com/rest/2.0/xpan"
    
    def __init__(self, access_token: str, refresh_token: str = ""):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.session = requests.Session()
    
    def _make_request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Make authenticated request."""
        url = f"{self.BASE_URL}{path}"
        params = kwargs.get("params", {})
        params["access_token"] = self.access_token
        kwargs["params"] = params
        
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            if response.status_code == 200:
                data = response.json()
                if "errno" in data and data["errno"] != 0:
                    raise Exception(f"百度网盘错误: {data.get('errmsg', '未知错误')}")
                return data
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
    
    def list_files(self, path: str = "/", order: str = "name") -> list[dict[str, Any]]:
        """List files at given path."""
        data = self._make_request("GET", "/file", params={
            "dir": path,
            "order": order,
            "limit": 100,
        })
        
        files = []
        for item in data.get("list", []):
            file_info = {
                "name": item.get("server_filename", ""),
                "path": item.get("path", ""),
                "file_id": str(item.get("fs_id", 0) or ""),
                "fs_id": item.get("fs_id", 0),
                "is_dir": item.get("isdir") == 1,
                "size": item.get("size", 0),
                "type": self._get_file_type(item),
                "modified": self._format_time(item.get("server_mtime", 0)),
            }
            files.append(file_info)
        
        return files
    
    def _get_file_type(self, item: dict) -> str:
        """Determine file type."""
        if item.get("isdir") == 1:
            return "directory"
        
        category = item.get("category", 0)
        if category == 1:
            return "image"
        elif category == 2:
            return "video"
        elif category == 3:
            return "audio"
        
        # Try from extension
        name = item.get("server_filename", "").lower()
        ext = Path(name).suffix
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            return "image"
        elif ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            return "video"
        elif ext in (".mp3", ".wav", ".aac", ".ogg"):
            return "audio"
        
        return "other"
    
    def _format_time(self, timestamp: int) -> str:
        """Format Unix timestamp."""
        if not timestamp:
            return ""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).isoformat()
    
    def get_download_link(self, fs_id: int) -> str:
        """Get download link for file."""
        data = self._make_request("GET", "/multimedia", params={
            "fsids": f"[{fs_id}]",
            "dlink": 1,
        })
        
        items = data.get("list", [])
        if items:
            return items[0].get("dlink", "")
        return ""
    
    def download_file(self, fs_id: int, local_path: Path) -> bool:
        """Download file to local path."""
        download_url = self.get_download_link(fs_id)
        
        if not download_url:
            raise Exception("无法获取下载链接")
        
        # Add access token to download URL
        download_url += f"&access_token={self.access_token}"
        
        response = requests.get(download_url, stream=True, timeout=300, headers={
            "User-Agent": "pan.baidu.com",
        })
        
        if response.status_code == 200:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            raise Exception(f"下载失败: {response.status_code}")


def get_baidu_auth_url(client_id: str, redirect_uri: str) -> str:
    """Get Baidu OAuth authorization URL."""
    return (
        f"https://openapi.baidu.com/oauth/2.0/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=basic,netdisk"
    )


def exchange_baidu_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code for tokens."""
    response = requests.post(
        "https://openapi.baidu.com/oauth/2.0/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
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
