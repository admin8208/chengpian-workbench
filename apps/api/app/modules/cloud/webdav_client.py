
"""WebDAV client for cloud storage integration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, quote

import requests
from loguru import logger

from app.logging_setup import sanitize_log_text


class WebDAVClient:
    """WebDAV client for accessing cloud storage."""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/') + '/'
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers['User-Agent'] = 'ChengPian-Workbench/1.0'
    
    def _make_url(self, path: str) -> str:
        """Build full URL from relative path."""
        encoded_path = '/'.join(quote(p, safe='') for p in path.strip('/').split('/'))
        return urljoin(self.base_url, encoded_path)
    
    def list_files(self, path: str = '/') -> list[dict[str, Any]]:
        """List files and directories at given path."""
        url = self._make_url(path)
        
        headers = {
            'Depth': '1',
            'Content-Type': 'application/xml',
        }
        
        body = '<?xml version=\"1.0\" encoding=\"utf-8\"?>'
        body += '<D:propfind xmlns:D=\"DAV:\">'
        body += '<D:prop>'
        body += '<D:displayname/>'
        body += '<D:getcontentlength/>'
        body += '<D:getcontenttype/>'
        body += '<D:resourcetype/>'
        body += '<D:getlastmodified/>'
        body += '</D:prop>'
        body += '</D:propfind>'
        
        try:
            response = self.session.request('PROPFIND', url, headers=headers, data=body, timeout=30)
            
            if response.status_code == 207:
                return self._parse_propfind_response(response.text, path)
            elif response.status_code == 401:
                raise Exception("认证失败，请检查用户名和密码")
            elif response.status_code == 404:
                raise Exception(f"路径不存在: {path}")
            else:
                raise Exception(f"WebDAV 请求失败: {response.status_code}")
                
        except requests.exceptions.Timeout:
            raise Exception("连接超时，请检查服务器地址")
        except requests.exceptions.ConnectionError:
            raise Exception("连接失败，请检查服务器地址")
        except Exception as e:
            if isinstance(e, Exception):
                raise
            raise Exception(f"WebDAV 错误: {str(e)}")
    
    def _parse_propfind_response(self, xml_text: str, base_path: str) -> list[dict[str, Any]]:
        """Parse PROPFIND XML response."""
        import xml.etree.ElementTree as ET
        
        items = []
        try:
            root = ET.fromstring(xml_text)
            ns = {'D': 'DAV:'}
            
            for response in root.findall('.//D:response', ns):
                href = response.find('.//D:href', ns)
                if href is None:
                    continue
                
                href_path = href.text or ''
                
                prop = response.find('.//D:propstat/D:prop', ns)
                if prop is None:
                    continue
                
                displayname = prop.find('D:displayname', ns)
                contentlength = prop.find('D:getcontentlength', ns)
                contenttype = prop.find('D:getcontenttype', ns)
                resourcetype = prop.find('D:resourcetype', ns)
                lastmodified = prop.find('D:getlastmodified', ns)
                
                is_dir = False
                if resourcetype is not None:
                    is_dir = resourcetype.find('D:collection', ns) is not None
                
                name = displayname.text if displayname is not None and displayname.text else ''
                if not name:
                    name = href_path.rstrip('/').split('/')[-1]
                
                if not name or name == base_path.strip('/').split('/')[-1]:
                    continue
                
                item = {
                    'name': name,
                    'path': href_path,
                    'is_dir': is_dir,
                    'size': int(contentlength.text) if contentlength is not None and contentlength.text else 0,
                    'content_type': contenttype.text if contenttype is not None and contenttype.text else '',
                    'modified': lastmodified.text if lastmodified is not None and lastmodified.text else '',
                }
                
                if not is_dir:
                    ct = item['content_type'].lower()
                    if ct.startswith('image/'):
                        item['type'] = 'image'
                    elif ct.startswith('video/'):
                        item['type'] = 'video'
                    elif ct.startswith('audio/'):
                        item['type'] = 'audio'
                    else:
                        item['type'] = 'other'
                else:
                    item['type'] = 'directory'
                
                items.append(item)
                
        except ET.ParseError as e:
            logger.error("webdav xml parse error: {}", sanitize_log_text(e))
            raise Exception("解析 WebDAV 响应失败")
        
        return items
    
    def download_file(self, remote_path: str, local_path: Path) -> bool:
        """Download file from WebDAV to local path."""
        url = self._make_url(remote_path)
        
        try:
            response = self.session.get(url, stream=True, timeout=60)
            
            if response.status_code == 200:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            elif response.status_code == 401:
                raise Exception("认证失败")
            elif response.status_code == 404:
                raise Exception(f"文件不存在: {remote_path}")
            else:
                raise Exception(f"下载失败: {response.status_code}")
                
        except requests.exceptions.Timeout:
            raise Exception("下载超时")
        except requests.exceptions.ConnectionError:
            raise Exception("连接失败")
        except Exception as e:
            if isinstance(e, Exception):
                raise
            raise Exception(f"下载错误: {str(e)}")


def test_webdav_connection(base_url: str, username: str, password: str) -> dict[str, Any]:
    """Test WebDAV connection."""
    client = WebDAVClient(base_url, username, password)
    
    try:
        files = client.list_files('/')
        return {
            'success': True,
            'message': '连接成功',
            'file_count': len(files),
        }
    except Exception as e:
        return {
            'success': False,
            'message': str(e),
        }
