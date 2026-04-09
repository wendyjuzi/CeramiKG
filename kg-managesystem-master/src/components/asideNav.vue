<template>
    <div class="sidebar">
        <el-menu
            :default-active="$route.path"
            class="sidebar-el-menu"
            @open="handleOpen"
            @close="handleClose"
            @select="handleSelect"
            :router="false"
        >
            <el-menu-item index="/search" @click="handleMenuItemClick('/search')">
            <el-icon><DataBoard /></el-icon>
            <span>文件管理</span>
            </el-menu-item>

            <el-menu-item index="/document-governance" @click="handleMenuItemClick('/document-governance')">
            <el-icon><Document /></el-icon>
            <span>文档治理</span>
            </el-menu-item>


            <el-menu-item index="/build" @click="handleMenuItemClick('/build')">
            <el-icon><DocumentAdd/></el-icon>
            <span>图谱构建</span>
            </el-menu-item>

            <el-menu-item index="/QA" @click="handleMenuItemClick('/QA')">
            <el-icon><Search /></el-icon>
            <span>知识问答</span>
            </el-menu-item>



        </el-menu>
    </div>
</template>

<script lang="ts" setup>
import {
DataBoard,
DocumentAdd,
Menu as IconMenu,
Location,
Setting,
DArrowRight,
Collection,
Search,
Document
} from '@element-plus/icons-vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const handleOpen = (key: string, keyPath: string[]) => {
console.log('Menu opened:', key, keyPath)
}

const handleClose = (key: string, keyPath: string[]) => {
console.log('Menu closed:', key, keyPath)
}

// 新增：监听菜单项点击事件
const handleMenuItemClick = (path: string) => {
  console.log('🖱️ Menu item clicked:', path, 'at', new Date().toISOString())
  console.log('🖱️ Current route before click:', route.path)
  // 直接调用路由跳转，作为@select事件的备份机制
  handleSelect(path)
}

const handleSelect = async (index: string) => {
  console.log('🚀 Menu selected:', index, 'Current route:', route.path)
  console.log('🚀 Menu select event triggered at:', new Date().toISOString())
  console.log('🚀 Router instance:', router)
  console.log('🚀 Route instance:', route)
  
  try {
    if (route.path !== index) {
      console.log('🔄 Navigating from', route.path, 'to', index)
      console.log('🔄 Router state before navigation:', {
        currentRoute: router.currentRoute.value,
        hasRoute: router.hasRoute(index.startsWith('/') ? index.slice(1) : index)
      })
      
      // 先尝试使用push方法
      console.log('🔄 Attempting router.push...')
      await router.push(index)
      
      // 添加短暂延迟，确保路由切换完成
      await new Promise(resolve => setTimeout(resolve, 100))
      
      console.log('✅ Navigation attempt completed')
      console.log('✅ Current route after navigation:', route.path)
      console.log('✅ Router current route:', router.currentRoute.value.path)
      
      // 验证路由是否真的切换了
      if (route.path !== index) {
        console.warn('❌ Route navigation failed! Expected:', index, 'Actual:', route.path)
        console.warn('❌ Attempting router.replace...')
        
        await router.replace(index)
        await new Promise(resolve => setTimeout(resolve, 100))
        
        if (route.path !== index) {
          console.error('❌ Router.replace also failed, attempting force reload')
          // 如果还没切换成功，强制重新加载页面
          window.location.href = window.location.origin + index
        } else {
          console.log('✅ Router.replace succeeded')
        }
      } else {
        console.log('✅ Navigation successful via router.push')
      }
    } else {
      console.log('ℹ️ Already on target route:', index)
    }
  } catch (error) {
    console.error('❌ Navigation error:', error)
    console.error('❌ Error stack:', error.stack)
    // 路由失败时强制跳转
    console.log('🔄 Attempting force navigation via location.href')
    window.location.href = window.location.origin + index
  }
}
</script>

<style scoped>
.sidebar {
    display: block;
    overflow-y: scroll;
    height: 100%;
}
.sidebar::-webkit-scrollbar {
    width: 0;
}
.sidebar-el-menu:not(.el-menu--collapse) {
    width: 250px;
}
.sidebar > ul {
    height: 100%;
}
</style>
  