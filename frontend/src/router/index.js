import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../pages/HomeScreen.vue'),
  },
  {
    path: '/photo-session',
    name: 'photo-session',
    component: () => import('../pages/PhotoSession.vue'),
  },
  {
    path: '/result',
    name: 'result',
    component: () => import('../pages/ResultDisplay.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Add navigation guards to ensure proper cleanup
router.beforeEach((to, from, next) => {
  // Clear any ongoing operations when navigating away from components
  if (from.name === 'photo-session') {
    // Any cleanup needed when leaving photo session
  }
  if (from.name === 'result') {
    // Any cleanup needed when leaving result display
  }
  next()
})

export default router
