<script setup lang="ts">
/**
 * 看板卡片：磨砂玻璃 + 流光描边（公共样式 .glass，见 tokens.css）+ 标题 + 右上角操作区 + 图表区。
 * note（单位与口径说明）是可选的：不传就不显示。说明文字由成员按需手动添加，不自动生成。
 */
defineProps<{ title: string; note?: string }>()
</script>

<template>
  <section class="panel glass">
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
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  padding: 22px 26px 18px;
}
.panel-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: none;
  margin-bottom: 12px;
}
.titles {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 500;
  color: var(--text-strong);
  white-space: nowrap;
  letter-spacing: 0.5px;
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
  z-index: 2; /* 在流光描边层之上，保证图表可点 */
}
</style>
