# 资产边界审计运行说明

## 目的

用于检查以下问题：

1. 公共素材库记录是否存在文件缺失
2. 公共素材库是否混入历史项目导入痕迹
3. 项目私有资产是否错误写入 `library/...` 路径
4. 是否仍有 scene 直接绑定 `library` 资产

## 脚本位置

`apps/api/scripts/audit_asset_boundaries.py`

## 执行命令

```bash
/opt/chengpian-workbench/apps/api/.venv/bin/python /opt/chengpian-workbench/apps/api/scripts/audit_asset_boundaries.py
```

## 输出重点

### `summary`

1. `library_asset_count`
2. `invalid_library_asset_count`
3. `suspicious_library_asset_count`
4. `directly_bound_library_asset_count`
5. `project_assets_in_library_path_count`

### 判读建议

1. `invalid_library_asset_count > 0`
   说明公共素材库中仍有数据库记录存在但物理文件缺失的脏数据。

2. `directly_bound_library_asset_count > 0`
   说明仍存在 scene 直接绑定公共素材库资产，需要立即排查绑定入口。

3. `project_assets_in_library_path_count > 0`
   说明项目私有资产被错误写进了 `library/...` 路径，需要修复写入链路。

4. `suspicious_library_asset_count > 0`
   不一定是错误。
   这类记录只是提示：公共素材库中有来自在线来源的素材，需结合业务确认这些是用户主动沉淀的公共素材，还是历史项目误导入。

## 建议巡检频率

1. 每次发布涉及素材导入逻辑的改动后执行一次
2. 每周至少执行一次
3. 用户反馈“素材库异常膨胀”“项目删不干净”时立即执行

## 配套健康检查

建议同时查看：

1. `/api/health` 中的 `worker`
2. `/api/health` 中的 `queue`

如果项目长期显示排队中，先确认 worker 在线，再执行本审计脚本排除素材边界问题。
