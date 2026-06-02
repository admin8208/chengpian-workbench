# System Architecture

## 概览

`成片工作台` 当前采用单机部署架构，但运行时已经明确分成几个独立职责层：

- Vue 3 前端：提供智能创作、素材创作、项目工作台、素材库、设置、健康检查、登录等页面
- FastAPI API：提供业务接口、认证守卫、静态文件挂载、数据库初始化入口
- Huey Worker：消费长任务，执行分镜、配音、渲染、清理等后台任务
- PostgreSQL：存放结构化业务数据
- Redis：存放 Huey 任务队列消息
- 本地 `data/` 目录：存放素材、导出、缓存和临时文件

当前默认运行方式不是前后端完全分离，而是 API 同时提供：

- `/api/*` 业务接口
- `/assets/*` 素材静态访问
- `/exports/*` 导出结果访问
- `/projects/*` 项目公共文件访问
- 前端 SPA 页面入口

## 运行拓扑

```text
浏览器
  |
  v
nginx
  |
  v
FastAPI API  ----------------------> PostgreSQL
  |     +-------------------------> data/assets
  |     +-------------------------> data/exports
  |     +-------------------------> data/projects
  |
  +----> Redis Queue <--------------> Worker
                                        |
                                        +--> LLM / TTS / 生图 / 在线素材 / 视频导入等外部能力
```

## 代码入口

### 前端

- 路由入口：`apps/web/src/router.ts`
- 应用壳：`apps/web/src/App.vue`
- 当前主要页面：
  - `apps/web/src/views/creator/ai/AiCreatorCenterView.vue`
  - `apps/web/src/views/creator/network/NetworkCreatorCenterView.vue`
  - `apps/web/src/features/project-workbench/pages/AiProjectView.vue`
  - `apps/web/src/features/project-workbench/pages/NetworkProjectView.vue`
  - `apps/web/src/views/project/RecentProjectsView.vue`
  - `apps/web/src/views/system/LibraryView.vue`
  - `apps/web/src/views/system/SettingsView.vue`
  - `apps/web/src/views/system/HealthView.vue`
  - `apps/web/src/views/auth/LoginView.vue`

### API

- 启动入口：`apps/api/run_api.py`
- 应用装配：`apps/api/app/main.py`
- 数据库初始化：`apps/api/app/db.py`
- 配置读取：`apps/api/app/settings.py`

### Worker

- 启动入口：`apps/api/run_worker.py`
- Huey 注册入口：`apps/api/app/worker.py`
- 任务定义：`apps/api/app/tasks.py`
- 队列实例：`apps/api/app/huey_app.py`

## API 层职责

`apps/api/app/main.py` 当前做了几件核心事情：

1. 创建 FastAPI 应用
2. 根据 `CHENGPIAN_EXPOSE_DOCS` 决定是否暴露 OpenAPI 文档
3. 通过 `lifespan` 执行数据库初始化、seed 和 provider 规范化
4. 注册 CORS
5. 挂载认证中间件 `auth_guard`
6. 按领域注册 router
7. 挂载前端 SPA 和静态目录

当前已接入的主要 router 包括：

- `auth`
- `project`
- `project_ops`
- `scene`
- `job`
- `asset`
- `cloud`
- `tts`
- `media`
- `llm`
- `image`
- `system`
- `channel`

这说明 API 既承担业务编排，也承担一部分“工作台型产品”的系统能力暴露。

## 前端架构

前端是 Vue 3 + Vite 单页应用，当前特点是：

- 没有全局 store 作为统一状态中心
- 主要依赖页面级 `ref / computed / watch`
- 页面进入前通过 `api.authStatus()` 做登录态和初始化检查
- 项目主工作台当前主要集中在 `apps/web/src/features/project-workbench/`

当前真实路由以 `apps/web/src/router.ts` 为准，核心用户流如下：

1. 未登录时进入 `/login`
2. 登录后默认进入 `/creator/ai`
3. 创建项目后进入 `/p/mix/:id`
4. 通过 `/recent` 管理项目，通过 `/library` 管理公共素材
5. 通过 `/settings` 与 `/health` 处理环境配置和运行健康检查

## Worker 与任务系统

### Worker 启动方式

`apps/api/run_worker.py` 在真正启动 Huey consumer 之前，会先做两件事：

1. 运行 `preflight`
2. 执行 `init_db()`，确保 schema 与迁移先完成

随后启动：

- `app.worker.huey`
- worker 数量来自 `CHENGPIAN_WORKER_COUNT`

### 队列实现

当前 Huey 使用的是 `RedisHuey`：

- 定义位置：`apps/api/app/huey_app.py`
- Redis 连接配置：`CHENGPIAN_REDIS_URL`

这意味着：

- 结构化业务数据已经迁到 PostgreSQL
- 后台任务队列由 Redis 负责
- API 和 Worker 只需要共享 PostgreSQL 与 Redis，不再依赖本地队列目录

### 任务类型

当前任务并不只是“渲染”一种，实际还包括：

- 分镜生成
- 改写
- 配音 / 字幕准备
- 最终渲染
- 离线音色安装
- 自动清理

任务定义主要集中在：

- `apps/api/app/tasks.py`
- `apps/api/app/tasks_tts_install.py`
- `apps/api/app/tasks_cleanup.py`

### 任务状态与恢复

任务元数据保存在 PostgreSQL 的 `Job` 表中，代码见：

- `apps/api/app/models.py`
- `apps/api/app/jobs.py`

当前系统支持：

- `queued`
- `running`
- `paused`
- `done`
- `failed`
- `cancelled`

`apps/api/app/jobs.py` 当前实现了：

- 入队校验
- 任务 payload 更新
- 暂停/取消协作控制
- worker lease / heartbeat
- worker 启动恢复遗留 running 任务

## 数据层边界

### PostgreSQL 存什么

当前业务数据库保存的主要是结构化数据：

- `Project`
- `Scene`
- `Job`
- `Asset`
- `AppConfig`
- `UserAccount`
- `LlmProvider`
- `ImageProvider`
- 各类 Secret / MediaSecret

定义位置：`apps/api/app/models.py`

### `data/` 存什么

根据 `apps/api/app/settings.py` 与相关路径工具，当前本地运行目录主要包括：

- `data/assets/`
  - 素材库图片 / 视频
  - 项目音频
  - 项目字幕
  - TTS 缓存
  - 项目级导入素材
- `data/exports/`
  - `final.mp4`
  - 历史导出
  - 预览输出
  - 二创结果

### 为什么会同时存在 PostgreSQL 和本地 `data/`

因为系统的数据分成两类：

1. 结构化业务数据
- 需要事务、查询、关系、状态更新
- 由 PostgreSQL 负责

2. 大文件与机器本地产物
- 图片、音频、视频、临时输出
- 由本地文件系统负责

3. 短生命周期任务消息
- 由 Redis 队列负责

这是当前单机部署最现实的组合方式。

## 静态文件与 SPA 挂载

`apps/api/app/web_static.py` 当前负责挂载：

- `/assets` -> `settings.assets_dir`
- `/exports` -> `settings.exports_dir`
- `/projects` -> 项目公共文件目录

`apps/api/app/main.py` 最后还会把前端 `dist` 挂到 `/`，形成 SPA 回退路由。

这意味着：

- 浏览器访问项目预览、导出视频、素材文件时，不一定走独立文件服务
- 很多静态内容是由 FastAPI 直接暴露路径提供的

## 配置与环境变量

关键配置集中在 `apps/api/app/settings.py`。

当前最重要的环境变量包括：

- `CHENGPIAN_DATABASE_URL`
- `CHENGPIAN_REDIS_URL`
- `CHENGPIAN_DATA_DIR`
- `CHENGPIAN_WEB_DIST_DIR`
- `CHENGPIAN_API_HOST`
- `CHENGPIAN_API_PORT`
- `CHENGPIAN_WORKER_COUNT`
- `CHENGPIAN_EXPOSE_DOCS`
- `CHENGPIAN_CORS`

其中最关键的是：

- `CHENGPIAN_DATABASE_URL` 必填
- `CHENGPIAN_REDIS_URL` 必填（默认可用 `redis://127.0.0.1:6379/0`）
- 当前业务库只接受 PostgreSQL 连接串

## 外部依赖边界

这个系统的“在线能力”并不是浏览器直接调用，而主要由后端机器发起。典型包括：

- LLM Provider
- 生图 Provider
- 在线 TTS
- Pexels / Pixabay 等素材源
- 抖音或其他视频导入解析

所以网络问题通常要看：

- API / Worker 所在机器能否访问外网
- 代理是否正确配置到服务进程

而不是只看浏览器本身是否能联网。

## 当前架构优点

- 单机部署简单，适合私有化和小团队使用
- 业务数据与大文件已经分层，不再混用 SQLite 存业务主数据
- API 与 Worker 分离，长任务不会直接阻塞 Web 请求
- 前端、API、Worker、数据目录的职责边界已经比较清晰

## 当前架构限制

- 当前 Redis 队列已解决单机 API/worker 的文件锁问题，但如未来多机扩展仍需统一 Redis 运维与监控
- `data/` 目录是单机共享前提，多机时需要共享存储策略
- 前端项目工作台状态仍较重，产品层复杂度主要集中在单页
- 静态文件大量由 API 直接挂载，后续大规模媒体访问时可能需要再拆分

## 后续演进建议

如果后续继续演进，优先级建议如下：

1. 稳定当前单机架构，不急于分布式化
2. 继续收敛前端项目工作台复杂度
3. 为 Redis 队列补充更完善的可观测性与告警
4. 在媒体访问量增长后，再考虑静态文件服务与共享存储拆分
5. 强化 PostgreSQL 的备份、连接池、监控与运维文档
