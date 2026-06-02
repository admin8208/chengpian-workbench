# Web App

`apps/web` 是当前产品的前端实现，基于 Vue 3 + Vite。

这份文档面向前端开发者，重点说明当前真实路由、页面职责和产品边界。

## 本地开发

```bash
npm install
npm run dev
```

默认开发地址：`http://127.0.0.1:5173`

构建：

```bash
npm run build
```

## 当前路由

- `/` -> `/creator/ai`
- `/login`
- `/creator`（兼容重定向到 `/creator/ai`）
- `/creator/ai`
- `/creator/network`
- `/p/mix/:id`
- `/p/ai/:id`
- `/p/network/:id`
- `/recent`
- `/library`
- `/video-audio`
- `/jobs`
- `/settings`
- `/health`

兼容跳转：

- `/creator` 重定向到 `/creator/ai`，保留旧入口链接
- `/p/mix/:id` 通过 `ProjectModeResolverView` 按项目素材模式分流到 `/p/ai/:id` 或 `/p/network/:id`

## 页面职责

### `src/features/project-workbench/pages/AiProjectView.vue`

- 智能创作项目工作台入口
- 复用 `project-workbench` 下的核心状态、流程和面板

### `src/views/creator/ai/AiCreatorCenterView.vue`

- 智能创作首页入口
- 创建智能生图素材模式项目

### `src/views/creator/network/NetworkCreatorCenterView.vue`

- 素材创作首页入口
- 创建网络素材模式项目

### `src/features/project-workbench/pages/NetworkProjectView.vue`

- 素材创作项目工作台
- 围绕网络素材检索、绑定和镜头修正展示项目阶段

### `src/views/project/RecentProjectsView.vue`

- 项目中心
- 查看项目当前阶段、失败提示和是否已有成片
- 打开项目 / 打开成片
- 批量选择并删除可删除项目

### `src/views/system/LibraryView.vue`

- 素材库管理
- 上传图片 / 视频
- 搜索与删除素材
- 从 WebDAV / 阿里云盘 / 百度网盘 / OneDrive 浏览并导入素材

### `src/views/system/SettingsView.vue`

- 创作前准备区
- 大模型快速配置
- 素材来源配置
- 配音后端与离线安装

### `src/views/system/HealthView.vue`

- 本机运行状态检查
- 查看 `storage` / `ffmpeg` / `edge_tts` / `offline_tts`
- 判断当前环境是否可以直接出片

### `src/views/auth/LoginView.vue`

- 登录页
- 首次启用时初始化管理员账号
- 未登录时作为所有受保护页面的前置入口

## 关键文件

- `src/router.ts`
  - 路由定义与登录守卫
- `src/App.vue`
  - 应用壳、侧边导航、顶栏
- `src/api/index.ts`
  - 前端 API 聚合层
- `src/api/types.ts`
  - 前端 API 类型定义
- `src/api/*.ts`
  - 按业务域拆分的 API 调用模块
- `src/features/project-workbench/`
  - 当前项目工作台主实现，含 `core`、`flow`、`scene`、`pages`
- `src/components/project/`
  - 项目工作台复用组件

## 当前状态管理方式

- 当前没有全局 store
- 页面普遍采用：
  - `ref` / `computed`
  - `watch`
  - 直接调用 `src/api/index.ts` 聚合出的 `api`
- 项目页的大部分状态和流程判断当前集中在 `src/features/project-workbench/`
- 路由进入前会先调用 `api.authStatus()` 做登录和初始化判断

这意味着：

- 页面级逻辑比较直观
- 但跨页复用的状态映射和术语容易重复实现

## 当前产品边界

### 前端已明确接入

- 登录与管理员初始化
  - 智能创作 / 素材创作创建项目
  - 项目主流程
- 分镜素材纠偏
- 最终成片预览与查看 final
- 项目中心
- 素材库
- 设置和健康检查
- 大模型 / 生图 / 素材来源测试
- 本机 / 在线配音试听

### 后端/API 已有，但前端未完整暴露

以下能力在 `src/api/` 已定义，或后端已有接口，但当前主界面没有完整产品化入口：

- 项目级上传：
  - 角色图
  - BGM
  - 配音文件
  - 字幕文件
- 独立任务：
  - `storyboard`
  - `rewrite`
  - `render-batch`
- 增强能力：
  - A/B hooks / variants
  - compliance
  - doctor mix smoke

### 遗留或当前未接入

- 当前未保留独立旧入口页面组件，旧入口链接由 `src/router.ts` 的兼容跳转承接

## 术语约定

- `文案创作`：指从标题 / 原文出发，经脚本、分镜、配音、素材、渲染得到成片的流程，对应 `/creator/ai` 或 `/creator/network`

## 文档维护建议

如果后续修改 README 或产品说明，建议始终区分三层：

1. Web 当前已接入
2. API 已支持但前端未完整暴露
3. 已下线或遗留

这样可以减少文档和真实代码再次漂移。
