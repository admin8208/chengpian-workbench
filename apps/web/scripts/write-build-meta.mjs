import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const webRoot = resolve(__dirname, '..')
const distDir = resolve(webRoot, 'dist')
const metaPath = resolve(distDir, 'build-meta.json')

function git(args) {
  try {
    return execFileSync('git', args, {
      cwd: webRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim()
  } catch {
    return ''
  }
}

const meta = {
  built_at: new Date().toISOString(),
  git_commit: git(['rev-parse', '--short', 'HEAD']) || null,
  git_branch: git(['rev-parse', '--abbrev-ref', 'HEAD']) || null,
  node_env: process.env.NODE_ENV || 'production',
}

mkdirSync(distDir, { recursive: true })
writeFileSync(metaPath, `${JSON.stringify(meta, null, 2)}\n`, 'utf8')
console.log(`[build-meta] wrote ${metaPath}`)
