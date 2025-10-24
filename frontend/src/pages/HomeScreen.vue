<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const promoModules = import.meta.glob('../../public/images/promos/*.{png,jpg,jpeg,webp,avif,gif}', {
  eager: true,
  import: 'default',
  query: '?url',
})

const promoSlides = Object.entries(promoModules)
  .filter(([, url]) => typeof url === 'string' && url)
  .map(([path, url]) => {
    const parts = path.split('/')
    const filename = parts[parts.length - 1] ?? path
    const label = filename.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim() || 'Promo'
    return {
      id: filename,
      type: 'image',
      src: url,
      alt: `${label} promotion`,
    }
  })
  .sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true, sensitivity: 'base' }))

const slidesSource = ref(promoSlides)

const placeholderSlide = {
  id: 'placeholder',
  originalId: 'placeholder',
  type: 'placeholder',
  message: 'No promos available',
}

const hasRealSlides = computed(() => slidesSource.value.length > 0)

const slides = computed(() => {
  if (!hasRealSlides.value) {
    return [{ ...placeholderSlide }]
  }
  return slidesSource.value.map((slide) => ({
    ...slide,
    originalId: slide.id,
  }))
})

const totalSlides = computed(() => slides.value.length)

const trackSlides = computed(() => {
  if (!hasRealSlides.value) {
    return slides.value
  }

  const total = slides.value.length
  if (total === 0) {
    return []
  }

  if (total === 1) {
    const single = slides.value[0]
    return [
      {
        ...single,
        id: `${single.id}-single`,
      },
    ]
  }

  // For ping-pong style, we don't need cloned slides
  return slides.value.map((slide) => ({
    ...slide,
  }))
})

const allowTransition = ref(true)
const trackPosition = ref(0) // Start at 0 since we don't have cloned slides
const currentIndex = ref(0)

const carouselRoot = ref(null)
const containerWidth = ref(0)
const dragOffset = ref(0)
const dragPercent = computed(() =>
  containerWidth.value ? (dragOffset.value / containerWidth.value) * 100 : 0
)

const isAnimating = ref(false)
const isPointerDown = ref(false)
const isDragging = ref(false)
const pointerId = ref(null)
const dragStartX = ref(0)

const isModalOpen = ref(false)
const isStartingSession = ref(false)
const modalError = ref('')
const cursorHidden = ref(false)
let cursorTimer = null

const activeSlide = computed(() => slides.value[currentIndex.value] ?? slides.value[0])
const activeSlideId = computed(() => activeSlide.value?.originalId ?? 'placeholder')

const updateBounds = () => {
  if (carouselRoot.value) {
    containerWidth.value = carouselRoot.value.clientWidth
  }
}

watch(
  [hasRealSlides, totalSlides],
  ([has, total]) => {
    allowTransition.value = false
    trackPosition.value = 0  // Start at 0 since no cloned slides
    currentIndex.value = 0
    dragOffset.value = 0
    isAnimating.value = false
    requestAnimationFrame(() => {
      allowTransition.value = true
    })
  },
  { immediate: true }
)

const trackTransform = computed(() => {
  if (!hasRealSlides.value || totalSlides.value <= 1) {
    return `translate3d(${dragPercent.value}%, 0, 0)`
  }
  const base = -(trackPosition.value * 100)
  const adjusted = base + dragPercent.value
  return `translate3d(${adjusted}%, 0, 0)`
})

const trackStyle = computed(() => ({
  transform: trackTransform.value,
  transition:
    allowTransition.value && !isDragging.value
      ? 'transform 450ms cubic-bezier(0.33, 1, 0.68, 1)'
      : 'none',
}))

const resetCursorTimer = () => {
  cursorHidden.value = false
  if (cursorTimer) {
    clearTimeout(cursorTimer)
  }
  if (isModalOpen.value) {
    return
  }
  cursorTimer = setTimeout(() => {
    cursorHidden.value = true
  }, 3000)
}

const openModal = () => {
  if (isModalOpen.value) return
  if (cursorTimer) {
    clearTimeout(cursorTimer)
  }
  cursorHidden.value = false
  modalError.value = ''
  isModalOpen.value = true
}

const closeModal = () => {
  if (isStartingSession.value) return
  modalError.value = ''
  isModalOpen.value = false
  resetCursorTimer()
}

const confirmStart = async () => {
  if (isStartingSession.value) return
  modalError.value = ''
  isStartingSession.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/session/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      const fallbackMessage = 'Failed to start the photo session. Please try again.'
      throw new Error(payload?.message || fallbackMessage)
    }

    isModalOpen.value = false
    router.push({ name: 'photo-session' })
  } catch (error) {
    console.error(error)
    modalError.value =
      error instanceof Error && error.message
        ? error.message
        : 'Unexpected error starting session.'
  } finally {
    isStartingSession.value = false
  }
}

const goNext = () => {
  const total = totalSlides.value
  if (!hasRealSlides.value || total <= 1) return
  
  // Don't allow new animations if already animating
  if (isAnimating.value) return
  
  // For ping-pong style, don't go beyond the last slide
  if (currentIndex.value >= total - 1) return
  
  allowTransition.value = true
  dragOffset.value = 0
  isAnimating.value = true
  currentIndex.value = currentIndex.value + 1
  trackPosition.value = currentIndex.value
}

const goPrev = () => {
  const total = totalSlides.value
  if (!hasRealSlides.value || total <= 1) return
  
  // Don't allow new animations if already animating
  if (isAnimating.value) return
  
  // For ping-pong style, don't go before the first slide
  if (currentIndex.value <= 0) return
  
  allowTransition.value = true
  dragOffset.value = 0
  isAnimating.value = true
  currentIndex.value = currentIndex.value - 1
  trackPosition.value = currentIndex.value
}

const finishTransitionIfNeeded = () => {
  if (!isAnimating.value) return

  const total = totalSlides.value
  if (!hasRealSlides.value || total <= 1) {
    isAnimating.value = false
    return
  }

  // For ping-pong style, just reset animation state
  isAnimating.value = false
}

const pointerThreshold = computed(() => Math.min(160, containerWidth.value * 0.25 || 160))

const resetDragState = () => {
  dragOffset.value = 0
  isDragging.value = false
  isPointerDown.value = false
  pointerId.value = null
}

const handlePointerDown = (event) => {
  if (isModalOpen.value) return
  resetCursorTimer()
  isPointerDown.value = true
  pointerId.value = event.pointerId
  dragStartX.value = event.clientX
  dragOffset.value = 0
  isDragging.value = false
  allowTransition.value = false
  if (event.currentTarget && event.currentTarget.setPointerCapture) {
    event.currentTarget.setPointerCapture(event.pointerId)
  }
}

const handlePointerMove = (event) => {
  if (!isPointerDown.value || isModalOpen.value) return
  const deltaX = event.clientX - dragStartX.value
  // Use a more generous threshold to ensure taps are properly detected
  if (!isDragging.value && Math.abs(deltaX) > 20) {
    isDragging.value = true
    // When we start dragging, we should stop any ongoing animation
    isAnimating.value = false
  }
  if (isDragging.value) {
    dragOffset.value = deltaX
  }
}

const triggerNavigationForDrag = (deltaX) => {
  const total = totalSlides.value
  if (!hasRealSlides.value || total <= 1) {
    allowTransition.value = true
    dragOffset.value = 0
    return false
  }
  if (Math.abs(deltaX) < pointerThreshold.value) {
    allowTransition.value = true
    dragOffset.value = 0
    return false
  }
  if (deltaX < 0) {
    goNext()
  } else {
    goPrev()
  }
  return true
}

const handlePointerUp = (event) => {
  if (!isPointerDown.value) return
  if (event.currentTarget && event.currentTarget.releasePointerCapture && pointerId.value !== null) {
    event.currentTarget.releasePointerCapture(pointerId.value)
  }
  const deltaX = event.clientX - dragStartX.value
  const navigated = isDragging.value ? triggerNavigationForDrag(deltaX) : false
  
  // Only process tap to open modal if we haven't started navigating and modal isn't open
  if (!isDragging.value && !navigated && !isModalOpen.value) {
    openModal()
  }
  // If the user barely moved their finger, consider it a tap even if it was slight movement
  else if (isDragging.value && Math.abs(deltaX) <= 20 && !navigated && !isModalOpen.value) {
    openModal()
  }
  
  // Only reset transitions and drag offset if we're not opening the modal
  if (!navigated && !isModalOpen.value) {
    allowTransition.value = true
    dragOffset.value = 0
  }
  resetDragState()
  resetCursorTimer()
}

const handlePointerCancel = (event) => {
  if (!isPointerDown.value) return
  if (event.currentTarget && event.currentTarget.releasePointerCapture && pointerId.value !== null) {
    event.currentTarget.releasePointerCapture(pointerId.value)
  }
  allowTransition.value = true
  dragOffset.value = 0
  resetDragState()
  resetCursorTimer()
}

const handlePointerLeave = (event) => {
  if (!isPointerDown.value) return
  handlePointerUp(event)
}

const handleKeydown = (event) => {
  if (event.repeat) return
  switch (event.key) {
    case 'ArrowRight':
      event.preventDefault()
      if (!isModalOpen.value) goNext()
      break
    case 'ArrowLeft':
      event.preventDefault()
      if (!isModalOpen.value) goPrev()
      break
    case 'Enter':
      event.preventDefault()
      if (isModalOpen.value) {
        confirmStart()
      } else {
        openModal()
      }
      break
    case 'Escape':
      if (isModalOpen.value) {
        event.preventDefault()
        closeModal()
      }
      break
    default:
      break
  }
}

const preloadCache = new Set()
const maxPreloadCacheSize = 50 // Limit the cache size to prevent memory buildup
watch(
  () => [currentIndex.value, hasRealSlides.value],
  () => {
    if (!hasRealSlides.value) return
    const total = slides.value.length
    const indices = [
      currentIndex.value,
      (currentIndex.value + 1) % total,
      (currentIndex.value - 1 + total) % total,
    ]
    indices.forEach((idx) => {
      const slide = slides.value[idx]
      if (slide?.type === 'image' && !preloadCache.has(slide.src)) {
        const img = new Image()
        img.src = slide.src
        preloadCache.add(slide.src)
        
        // Limit cache size to prevent memory buildup
        if (preloadCache.size > maxPreloadCacheSize) {
          const firstEntry = preloadCache.values().next().value
          if (firstEntry) {
            preloadCache.delete(firstEntry)
          }
        }
      }
    })
  },
  { immediate: true }
)

// Store references to event listeners for proper cleanup
let resizeListener = null
let keydownListener = null

onMounted(() => {
  updateBounds()
  resizeListener = updateBounds
  keydownListener = handleKeydown
  window.addEventListener('resize', resizeListener)
  window.addEventListener('keydown', keydownListener)
  resetCursorTimer()
})

onBeforeUnmount(() => {
  if (resizeListener) {
    window.removeEventListener('resize', resizeListener)
    resizeListener = null
  }
  if (keydownListener) {
    window.removeEventListener('keydown', keydownListener)
    keydownListener = null
  }
  if (cursorTimer) {
    clearTimeout(cursorTimer)
    cursorTimer = null
  }
  
  // Clear the preload cache to free up memory
  preloadCache.clear()
})
</script>

<template>
  <div
    ref="carouselRoot"
    class="home-screen"
    :class="{ 'cursor-hidden': cursorHidden }"
    tabindex="-1"
    @pointerdown="handlePointerDown"
    @pointermove="handlePointerMove"
    @pointerup="handlePointerUp"
    @pointercancel="handlePointerCancel"
    @pointerleave="handlePointerLeave"
  >
    <div class="carousel-track-wrapper">
      <div
        class="carousel-track"
        :style="trackStyle"
        @transitionend="finishTransitionIfNeeded"
      >
        <div
          v-for="(slide, index) in trackSlides"
          :key="slide.id ?? `slide-${index}`"
          class="carousel-slide"
          :class="{
            'is-placeholder': slide.type === 'placeholder',
            'is-active': (slide.originalId ?? slide.id) === activeSlideId,
          }"
        >
          <img
            v-if="slide.type === 'image'"
            :src="slide.src"
            :alt="slide.alt"
            draggable="false"
          />
          <div v-else class="carousel-placeholder">
            <div class="placeholder-copy">
              <h1>No promos available</h1>
              <p>Stay tuned for upcoming campaigns.</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <teleport to="body">
      <div
        v-if="isModalOpen"
        class="modal-backdrop"
        role="presentation"
      >
        <div
          class="modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="start-modal-title"
          @click.stop
        >
          <h2 id="start-modal-title  ">Mulai foto?</h2>
          <p v-if="modalError" class="modal-error" role="alert">
            {{ modalError }}
          </p>
          <div class="modal-actions">
            <button
              type="button"
              class="modal-batal modal-btn putih-semua"
              :disabled="isStartingSession"
              @click="closeModal"
            >
              Batal
            </button>
                        <button
              type="button"
              class="modal-ya modal-btn merah-semua"
              :disabled="isStartingSession"
              :aria-busy="isStartingSession"
              @click="confirmStart"
            >
              <span v-if="isStartingSession">Starting...</span>
              <span v-else>Ya</span>
            </button>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<style scoped>
.home-screen {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #000;
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
  display: flex;
  align-items: stretch;
  justify-content: center;
  color: #fff;
}

.home-screen.cursor-hidden {
  cursor: none;
}

.carousel-track-wrapper {
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: relative;
}

.carousel-track {
  width: 100%;
  height: 100%;
  display: flex;
}

.carousel-slide {
  position: relative;
  width: 100%;
  height: 100%;
  flex: 0 0 100%;
}

.carousel-slide img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  pointer-events: none;
}

.carousel-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #121212, #2b2b2b);
  text-align: center;
  padding: 2rem;
}

.placeholder-copy h1 {
  font-size: clamp(2.5rem, 6vw, 4rem);
  margin: 0 0 1rem;
}

.placeholder-copy p {
  font-size: clamp(1.2rem, 3vw, 2rem);
  margin: 0;
  opacity: 0.8;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  z-index: 20;
  backdrop-filter: blur(4px);
}

.modal {
  background: #FFFFFF;
  border-radius: 32px;
  padding: clamp(2rem, 5vw, 3rem);
  text-align: center;
  color: #fff;
  min-width: min(50rem, 90vw);
  min-height: min(40rem, 90vw);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.35);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center
}

.modal h2 {
  font-size: 84px;
  margin: 0 0 6rem;
  font-weight: 700;
  font-family: "Poppins", sans-serif;
  font-style: normal;
  color: #E60000;
}

.modal-error {
  margin: 0 0 1.5rem;
  color: #ff8aa0;
  font-size: clamp(1rem, 2.2vw, 1.4rem);
}

.modal-actions {
  display: flex;
  gap: 1.5rem;
  justify-content: center;
  flex-wrap: wrap;
}

.modal-btn {
  min-width: 20rem;
  padding: 1rem 2.5rem;
  font-size: 60px;
  /* font-weight: 600; */
  /* border: none; */
  border-radius: 999px;
  cursor: pointer;
  transition: transform 150ms ease, box-shadow 150ms ease;
}


.modal-btn:hover,
.modal-btn:focus-visible {
  transform: translateY(-2px) scale(1.02);
  outline: none;
}

.modal-btn:active {
  transform: translateY(0);
}

.modal-btn[disabled] {
  opacity: 0.65;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

@media (orientation: landscape) {
  .home-screen {
    max-width: 1080px;
    margin: 0 auto;
  }
}
</style>
