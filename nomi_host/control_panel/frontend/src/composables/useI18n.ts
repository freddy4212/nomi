import { ref, computed, watch } from 'vue'
import messages from '../locales'

type Locale = 'zh' | 'en'

// State needs to be outside the function to be shared (singleton-like)
// or we can use a Pinia store, but a simple reactive state works here.
const currentLocale = ref<Locale>(('localStorage' in window ? localStorage.getItem('user-locale') as Locale : null) || 'zh')

watch(currentLocale, (newLocale) => {
  localStorage.setItem('user-locale', newLocale)
})

export function useI18n() {
  
  const toggleLocale = () => {
    currentLocale.value = currentLocale.value === 'zh' ? 'en' : 'zh'
  }

  const setLocale = (locale: Locale) => {
    currentLocale.value = locale
  }

  // Simple getter for nested keys e.g. 'nav.perception'
  const t = (key: string): string => {
    const keys = key.split('.')
    let result: any = messages[currentLocale.value]
    
    for (const k of keys) {
      if (result && typeof result === 'object' && k in result) {
        result = result[k]
      } else {
        return key // Fallback to key if not found
      }
    }
    
    return result as string
  }

  // Handle dynamic text received from backend
  const tDynamic = (text: string | null | undefined): string => {
    if (!text) return text || ''
    
    // For Chinese, we can just return it unless we want to map it too
    // but the dictionary supports both, so we can just use the map.
    const dict = messages[currentLocale.value]?.dynamic
    if (!dict) return text

    let result = text
    // Sort keys by length so "可能坐著" is replaced before "坐著"
    const keys = Object.keys(dict).sort((a, b) => b.length - a.length)
    
    for (const key of keys) {
      if (result.includes(key)) {
        result = result.replace(new RegExp(key, 'g'), dict[key])
      }
    }
    
    return result
  }

  return {
    locale: currentLocale,
    toggleLocale,
    setLocale,
    t,
    tDynamic
  }
}
