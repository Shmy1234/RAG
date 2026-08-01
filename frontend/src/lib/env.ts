type RequiredUrlName = 'VITE_API_BASE_URL' | 'VITE_SUPABASE_URL'

function required(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name]?.trim()
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`)
  }
  return value
}

function requiredHttpUrl(name: RequiredUrlName): string {
  const value = required(name)
  try {
    const url = new URL(value)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      throw new Error()
    }
    return url.toString().replace(/\/+$/, '')
  } catch {
    throw new Error(`Invalid HTTP URL in environment variable: ${name}`)
  }
}

export const env = Object.freeze({
  apiBaseUrl: requiredHttpUrl('VITE_API_BASE_URL'),
  supabaseUrl: requiredHttpUrl('VITE_SUPABASE_URL'),
  supabaseAnonKey: required('VITE_SUPABASE_ANON_KEY'),
})
