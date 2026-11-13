<script setup lang="ts" generic="T extends string | number">
/** 卡片右上角的分段切换按钮（口径、分箱宽度等），统一样式与尺寸 */
defineProps<{ options: { value: T; label: string }[] }>()
const model = defineModel<T>({ required: true })
</script>

<template>
  <div class="seg">
    <button v-for="o in options" :key="o.value" :class="{ on: model === o.value }" @click="model = o.value">
      {{ o.label }}
    </button>
  </div>
</template>

<style scoped>
.seg {
  display: inline-flex;
  padding: 3px;
  gap: 2px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--glass-border);
}
button {
  background: transparent;
  border: 0;
  color: var(--text-secondary);
  font-size: var(--fs-small);
  padding: 4px 14px;
  border-radius: 7px;
  cursor: pointer;
}
button.on {
  color: var(--bg-base);
  background: var(--accent);
  font-weight: 600;
}
</style>
