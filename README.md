# 成片工作台

`成片工作台` 是一个面向单机 / 私有化部署场景的视频生产工作台。

当前产品主线聚焦于文案创作：从项目标题、原文、脚本/分镜、配音字幕、素材补齐到最终成片输出。

当前默认运行形态：

- 前端构建产物：`apps/web/dist`
- API 服务：`apps/api/run_api.py`
- Worker 服务：`apps/api/run_worker.py`
- 业务数据库：PostgreSQL
- 任务队列：Redis（Huey 后端）
- 本地运行目录：`data/`

## 快速开始

### Docker 一键启动（推荐）

需安装 [Docker](https://docker.com/products/docker-desktop/) 和 Docker Compose。

```bash
# 1. 克隆仓库
git clone https://github.com/admin8208/chengpian-workbench.git
cd chengpian-workbench

# 2. 下载多音字模型（约 160MB，仅首次）
bash scripts/setup/download_g2pw_model.sh

# 3. 启动全部服务
docker compose up -d

# 4. 打开浏览器访问 http://localhost:8010
#    首次使用会自动引导创建管理员账号
```

> 数据库密码可通过 CHENGPIAN_DB_PASSWORD 环境变量自定义，默认为 chengpian。

### Windows 手动部署

前置要求：Python 3.10+、Node.js 18+、PostgreSQL 16、Redis 7、FFmpeg

```powershell
git clone https://github.com/admin8208/chengpian-workbench.git
cd chengpian-workbench
.\scripts\setup\download_g2pw_model.ps1
copy .env.example .env.local
pip install -r apps/api/requirements.txt
cd apps/web
npm install
npm run build
cd ../..
python apps/api/run_worker.py
python apps/api/run_api.py
```

### Linux 手动部署

```bash
git clone https://github.com/admin8208/chengpian-workbench.git
cd chengpian-workbench
bash scripts/setup/download_g2pw_model.sh
cp .env.example .env.local
pip install -r apps/api/requirements.txt
cd apps/web
npm install
npm run build
cd ../..
python apps/api/run_worker.py &
python apps/api/run_api.py
```


## 核心能力

- 创建文案创作项目并选择赛道 / 素材模式
- 生成视频、继续生成、重跑全部
- 分镜素材纠偏与镜头级人工修正
- 在线 / 离线配音与字幕预览
- 最终成片渲染与历史输出管理
- 素材库管理与网盘导入
- 大模型、生图、素材源、TTS 配置与健康检查
- 管理员初始化、登录、子账号管理

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

## 当前状态说明

- 当前默认部署形态仍然是单机
- 当前业务数据库已经切换到 PostgreSQL
- `data/` 不再承担业务数据库职责
- 前端 README 已按当前真实路由更新
- 生产环境下不要以 `root` 手工启动 API / Worker，否则 `data/` 可能出现 `root:root` 文件并导致项目删除失败

## 术语约定

- `文案创作`：指从标题 / 原文出发，经脚本、分镜、配音、素材、渲染得到成片的流程，对应 `/creator/ai` 或 `/creator/network`
