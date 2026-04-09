import {createRouter, createWebHistory} from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

// 路由列表
const routes = [
    {
        path: '/',
        name: '/',
        component: () => import('../views/pages/ManageView.vue')
    },
    {
        path: '/search',
        name: 'SearchFile',
        component: () => import('../views/pages/PDFUpload.vue')
    },
    {
        path: '/parse',
        name: 'FileParse',
        component: () => import('../views/pages/FileParse.vue')
    },
    {
        path: '/build',
        name: 'BuildKG',
        component: () => import('../views/pages/BuildView.vue')
    },
    {
        path: '/QA',
        name: 'QA',
        component: () => import('../views/pages/QA.vue')
    },
    {
        path: '/document-governance',
        name: 'DocumentGovernance',
        component: () => import('../views/pages/DocumentGovernance.vue')
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})


// 路由守卫
router.beforeEach((to, from, next) => {
    NProgress.start()
    next()
})

router.afterEach(() => {
    NProgress.done()
})

export default router