# 成片工作台

> 一款面向单机 / 私有化部署场景的**短视频自动生产工作台**。
> 从文案到成片，全程自动化，支持 AI 智能生图和网络素材匹配双模式。

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Vue 3](https://img.shields.io/badge/Vue-3.5-brightgreen)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Redis](https://img.shields.io/badge/Redis-7-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

架构概述：

- 前端构建产物：`apps/web/dist`
- API 服务：`apps/api/run_api.py`
- Worker 服务：`apps/api/run_worker.py`
- 业务数据库：PostgreSQL
- 任务队列：Redis（Huey 后端）
- 本地运行目录：`data/`

Windows 运行说明：

- 开发/调试/生产脚本现在会通过 `scripts/windows/run_worker_supervisor.ps1` 拉起 worker。
- 该 supervisor 会在 `run_worker.py` 意外退出后自动重启，避免任务长期停在 `queued` 或残留假 `running` 状态。

## 核心功能

### 双模式视频创作

- **AI 智能创作**：输入标题/原文，LLM 生成文案脚本 → AI 逐镜头出图 → TTS 配音 → 合成成片
- **网络素材创作**：输入标题/原文，LLM 生成文案脚本 → 自动搜索并匹配网络素材（Pexels / Pixabay / Wikimedia）→ TTS 配音 → 合成成片
- **音频驱动模式**：上传旁白音频，自动转写后生成完整视频
- **Autopilot 自动驾驶**：一键启动，自动执行全部 4 个阶段（分镜 → 配音 → 素材 → 渲染），支持断点续传

### 智能配音

- **在线配音**：Edge TTS，50+ 自然中文音色可选
- **离线配音**：Piper TTS，完全离线无需网络，一键安装
- **智能剧情配音**：LLM 辅助分段，带情感控制，音色更自然
- **自动回退**：在线失败自动切换到离线

### 画面素材

- **AI 图片生成**：支持 OpenAI 兼容接口，可对接 DeepSeek / Moonshot / Ollama 等
- **网络素材搜索**：Pexels、Pixabay、Wikimedia Commons 三源切换
- **素材纠偏**：自动检测缺失/重复素材，智能修复与镜头级人工修正

### 素材管理与网盘导入

- **素材库**：图片/视频上传、预览、搜索、删除
- **云盘导入**：支持 WebDAV（坚果云/NextCloud）、阿里云盘、百度网盘、OneDrive

### 系统管理与监控

- **健康检查仪表盘**：一键检测存储 / Worker / FFmpeg / TTS / 网络链路
- **任务中心**：全局任务管理，支持暂停、恢复、取消、重试
- **Provider 配置**：可视化配置 LLM、生图、素材源、TTS 后端
- **子账号管理**：管理员创建和管理子账号

### 实用工具

- **视频转音频**：上传视频或粘贴链接（支持抖音 / B站 / YouTube 等）提取音轨
- **一键创建项目**：从提取的音频直接创建视频项目

### 技术栈

| 层 | 技术 |
|--|------|
| 后端框架 | Python FastAPI |
| 任务队列 | Huey + Redis |
| 数据库 | PostgreSQL |
| 前端框架 | Vue 3 + TypeScript + Element Plus |
| 构建工具 | Vite |
| TTS | Edge TTS（在线）+ Piper（离线） |
| 部署 | Docker Compose / systemd / nginx |

## 目录结构

```text
/opt/chengpian-workbench/
  apps/
    api/
    web/
  data/
  deploy/
  docs/
  scripts/
```

说明：

- `apps/api/`：FastAPI 后端、任务处理、数据库模型与业务逻辑
- `apps/web/`：Vue 3 前端
- `data/`：本机运行数据，包含素材、导出文件、缓存、日志和本机生成的密钥；不属于源码
- `deploy/`：nginx 与 systemd 模板
- `docs/`：部署与整理中的项目文档
- `scripts/`：开发/生产辅助脚本

## 数据边界

- PostgreSQL：存放项目、镜头、任务、配置、账号、Provider 元数据等结构化业务数据
- Redis：存放 Huey 任务队列消息
- `data/`：存放素材文件、导出视频和其他本机文件产物

源码与运行数据边界：

- `apps/`、`deploy/`、`docs/`、`scripts/` 是源码、部署模板和文档
- `data/`、`.env.local`、日志、缓存、构建产物、虚拟环境和依赖目录是本机运行/开发产物，不应纳入版本管理
- 生产环境建议显式设置 `CHENGPIAN_DATA_DIR` 到源码目录之外，例如 `/var/lib/chengpian`
- 密钥文件和真实环境变量只应在目标机器生成或配置，不应随代码分发

当前后端只支持 PostgreSQL 作为业务数据库。

必需环境变量：

```bash
export CHENGPIAN_DATABASE_URL=postgresql+psycopg://chengpian:password@127.0.0.1:5432/chengpian
```

## 关键文档

- 总体部署说明：`docs/deployment/deployment.md`
- Linux 部署步骤：`docs/deployment/deployment-linux.md`
- 系统架构说明：`docs/architecture/architecture.md`
- 配置项清单：`docs/operations/configuration.md`
- 前端当前路由与页面边界：`apps/web/README.md`
- 资产边界与存储约定：`docs/architecture/project-asset-boundary.md`
- 资产边界审计说明：`docs/operations/asset-audit-runbook.md`
- 历史重构计划：`docs/plans/refactor-plan.md`

## 快速定位

- 前端入口：`apps/web/src/router.ts`
- API 入口：`apps/api/app/main.py`
- 数据库设置：`apps/api/app/settings.py`
- 数据库初始化：`apps/api/app/db.py`
- systemd 模板：`deploy/systemd/`
