<script setup>
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { ref, watch } from 'vue'
import AsideNav from '@/components/asideNav.vue'
import { Fold, Expand } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const locale = ref(zhCn)
const isCollapse = ref(false)
const asideWidth = ref('220px')
const routerKey = ref(`${route.fullPath}-${Date.now()}`)

watch(
  () => route.fullPath,
  (newPath) => {
    routerKey.value = `${newPath}-${Date.now()}`
  },
  { immediate: true }
)

function toggleCollapse() {
  isCollapse.value = !isCollapse.value
  asideWidth.value = isCollapse.value ? '0px' : '220px'
}
</script>

<template>
  <el-config-provider :locale="locale">
    <el-container class="app-shell">
      <el-header class="nav-el-header">
        <span>CeramiKG 陶瓷材料知识图谱构建与可视化系统</span>
        <el-button
          class="collapse-button"
          @click="toggleCollapse"
          :icon="isCollapse ? Expand : Fold"
          circle
        />
      </el-header>
      <el-container>
        <el-aside :width="asideWidth" class="app-aside">
          <aside-nav :is-collapse="isCollapse" />
        </el-aside>
        <el-container>
          <el-main>
            <router-view :key="routerKey" />
          </el-main>
          <el-footer class="app-footer">
            <span>CeramiKG Manage System ©2026</span>
          </el-footer>
        </el-container>
      </el-container>
    </el-container>
  </el-config-provider>
</template>

<style scoped>
html,
body {
  height: 100%;
  margin: 0;
  border: 0;
  padding: 0;
}

.app-shell {
  margin: 0;
  border: none;
  padding: 0;
}

.nav-el-header {
  position: relative;
  line-height: 60px;
  font-size: large;
  background: linear-gradient(200deg, rgba(67, 98, 220, 0.75), rgba(10, 111, 239, 0.82));
  color: white;
  border-radius: 10px;
  transition: 0.125s ease-in-out;
}

.collapse-button {
  float: right;
  margin-top: 12px;
}

.app-aside {
  transition: width 0.3s;
}

.app-footer {
  text-align: center;
  font-size: 14px;
}
</style>
