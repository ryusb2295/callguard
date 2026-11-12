import { reactive } from 'vue'

// 목업은 탭마다 다른 사람으로 로그인할 수 있게 sessionStorage를 쓴다 (탭 하나는 엄마, 하나는 딸)
const box = () => (import.meta.env.VITE_MOCK === '1' ? sessionStorage : localStorage)

function load() {
  try {
    return JSON.parse(box().getItem('callguard_user') || 'null')
  } catch {
    return null
  }
}

export const store = reactive({
  user: load(),
  setUser(u) {
    this.user = u
    try {
      if (u) box().setItem('callguard_user', JSON.stringify(u))
      else box().removeItem('callguard_user')
    } catch {
      /* 저장 공간을 못 써도 앱은 계속 동작 */
    }
  }
})
