<script setup lang="ts">
/** 实时在线榜：60 秒轮询，列表自动滚动；和上一个采集时刻比较显示升降 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { rankApi } from '@/api'
import IconButton from '@/components/layout/IconButton.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { intNum } from '@/theme/format'

const router = useRouter()
const r = useRemote((s) => rankApi.onlineLive(20, s), [], { pollMs: 60_000 })
const items = computed(() => r.data.value?.items ?? [])

const SCROLL_MIN = 7

/** 超过一屏时把列表拼两遍，配合 translateY(-50%) 做无缝循环滚动 */
const rows = computed(() => {
  const list = items.value.map((it) => {
    const d = it.player_count_prev ? (it.player_count - it.player_count_prev) / it.player_count_prev : null
    return { ...it, delta: d }
  })
  return list.length >= SCROLL_MIN ? [...list, ...list] : list
})
</script>

<template>
  <Panel title="实时在线榜">
    <div v-if="items.length" class="list" :class="{ scroll: items.length >= SCROLL_MIN }">
      <div class="track">
        <div v-for="(it, i) in rows" :key="i" class="row" @click="router.push(`/game/${it.appid}`)">
          <span class="rank" :class="{ top: it.rank <= 3 }">{{ it.rank }}</span>
          <span class="name" :title="it.name">{{ it.name }}</span>
          <span class="count">{{ intNum(it.player_count) }}</span>
          <span class="delta" :class="{ up: (it.delta ?? 0) > 0, down: (it.delta ?? 0) < 0 }">
            <template v-if="it.delta === null">—</template>
            <template v-else>{{ it.delta >= 0 ? '▲' : '▼' }} {{ Math.abs(it.delta * 100).toFixed(1) }}%</template>
          </span>
        </div>
      </div>
    </div>
    <div v-else class="state">
      <template v-if="r.state.value === 'loading'">加载中…</template>
      <template v-else-if="r.state.value === 'error'">
        <span class="err">{{ r.error.value }}</span>
        <IconButton icon="retry" label="重试" :size="42" @click="r.reload" />
      </template>
      <template v-else>还没有在线人数榜单（等待每小时快照聚合）</template>
    </div>
    <div v-if="r.state.value === 'error' && items.length" class="stale">数据未更新</div>
  </Panel>
</template>

<style scoped>
.list {
  height: 100%;
  overflow: hidden;
}
.list.scroll .track {
  animation: roll 40s linear infinite;
}
.list.scroll:hover .track {
  animation-play-state: paused;
}
@keyframes roll {
  to {
    transform: translateY(-50%);
  }
}
.row {
  display: grid;
  grid-template-columns: 44px 1fr 130px 100px;
  align-items: center;
  height: 52px;
  padding: 0 10px;
  font-size: 18px;
  border-radius: 8px;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.06);
  cursor: pointer;
}
.row:hover {
  background: var(--accent-dim);
}
.rank {
  font-family: var(--font-number);
  color: var(--text-secondary);
}
.rank.top {
  color: var(--accent);
  font-weight: 700;
}
.name {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.count {
  text-align: right;
  font-family: var(--font-number);
  font-size: 20px;
  color: var(--text-strong);
}
.delta {
  text-align: right;
  font-size: var(--fs-small);
  color: var(--text-secondary);
}
.delta.up {
  color: var(--positive);
}
.delta.down {
  color: var(--negative);
}
.state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 18px;
}
.err {
  color: var(--negative);
}
.stale {
  position: absolute;
  top: 0;
  right: 0;
  font-size: var(--fs-small);
  color: var(--warning);
}
</style>
