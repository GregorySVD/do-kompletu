import axios from 'axios'

export const accessTokenStorageKey = 'do-kompletu-access-token'
export const refreshTokenStorageKey = 'do-kompletu-refresh-token'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})

apiClient.interceptors.request.use((config) => {
  const accessToken = sessionStorage.getItem(accessTokenStorageKey)

  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }

  return config
})

export default apiClient
