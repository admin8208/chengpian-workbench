import { http } from './http'
import type { HttpInit } from './http'
import type { AuthStatus, UserAccount } from './types'

export const authApi = {
  authStatus: (init?: HttpInit) => http<AuthStatus>('/api/auth/status', init),
  authSetup: (body: { username: string; password: string }) => http<AuthStatus>('/api/auth/setup', { method: 'POST', body: JSON.stringify(body) }),
  authLogin: (body: { username: string; password: string }) => http<AuthStatus>('/api/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  authLogout: () => http<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),
  authUsers: () => http<UserAccount[]>('/api/auth/users'),
  authCreateUser: (body: { username: string; password: string }) => http<UserAccount>('/api/auth/users', { method: 'POST', body: JSON.stringify(body) }),
  authPatchUser: (userId: number, body: { enabled?: boolean }) => http<UserAccount>(`/api/auth/users/${userId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  authResetUserPassword: (userId: number, body: { password: string }) => http<UserAccount>(`/api/auth/users/${userId}/reset-password`, { method: 'POST', body: JSON.stringify(body) }),
}
