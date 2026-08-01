import { request, type RequestOptions } from '@/lib/http'

type RequestBody = RequestOptions['body']
type RequestConfig = Omit<RequestOptions, 'body' | 'method'>

export const api = {
  get: <T>(path: string, options?: RequestConfig) => request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: RequestBody, options?: RequestConfig) => request<T>(path, { ...options, body, method: 'POST' }),
  put: <T>(path: string, body?: RequestBody, options?: RequestConfig) => request<T>(path, { ...options, body, method: 'PUT' }),
  patch: <T>(path: string, body?: RequestBody, options?: RequestConfig) => request<T>(path, { ...options, body, method: 'PATCH' }),
  delete: <T>(path: string, options?: RequestConfig) => request<T>(path, { ...options, method: 'DELETE' }),
}
