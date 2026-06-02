import type { Job } from '../../../api'
import { parseJobPayload as parseJobPayloadBase } from '../../../utils/jobDiagnostics'

export function parseJobPayload(job: Job | null | undefined) {
  return parseJobPayloadBase(job as Job)
}

export async function refreshProjectTaskState(options: {
  refreshSummaryOnly: () => Promise<void>
  loadProjectJobs: () => Promise<void>
}) {
  await Promise.all([options.refreshSummaryOnly(), options.loadProjectJobs()])
}

export async function handleNoFinalNotice(options: {
  route: any
  router: any
  info: { value: string }
}) {
  const notice = String((options.route.query as any)?.notice || '').trim().toLowerCase()
  if (notice !== 'no_final') return
  options.info.value = '还没有最终成片文件。你可以先点"生成视频"，系统会自动推进并生成预览。'
  const query: any = { ...(options.route.query as any) }
  delete query.notice
  await options.router.replace({ query })
}
