<script setup lang="ts">
/** 看板面板：标题 + 单位与口径说明（图表规范要求每张图都写明）+ 右上角操作区 + 图表区 */
defineProps<{ title: string; note?: string }>()
</script>

<template>
  <section class="panel">
    <header class="panel-head">
      <h3 class="title">{{ title }}</h3>
      <span v-if="note" class="note" :title="note">{{ note }}</span>
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
  background: linear-gradient(180deg, rgba(42, 71, 94, 0.35), rgba(27, 40, 56, 0.9) 40px), var(--bg-panel);
  border: 1px solid rgba(102, 192, 244, 0.14);
  border-radius: var(--radius);
  padding: 10px 14px 10px;
}
.panel-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  height: 26px;
  flex: none;
}
.title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-strong);
  white-space: nowrap;
  padding-left: 8px;
  border-left: 3px solid var(--accent);
  line-height: 1;
}
.note {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
  flex: none;
}
.panel-body {
  flex: 1;
  min-height: 0;
  position: relative;
}
</style>
