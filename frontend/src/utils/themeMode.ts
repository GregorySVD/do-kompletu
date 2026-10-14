export type ThemeMode = 'light' | 'dark'

const themeStorageKey = 'do-kompletu-theme'

export function getInitialThemeMode(): ThemeMode {
  const savedMode = localStorage.getItem(themeStorageKey)

  return savedMode === 'light' || savedMode === 'dark' ? savedMode : 'light'
}

export function applyThemeMode(mode: ThemeMode) {
  localStorage.setItem(themeStorageKey, mode)
  document.documentElement.dataset.theme = mode
}
