<script setup lang="ts">
/** 看板卡片：毛玻璃外壳 + 标题 + 单位与口径说明（图表规范要求每张图都写明）+ 右上角操作区 + 图表区 */
defineProps<{ title: string; note?: string }>()
</script>

<template>
  <section class="panel">
    <header class="panel-head">
      <div class="titles">
        <h3 class="title">{{ title }}</h3>
        <span v-if="note" class="note" :title="note">{{ note }}</span>
      </div>
      <div class="actions"><slot name="actions" /></div>
    </header>
    <div class="panel-body"><slot /></div>
  </section>
</template>

<style scoped>
.panel {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  background: linear-gradient(160deg, var(--glass-highlight), transparent 38%), var(--bg-panel);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
  padding: 18px 22px 16px;
  backdrop-filter: blur(14px);
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
/* 左上角一小段发光描边，呼应参考稿的光线感 */
.panel::before {
  content: '';
  position: absolute;
  top: -1px;
  left: 24px;
  width: 120px;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  box-shadow: 0 0 12px var(--accent-glow);
}
.panel-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: none;
  margin-bottom: 10px;
}
.titles {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--text-strong);
  white-space: nowrap;
  letter-spacing: 1px;
}
.note {
  font-size: var(--fs-small);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.actions {
  margin-left: auto;
  display: flex;
  gap: 6px;
  flex: none;
}
.panel-body {
  flex: 1;
  min-height: 0;
  position: relative;
}
</style>
