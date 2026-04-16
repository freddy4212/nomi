import { ref, watch } from 'vue'

export type ThemeMode = 'dark' | 'light'

const STORAGE_KEY = 'ui-theme-mode'
const rootElement = typeof document !== 'undefined' ? document.documentElement : null

const THEME_META_COLORS: Record<ThemeMode, string> = {
  dark: '#111827',
  light: '#e8eef6',
}

const getInitialTheme = (): ThemeMode => {
  if (typeof window === 'undefined') return 'dark'
  const saved = window.localStorage.getItem(STORAGE_KEY)
  return saved === 'light' ? 'light' : 'dark'
}

const currentTheme = ref<ThemeMode>(getInitialTheme())

const applyThemeClass = (theme: ThemeMode) => {
  if (!rootElement) return
  rootElement.classList.toggle('theme-light', theme === 'light')
  rootElement.classList.toggle('theme-dark', theme === 'dark')
}

const applyThemeMeta = (theme: ThemeMode) => {
  if (typeof document === 'undefined') return
  let meta = document.querySelector('meta[name="theme-color"]')
  if (!meta) {
    meta = document.createElement('meta')
    meta.setAttribute('name', 'theme-color')
    document.head.appendChild(meta)
  }
  meta.setAttribute('content', THEME_META_COLORS[theme])
}

applyThemeClass(currentTheme.value)
applyThemeMeta(currentTheme.value)

watch(currentTheme, (newTheme) => {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, newTheme)
  }
  applyThemeClass(newTheme)
  applyThemeMeta(newTheme)
})

export function useTheme() {
  const toggleTheme = () => {
    currentTheme.value = currentTheme.value === 'dark' ? 'light' : 'dark'
  }

  const setTheme = (theme: ThemeMode) => {
    currentTheme.value = theme
  }

  return {
    theme: currentTheme,
    toggleTheme,
    setTheme,
  }
}
