import type { AuthStatus } from './types'
import { authApi } from './auth'
import type { HttpInit } from './http'

const AUTH_CACHE_TTL_MS = 10_000

type CacheEntry = {
  value: AuthStatus
  expiresAt: number
}

let authCache: CacheEntry | null = null
let authPending: Promise<AuthStatus> | null = null

function isCacheFresh(entry: CacheEntry | null) {
  return Boolean(entry && entry.expiresAt > Date.now())
}

export function readCachedAuthStatus(): AuthStatus | null {
  return isCacheFresh(authCache) ? authCache!.value : null
}

export function writeCachedAuthStatus(status: AuthStatus, ttlMs = AUTH_CACHE_TTL_MS): AuthStatus {
  authCache = {
    value: status,
    expiresAt: Date.now() + Math.max(0, ttlMs),
  }
  return status
}

export function clearCachedAuthStatus() {
  authCache = null
}

export async function fetchAuthStatus(init?: HttpInit, options?: { force?: boolean }): Promise<AuthStatus> {
  const force = Boolean(options?.force)
  if (!force) {
    const cached = readCachedAuthStatus()
    if (cached) return cached
    if (authPending) return authPending
  }

  const request = authApi.authStatus(init)
    .then((status) => writeCachedAuthStatus(status))
    .catch((error) => {
      if (force) clearCachedAuthStatus()
      throw error
    })
    .finally(() => {
      if (authPending === request) authPending = null
    })

  authPending = request
  return request
}
