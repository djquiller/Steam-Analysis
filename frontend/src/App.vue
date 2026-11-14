<script setup lang="ts">
// 详情页返回大屏时保留大屏状态（筛选、已加载的图表），不重新请求全部接口
</script>

<template>
  <RouterView v-slot="{ Component }">
    <KeepAlive include="Dashboard">
      <component :is="Component" />
    </KeepAlive>
  </RouterView>
</template>
