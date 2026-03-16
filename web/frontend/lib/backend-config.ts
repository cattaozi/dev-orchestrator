const DEFAULT_BACKEND_ORIGIN = 'http://127.0.0.1:7000'

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '')
}

const backendOrigin = trimTrailingSlash(
  process.env.BACKEND_ORIGIN ?? DEFAULT_BACKEND_ORIGIN
)

export const API_BASE = `${backendOrigin}/api`
