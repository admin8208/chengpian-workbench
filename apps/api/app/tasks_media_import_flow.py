from dataclasses import dataclass
import json


@dataclass
class ImportedAssetResult:
    asset: object | None = None
    picked_url: str = ""
    picked_provider: str = ""
    last_import_err: Exception | None = None


def import_candidate_assets(
    *,
    web_items: list,
    keep_running: bool,
    scene_deadline: float,
    media_total_deadline: float,
    now_time,
    wait_if_job_paused,
    target_job_id: int,
    url_hash,
    used_hashes: set[str],
    title_key,
    used_title_keys: set[str],
    recent_providers: list[str],
    import_to_project,
    import_request_cls,
    project_id: int,
) -> ImportedAssetResult:
    result = ImportedAssetResult()
    for item in (web_items or [])[:12]:
        wait_if_job_paused(target_job_id)
        if now_time() >= scene_deadline or now_time() >= media_total_deadline:
            break
        try:
            url_hash_value = url_hash(str(getattr(item, "file_url", "") or ""))
            if url_hash_value and url_hash_value in used_hashes:
                continue
            title_key_value = title_key(str(getattr(item, "title", "") or ""))
            if title_key_value and title_key_value in used_title_keys:
                continue
            provider = str(getattr(item, "provider", "") or "")
            if recent_providers and len(recent_providers) >= 2 and recent_providers[-1] == provider == recent_providers[-2]:
                continue
            asset = import_to_project(
                import_request_cls(
                    provider=item.provider,
                    kind=item.kind,
                    title=item.title,
                    page_url=item.page_url,
                    file_url=item.file_url,
                    width=getattr(item, "width", None),
                    height=getattr(item, "height", None),
                    duration_sec=getattr(item, "duration_sec", None),
                    thumb_url=item.thumb_url,
                    preview_url=item.preview_url,
                    license_short=item.license_short,
                    license_url=item.license_url,
                    author=item.author,
                    attribution=item.attribution,
                ),
                project_id=int(project_id),
                max_bytes_override=(40 * 1024 * 1024 if keep_running and str(getattr(item, "kind", "") or "") == "video" else None),
                connect_timeout_s=(8 if keep_running else 20),
                read_timeout_s=(35 if keep_running else 120),
            )
            result.asset = asset
            result.picked_url = str(getattr(item, "file_url", "") or "").strip()
            result.picked_provider = provider
            break
        except Exception as exc:
            result.last_import_err = exc
            continue
    return result


@dataclass
class ImportedAssetApplyResult:
    selected_as_main: bool
    aid: int
    meta_a: dict


def apply_imported_asset(
    *,
    asset,
    picked_url: str,
    picked_provider: str,
    picked_main_candidate: bool,
    main_candidate_file_url: str,
    main_candidate_duration_sec: float,
    expected_dur: float,
    scene_idx: int,
    scene_id: int,
    query_used: str,
    best_conf: float,
    best_reason: str,
    set_scene_asset,
    main_clip_window,
    asset_title_key,
    asset_duration_sec,
    url_hash,
    used_hashes: set[str],
    used_title_keys: set[str],
    recent_providers: list[str],
    used_asset_types: list[str],
    used_providers: list[str],
) -> ImportedAssetApplyResult:
    if picked_url:
        hash_value = url_hash(picked_url)
        if hash_value:
            used_hashes.add(hash_value)

    meta_a = {}
    try:
        meta_a = json.loads(getattr(asset, "meta_json", "{}") or "{}")
        if not isinstance(meta_a, dict):
            meta_a = {}
    except Exception:
        meta_a = {}

    title_key_value = asset_title_key(asset, meta_a)
    if title_key_value:
        used_title_keys.add(title_key_value)
    recent_providers.append(str(picked_provider or ""))
    if len(recent_providers) > 4:
        recent_providers[:] = recent_providers[-4:]

    selected_as_main = bool(
        picked_main_candidate and main_candidate_file_url and picked_url == main_candidate_file_url and str(getattr(asset, "kind", "") or "").lower() == "video"
    )

    main_seg = (None, None)
    if selected_as_main:
        main_seg = main_clip_window(duration_sec=float(main_candidate_duration_sec or 0.0), expected_dur=float(expected_dur or 0.0), scene_idx=scene_idx)

    set_scene_asset(
        scene_id=scene_id,
        asset_id=int(asset.id),
        query_used=query_used,
        best_conf=float(best_conf or 0.0),
        best_reason=best_reason,
        source_label=str(picked_provider or "imported"),
        render_role="main" if selected_as_main else "support",
        segment_start=main_seg[0],
        segment_end=main_seg[1],
    )

    try:
        asset_kind = str(getattr(asset, "kind", "") or "").lower()
        asset_provider = str(picked_provider or "").lower()
        if asset_kind:
            used_asset_types.append(asset_kind)
            if len(used_asset_types) > 3:
                used_asset_types[:] = used_asset_types[-3:]
        if asset_provider:
            used_providers.append(asset_provider)
            if len(used_providers) > 3:
                used_providers[:] = used_providers[-3:]
    except Exception:
        pass

    return ImportedAssetApplyResult(selected_as_main=selected_as_main, aid=int(asset.id), meta_a=meta_a)
