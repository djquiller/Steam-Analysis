<script setup lang="ts" generic="T extends string | number">
/**
 * 卡片右上角的分段切换（口径、分箱宽度等）。
 * 选中块是独立的一层，切换时弹性滑到新选项下面；按钮等宽，滑块宽度 = 一格。
 */
import { computed } from 'vue'

const props = defineProps<{ options: { value: T; label: string }[] }>()
const model = defineModel<T>({ required: true })

const index = computed(() => Math.max(0, props.options.findIndex((o) => o.value === model.value)))
</script>

<template>
  <div class="seg" :style="{ '--n': options.length, '--i': index }">
    <span class="thumb" aria-hidden="true" />
    <button v-for="o in options" :key="o.value" :class="{ on: model === o.value }" @click="model = o.value">
      {{ o.label }}
    </button>
  </div>
</template>

<style scoped>
.seg {
  position: relative;
  display: grid;
  grid-template-columns: repeat(var(--n), 1fr);
  padding: 4px;
  border-radius: 20px;
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.thumb {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  width: calc((100% - 8px) / var(--n));
  border-radius: 16px;
  background: linear-gradient(110deg, rgba(212, 214, 255, 0.95), rgba(163, 167, 240, 0.85));
  box-shadow: 0 4px 16px rgba(163, 167, 240, 0.35);
  transform: translateX(calc(100% * var(--i)));
  transition: transform 0.55s var(--ease-spring);
}
button {
  position: relative;
  z-index: 1;
  background: transparent;
  border: 0;
  color: var(--text-secondary);
  font-size: var(--fs-small);
  padding: 5px 16px;
  border-radius: 16px;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.35s var(--ease-out);
}
button:hover {
  color: var(--text-primary);
}
button.on {
  color: #16172a;
  font-weight: 600;
}
</style>
