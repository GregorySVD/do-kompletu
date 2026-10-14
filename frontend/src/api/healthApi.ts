import apiClient from './apiClient'

interface HealthResponse {
  status: string
}

export async function checkBackendHealth(): Promise<boolean> {
  const response = await apiClient.get<HealthResponse>('/health', {
    timeout: 5_000,
  })

  return response.status === 200 && response.data.status === 'ok'
}
