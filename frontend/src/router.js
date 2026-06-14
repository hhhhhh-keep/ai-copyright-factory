import { createRouter, createWebHistory } from 'vue-router'
import HomePage from './pages/HomePage.vue'
import PlanningReviewPage from './pages/PlanningReviewPage.vue'
import HistoryPage from './pages/HistoryPage.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomePage },
    { path: '/history', name: 'history', component: HistoryPage },
    {
      path: '/planning-review/:jobId',
      name: 'planning-review',
      component: PlanningReviewPage
    }
  ]
})
