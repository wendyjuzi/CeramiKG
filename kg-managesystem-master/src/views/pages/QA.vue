<template>
  <div class="build-container" @click="scrollToTop">
    <!-- 增大后的容器：作为遮蔽层和iframe的定位父容器 -->
    <div class="fixed-container">
      <!-- 新增字幕的遮蔽层（核心修改：添加文字内容） -->
      <div class="ragflow-mask">
        <span class="mask-title">智能体知识问答</span>
      </div>
      <!-- 原有iframe：嵌入RAGFlow页面 -->
      <iframe
          ref="ragflowIframe"
          class="ragflow-iframe"
          src="http://localhost:80/chat"
          frameborder="0"
          title="RAGFlow 知识问答平台"
      ></iframe>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue';
const ragflowIframe = ref(null);

const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (ragflowIframe.value) {
    try {
      const iframeWindow = ragflowIframe.value.contentWindow;
      iframeWindow.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (e) {
      console.warn('跨域限制，无法操作iframe内部滚动');
    }
  }
};

// 页面挂载后初始化iframe样式（保留原有功能）
onMounted(() => {
  const iframe = ragflowIframe.value;
  if (!iframe) return;

  // iframe加载完成后适配内部内容
  iframe.onload = () => {
    scrollToTop(); // 初始加载后滚动到顶部
    try {
      const innerDoc = iframe.contentDocument || iframe.contentWindow.document;
      if (innerDoc) {
        // 调整RAGFlow内部内容样式，避免与遮蔽层冲突
        innerDoc.body.style.height = '100%';
        innerDoc.documentElement.style.height = '100%';
        const rootEl = innerDoc.querySelector('#app') || innerDoc.body;
        if (rootEl) {
          rootEl.style.height = '100%';
          rootEl.style.width = '100%';
        }
      }
    } catch (e) {
      console.warn('跨域限制，使用默认适配');
    }
  };
});
</script>
<style scoped>
/* 清除默认样式（保留原有） */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* 页面基础样式（保留原有） */
html, body {
  width: 100%;
  height: 100%;
  overflow: hidden; /* 禁止页面整体滚动 */
  background: #f5f5f5;
}

/* 外层容器 - 点击区域覆盖整个页面（保留原有） */
.build-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 10px;
  cursor: pointer; /* 提示可点击 */
}

/* 固定容器 - 作为定位父容器（保留原有） */
.fixed-container {
  width: 95vw; /* 宽度占视口的95% */
  max-width: 1400px; /* 最大宽度增大到1400px */
  height: 78vh; /* 高度占视口的78%（可根据需求调整） */
  max-height: 900px; /* 最大高度增大到900px */
  position: relative; /* 关键：让遮蔽层相对于此容器定位 */
  overflow: hidden;
  box-shadow: 0 2px 15px rgba(0, 0, 0, 0.1);
  background: #fff;
}

/* 核心：带字幕的遮蔽层样式 */
/* 核心：居左且带左侧空隙的遮蔽层样式 */
.ragflow-mask {
  position: absolute;
  top: 0; /* 遮蔽层在顶部（与原有一致） */
  left: 0;
  right: 0;
  height: 55px; /* 保持原有高度，确保完全遮蔽图标栏 */
  background: #fff; /* 与RAGFlow页面背景一致，无视觉割裂 */
  z-index: 10; /* 高于iframe，确保遮蔽生效 */
  /* 垂直居中+水平居左（带空隙） */
  display: flex;
  align-items: center; /* 垂直居中，确保字幕不偏上偏下 */
  justify-content: flex-start; /* 水平居左，不居中 */
  padding-left: 24px; /* 核心：左侧空隙（24px视觉更舒适，可按需调整） */
  padding-top: 15px;
}

/* 字幕样式（优化视觉效果） */
.mask-title {
  font-size: 28px; /* 字体大小适中，清晰可见 */
  color: #333; /* 深灰色文字，不刺眼且醒目 */
  font-weight: 500; /* 中等加粗，提升层次感 */
  letter-spacing: 0.5px; /* 轻微字距，提升可读性 */
}

/* iframe样式（保留原有，确保在遮蔽层下方） */
.ragflow-iframe {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
  z-index: 1;
}
</style>