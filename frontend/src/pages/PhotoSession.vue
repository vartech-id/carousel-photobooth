<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const pollIntervalMs = 2000

const status = ref('checking')
const assetPath = ref('')
const assetUrl = ref('')
const errorMessage = ref('')
let pollHandle = null
let hasNavigated = false

// Track component mounted state to prevent updates after unmounting
let isComponentMounted = true

const isError = computed(() => status.value === 'error')
const isWaiting = computed(
  () => status.value === 'checking' || status.value === 'in_progress' || status.value === 'finalizing'
)

const statusCopy = computed(() => {
  switch (status.value) {
    case 'completed':
      return 'Processing complete. Loading your photos...'
    case 'finalizing':
      return 'Finalizing your photo <br/>Please hold tight.'
    case 'in_progress':
      return 'Waiting for your photo.'
    case 'error':
      return 'We hit a snag while waiting for the session.'
    case 'idle':
      return 'Preparing a brand new session...'
    default:
      return 'Contacting DSLRBooth...'
  }
})

const stopPolling = () => {
  if (pollHandle) {
    clearInterval(pollHandle)
    pollHandle = null
  }
}

const handleState = (state) => {
  // Don't process state updates if component is unmounted
  if (!isComponentMounted) return
  
  const nextStatus = state?.status ?? 'idle'
  assetPath.value = state?.asset_path ?? ''

  const rawAssetUrl = state?.asset_url ?? ''
  if (rawAssetUrl) {
    try {
      assetUrl.value = new URL(rawAssetUrl, apiBaseUrl).href
    } catch (error) {
      console.error('Failed to resolve asset URL', error)
      assetUrl.value = rawAssetUrl
    }
  } else {
    assetUrl.value = ''
  }

  status.value = nextStatus

  if (nextStatus === 'idle') {
    stopPolling()
    router.replace({ name: 'home' })
    return
  }

  if (nextStatus === 'completed') {
    if (assetUrl.value && !hasNavigated) {
      hasNavigated = true
      stopPolling()
      router.replace({ name: 'result' })
    } else if (!assetUrl.value) {
      status.value = 'finalizing'
    }
  }
}

const fetchStatus = async () => {
  // Don't fetch if component is unmounted
  if (!isComponentMounted) return
  
  try {
    const response = await fetch(`${apiBaseUrl}/session/status`, { cache: 'no-store' })
    if (!response.ok) {
      throw new Error(`Status request failed with ${response.status}`)
    }
    const payload = await response.json()
    errorMessage.value = ''
    handleState(payload?.state ?? {})
  } catch (error) {
    console.error(error)
    errorMessage.value = 'Unable to reach the photo booth. Please retry.'
    status.value = 'error'
    stopPolling()
  }
}

const retryNow = async () => {
  errorMessage.value = ''
  status.value = 'checking'
  assetUrl.value = ''
  await fetchStatus()
  if (!pollHandle && !hasNavigated) {
    pollHandle = setInterval(fetchStatus, pollIntervalMs)
  }
}

const goHome = async () => {
  stopPolling()
  try {
    await fetch(`${apiBaseUrl}/session/reset`, { method: 'POST' })
  } catch (error) {
    console.error('Failed to reset session before leaving photo session.', error)
  } finally {
    if (isComponentMounted) {
      router.replace({ name: 'home' })
    }
  }
}

onMounted(() => {
  isComponentMounted = true
  fetchStatus()
  pollHandle = setInterval(fetchStatus, pollIntervalMs)
})

onBeforeUnmount(() => {
  isComponentMounted = false
  stopPolling()
})
</script>

<template>
  <main class="session-screen" role="status" aria-live="polite">
    <div class="status-panel" :class="{ waiting: isWaiting, error: isError }">
      <div class="loader" v-if="isWaiting">
        <span class="loader-core" />
      </div>
      <h1 v-html="statusCopy"></h1>
      <p v-if="errorMessage" class="error-copy">{{ errorMessage }}</p>
      <div class="actions">
        <button type="button" class="action-btn primary" v-if="isError" @click="retryNow">
          Retry
        </button>
        <button type="button" class="back-to-home action-btn putih-semua" @click="goHome">
          Back to home
        </button>
      </div>
    </div>
  </main>
</template>

<style scoped>
.session-screen {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  /* background: radial-gradient(circle at center, rgba(255, 0, 43, 0.18), rgba(0, 0, 0, 0.9)); */
  color: #fff;
  text-align: center;
  padding: 2rem;
}

.status-panel {
  font-size: 84px;
  margin: 0 0 2rem;
  font-weight: 700;
  font-family: "Poppins", sans-serif;
  font-style: normal;
  color: #E60000;
  background: #ffff;
  border-radius: 32px;
  padding: clamp(2rem, 5vw, 3rem);
  text-align: center;
  color: #ff0000;
  min-width: min(50rem, 90vw);
  min-height: min(40rem, 90vw);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.35);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center
}

.status-panel.waiting {
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.status-panel.error {
  border: 1px solid rgba(255, 0, 43, 0.45);
  background: rgba(30, 8, 12, 0.92);
}

.loader {
  width: clamp(80px, 20vw, 120px);
  height: clamp(80px, 20vw, 120px);
  border-radius: 50%;
  border: 6px solid rgba(255, 255, 255, 0.15);
  border-top-color: #ff002b;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: spin 1.25s linear infinite;
}

.loader-core {
  width: 55%;
  height: 55%;
  border-radius: 50%;
  background: rgba(255, 0, 43, 0.35);
  filter: blur(1px);
}

h1 {
  font-size: clamp(2.25rem, 5vw, 3.5rem);
  margin: 0;
}

.error-copy {
  font-size: clamp(1.1rem, 2.2vw, 1.5rem);
  margin: 0;
  color: #ff8aa0;
}

.actions {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  justify-content: center;
}

.action-btn {
  color: #E60000 ;
  min-width: 20rem;
  padding: 1rem 2.5rem;
  font-size: 40px;
  /* font-weight: 600; */
  border: 5px solid #E60000;
  border-radius: 999px;
  cursor: pointer;
  transition: transform 150ms ease, box-shadow 150ms ease;
  background: white;
  transform: translate(0px, 20px);
}

/* .action-btn.primary {
  background: #ff002b;
  color: #fff;
  box-shadow: 0 16px 32px rgba(255, 0, 43, 0.35);
} */

/* .action-btn.secondary {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  border: 2px solid rgba(255, 255, 255, 0.25);
} */

/* .action-btn:hover,
.action-btn:focus-visible {
  transform: translateY(-2px);
  outline: none;
} */

.action-btn:active {
  transform: translateY(0);
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
