# Refactor Plan

## Goal

This project should be positioned as a video creation workbench, not a metaverse product.

Primary product lines:

- Script-to-video creation
- Movie/TV clip remix

Core production chain:

- Topic and source input
- Full spoken script generation
- Storyboard and media binding
- Voice and subtitle generation
- Final video rendering

## Current Problems

- Historical product naming and structure notes in this file may be outdated and should be refreshed when structure changes again
- User-facing terminology mixes product language and engineering language
- Main creation flow and remix flow are not clearly separated
- Settings page still exposes too much implementation detail
- Media autofill, TTS, and render behavior contain legacy fallback logic
- Deployment shape is still development-oriented

## Refactor Principles

- Refactor in place; do not rewrite the whole project into a new app yet
- Prioritize user-facing clarity before deep internal cleanup
- Keep one canonical pipeline for creation: script -> storyboard -> voice -> media -> final
- Unify all online capabilities under one proxy/network layer
- Split by business domain, not by historical file growth

## Target Frontend Structure

```text
apps/web/src/views/
  creator/
    CreatorCenterView.vue
    MixProjectView.vue
  remix/
    RemixView.vue
  project/
    RecentProjectsView.vue
  system/
    SettingsView.vue
    HealthView.vue
    JobsView.vue
  shared/
    NotFoundView.vue
```

Later target component grouping:

```text
apps/web/src/components/
  project/
  media/
  tts/
  remix/
  system/
```

## Target Backend Structure

Keep current app runnable, but gradually converge modules toward:

```text
apps/api/app/modules/
  creator/
  remix/
  media/
  render/
  tts/
  system/
```

## Execution Phases

### Phase 1: Product and Naming Cleanup

- Replace legacy branding with `成片工作台` and keep all user-facing terminology aligned to creation and remix workflows
- Unify UI wording for creation, remix, TTS, and render
- Keep current routes working while improving labels

### Phase 2: Main Creation Flow Cleanup

- Keep full spoken script as canonical text source
- Keep storyboard, subtitle, and voice aligned to the same text chain
- Continue reducing repeated media and misleading task states

### Phase 3: Remix Flow Isolation

- Keep remix page focused on movie/TV clip remix only
- Keep recommendation logic film/TV oriented
- Avoid leaking creator workflow concepts into remix flow

### Phase 4: Settings and System Cleanup

- Translate technical terms into user language
- Keep advanced maintenance collapsed by default
- Keep online capability checks explicit about backend-machine networking

### Phase 5: Directory-Level Reorganization

- Move views into domain folders
- Update imports and router paths
- Only after structure stabilizes, consider deeper component/module moves

## Deployment Modes

### Current Development Mode

- Web: Vite dev server
- API: FastAPI
- Worker: Huey worker
- Database: PostgreSQL
- Runtime files: local `data/`

### Short-Term Production Mode

- Built static frontend
- API service
- Worker service
- Shared data directory mount

### Long-Term Production Mode

- Static frontend hosting
- API and worker split
- PostgreSQL remains the business database
- Shared storage, stronger backup, and observability improvements as concurrency grows

## Immediate Steps

1. Create this refactor plan document
2. Reorganize frontend view files by domain
3. Keep router imports aligned to the new structure
4. Rebuild and verify the app still works
5. Continue domain-by-domain cleanup after structure is stable

## Current Completed Status

Completed in-place refactor rounds:

- Frontend views reorganized by business domain:
  - `views/creator`
  - `views/project`
  - `views/system`
  - `views/shared`
- Frontend components reorganized by business domain:
  - `components/project`
  - `components/system`
  - `components/shared`
- Global branding and key user-facing terms aligned to `成片工作台`
- Backend TTS implementation reorganized into `app/modules/tts`
- Backend media implementation reorganized into `app/modules/media`
- Compatibility re-export files kept at legacy top-level paths to avoid breaking current runtime

## Next Refactor Focus

- Continue reducing direct usage of legacy compatibility files
- Move more backend domain logic behind module-local service boundaries
- Clean up old naming inside job kinds, summaries, and diagnostics where it still leaks historical concepts
