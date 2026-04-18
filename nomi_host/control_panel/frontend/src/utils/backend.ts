const backendHost = import.meta.env.VITE_NOMI_BACKEND_HOST || window.location.hostname
const backendPort = import.meta.env.VITE_NOMI_BACKEND_PORT || '8000'

function normalizePath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`
}

export function buildWsUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${backendHost}:${backendPort}${normalizePath(path)}`
}

export function buildApiUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'https' : 'http'
  return `${protocol}://${backendHost}:${backendPort}${normalizePath(path)}`
}

export function getBackendPort(): string {
  return backendPort
}
