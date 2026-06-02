# Configuration Reference

这份文档整理当前代码里实际生效的主要配置项，重点覆盖：

- 必填环境变量
- API / Worker 运行参数
- 路径与静态资源参数
- 网络代理与请求超时
- 清理与保留策略
- 部分高级调优项

说明：

- 配置名称统一以 `CHENGPIAN_*` 为主
- 在线 TTS 可通过 `CHENGPIAN_TTS_PROXY` 单独配置代理
- 默认值与行为均以当前代码为准

## 配置来源

当前配置主要来自这些位置：

- `apps/api/app/settings.py`
- `apps/api/run_api.py`
- `apps/api/app/main.py`
- `apps/api/app/api_common.py`
- `apps/api/app/tasks.py`
- `apps/api/app/llm_client.py`
- `apps/api/app/modules/tts/runtime.py`
- `apps/api/app/http_client.py`
- `apps/api/app/proxy_settings.py`
- `apps/api/app/modules/tts/offline.py`

此外，`settings.py` 会按顺序尝试加载仓库根目录下的：

- `.env.local`
- `.env.prod`

如果这些文件存在，会在进程启动时被读取。

## 必填配置

### `CHENGPIAN_DATABASE_URL`

- 是否必填：是
- 默认值：无
- 作用：业务数据库连接串
- 当前要求：必须是 PostgreSQL 连接串

支持前缀：

- `postgresql://`
- `postgresql+psycopg://`
- `postgresql+psycopg2://`

示例：

```bash
export CHENGPIAN_DATABASE_URL=postgresql+psycopg://chengpian:password@127.0.0.1:5432/chengpian
```

如果未设置，后端会直接启动失败。

## 基础运行配置

### `CHENGPIAN_DATA_DIR`

- 默认值：`<repo>/data`
- 作用：本地运行数据根目录
- 影响内容：
  - `assets`
  - `exports`
  - `huey`
  - 项目级文件与缓存

### `CHENGPIAN_WEB_DIST_DIR`

- 默认值：`<repo>/apps/web/dist`
- 作用：前端构建产物目录
- 用途：API 启动后会把 SPA 从这里挂到 `/`

## API / Worker 运行配置

### `CHENGPIAN_API_HOST`

- 默认值：`127.0.0.1`
- 作用：API 监听地址
- 使用位置：`apps/api/run_api.py`

### `CHENGPIAN_API_PORT`

- 默认值：`8000`
- 生产脚本默认：`8010`
- 作用：API 监听端口

### `CHENGPIAN_RELOAD`

- 默认值：`1`
- 在生产启动脚本中的默认值：`0`
- 作用：控制 `uvicorn` 是否开启热重载
- 取值规则：`0/false/no` 视为关闭，其余视为开启

### `CHENGPIAN_WORKER_COUNT`

- 默认值：`1`
- 作用：Huey worker 并发 worker 数
- 下限：至少为 `1`

### `CHENGPIAN_REDIS_URL`

- 默认值：`redis://127.0.0.1:6379/0`
- 作用：Huey / Worker 使用的 Redis 队列连接串
- 使用位置：`apps/api/app/settings.py`、`apps/api/app/huey_app.py`

### `CHENGPIAN_EXPOSE_DOCS`

- 默认值：`0`
- 作用：是否暴露 FastAPI 文档
- 打开后会暴露：
  - `/docs`
  - `/redoc`
  - `/openapi.json`

## Web / 安全相关配置

### `CHENGPIAN_CORS`

- 默认值：空
- 作用：覆盖 API 的 CORS 白名单
- 格式：英文逗号分隔

若未设置，默认允许：

- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `http://localhost:5188`
- `http://127.0.0.1:5188`

注意：

- `*` 会被过滤掉，不会直接作为允许来源使用

### `CHENGPIAN_COOKIE_SECURE`

- 默认值：`auto`
- 可选值：`auto` / `true` / `false`
- 作用：控制认证 Cookie 的 secure 策略

## 网络代理与请求标识

### `CHENGPIAN_TTS_PROXY`

- 默认值：空
- 作用：仅指定在线 TTS 出网代理
- 使用位置：Edge 在线配音、在线配音连通性检查

### `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY`

- 是否支持：普通后端 HTTP 客户端默认不读取
- 作用：避免 LLM、生图、素材搜索等能力误继承本机代理；如在线 TTS 需要代理，请使用 `CHENGPIAN_TTS_PROXY`

### `CHENGPIAN_USER_AGENT`

- 默认值：空
- 作用：覆盖后端发出的 HTTP 请求 User-Agent

### `CHENGPIAN_OFFICIAL_USER_AGENT`

- 默认值：空
- 作用：覆盖系统内置默认 User-Agent 模板
- 若未设置，代码内置默认值为：
  - `ChengpianWorkbench/0.1 (+https://chengpian.local; contact: support@chengpian.local)`

## 超时与请求调优

### `CHENGPIAN_LLM_TIMEOUT_S`

- 默认值：由调用方传入的默认超时时间决定，最小不低于 `15`
- 作用：控制 LLM 请求的默认超时
- 使用位置：`apps/api/app/llm_client.py`

### `CHENGPIAN_TTS_TIMEOUT_S`

- 默认值：`120`
- 作用：控制 Edge TTS 生成音频/字幕时的超时秒数

### `CHENGPIAN_IMAGE_TIMEOUT_S`

- 默认值：`600`
- 最小值：`20`
- 作用：控制生图请求单次超时、详细提示词生图超时、生成图 URL 下载超时；同时影响“设置 -> 生图模型”里的测试生图和主流程正式生图

### `CHENGPIAN_IMAGE_ATTEMPTS`

- 默认值：`2`
- 范围：`1` 到 `4`
- 作用：控制生图失败后的最大重试次数

## TTS 与缓存相关配置

### `CHENGPIAN_TTS_CACHE_MAX_AGE_DAYS`

- 默认值：`7`
- 作用：TTS 缓存文件最大保留天数

### `CHENGPIAN_TTS_CACHE_MAX_SIZE_GB`

- 默认值：`5.0`
- 作用：TTS 缓存总大小上限（GB）

### `CHENGPIAN_KEEP_TTS_PREVIEWS`

- 默认值：`3`
- 范围：`0` 到 `30`
- 作用：保留最近多少个 TTS 试听文件
- 影响目录：`data/exports/tts_previews/`

### `CHENGPIAN_PIPER_BIN_URL`

- 默认值：空
- 作用：覆盖 Piper 离线 TTS 引擎的下载地址
- 使用场景：
  - 官方源访问不稳定
  - 需要固定公司内镜像源

## 清理与保留策略

### `CHENGPIAN_TEMP_FILE_MAX_AGE_HOURS`

- 默认值：`24`
- 作用：临时文件最大保留时长

### `CHENGPIAN_CLEANUP_INTERVAL_HOURS`

- 默认值：`6`
- 作用：自动清理任务的执行间隔参考值

### `CHENGPIAN_AUTO_CLEANUP_ENABLED`

- 默认值：`true`
- 作用：是否启用自动清理
- 判定为开启的值：`true` / `1` / `yes`

### `CHENGPIAN_KEEP_EXPORT_CANDIDATES`

- 默认值：`0`
- 范围：`0` 到 `200`
- 作用：每个项目保留多少个导出候选视频

### `CHENGPIAN_KEEP_EXPORT_HISTORY`

- 默认值：`0`
- 范围：`0` 到 `200`
- 作用：每个项目保留多少个历史导出视频

### `CHENGPIAN_KEEP_GENERATED_TTS`

- 默认值：`1`
- 范围：`0` 到 `50`
- 作用：每个项目保留多少份系统自动生成的语音/字幕产物

## 推荐配置分层

### 最小必配

```bash
export CHENGPIAN_DATABASE_URL=postgresql+psycopg://chengpian:password@127.0.0.1:5432/chengpian
```

### 单机生产常用配置

```bash
export CHENGPIAN_API_HOST=127.0.0.1
export CHENGPIAN_API_PORT=8010
export CHENGPIAN_RELOAD=0
export CHENGPIAN_EXPOSE_DOCS=0
export CHENGPIAN_DATABASE_URL=postgresql+psycopg://chengpian:password@127.0.0.1:5432/chengpian
export CHENGPIAN_DATA_DIR=/opt/chengpian-workbench/data
export CHENGPIAN_WEB_DIST_DIR=/opt/chengpian-workbench/apps/web/dist
export CHENGPIAN_WORKER_COUNT=1
```

### 在线 TTS 需要代理时

```bash
export CHENGPIAN_TTS_PROXY=http://127.0.0.1:7890
```

## 推荐维护方式

### systemd 部署

建议把配置集中写到：

- `deploy/systemd/chengpian.env`

可从示例文件复制：

```bash
cp /opt/chengpian-workbench/deploy/systemd/chengpian.env.example /opt/chengpian-workbench/deploy/systemd/chengpian.env
chmod 600 /opt/chengpian-workbench/deploy/systemd/chengpian.env
```

### 本地开发

建议使用：

- `.env.local`

这样可以避免把本机配置写死到脚本或 service 模板里。

## 说明与限制

1. 文档只整理当前代码中明确读取的主要配置项。
2. 若未来新增配置，应同步更新本文件与部署文档。
3. TTS 代理仅影响在线 TTS；LLM、生图、素材搜索、视频导入等普通后端 HTTP 请求默认不继承本机代理。
