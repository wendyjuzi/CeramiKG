<script setup>
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { ref, watch } from "vue";
import AsideNav from "@/components/asideNav.vue";
import { Fold, Expand } from '@element-plus/icons-vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const locale = ref(zhCn);
const isCollapse = ref(false); // 控制侧边栏折叠状态
const asideWidth = ref('220px'); // 动态侧边栏宽度（优化：从270px缩小到220px）

// 强制路由key：包含时间戳确保每次跳转都重新渲染组件
const routerKey = ref(`${route.fullPath}-${Date.now()}`);

// 监听路由变化，更新key以强制组件重新渲染
watch(
  () => route.fullPath,
  (newPath) => {
    console.log('App.vue: Route changed to:', newPath)
    routerKey.value = `${newPath}-${Date.now()}`
    console.log('App.vue: Updated router key to:', routerKey.value)
  },
  { immediate: true }
)

// 切换折叠状态
function toggleCollapse() {
  isCollapse.value = !isCollapse.value;
  asideWidth.value = isCollapse.value ? '0px' : '220px';
}
</script>

<template>
  <el-config-provider :locale="locale">
    <el-container style="margin: 0; border: none; padding: 0;">
      <el-header class="nav-el-header">
        <span>冶金合金知识图谱构建与可视化系统</span>
        <el-button
          @click="toggleCollapse"
          :icon="isCollapse ? Expand : Fold"
          circle
          style="float: right; margin-top: 12px;"
        />
      </el-header>
      <el-container>
        <!-- 侧边栏 -->
        <el-aside :width="asideWidth" style="transition: width 0.3s;">
          <aside-nav :is-collapse="isCollapse" />
        </el-aside>
        <!-- 主页面 -->
        <el-container>
          <el-main>
            <router-view :key="routerKey" />
          </el-main>
          <el-footer>
            <span style="font-size: 14px; margin-left: 40%;">
              Cig-KG Manage System ©2025 Created by BDKEI
            </span>
          </el-footer>
        </el-container>
      </el-container>
    </el-container>
  </el-config-provider>
</template>

<style scoped>
html, body {
  height: 100%;
  margin: 0;
  border: 0;
  padding: 0;
}

.nav-el-header {
  line-height: 60px;
  font-size: large;
  background: linear-gradient(200deg, rgba(67, 98, 220, 0.75), rgba(10, 111, 239, 0.82));
  color: white;
  border-radius: 10px;
  transition: 0.125s ease-in-out;
  position: relative;
}
</style>