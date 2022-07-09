<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { MAX_Z_INDEX } from '@moefy-canvas/core'
import { Sparkler, SparklerMode } from '@moefy-canvas/theme-sparkler'

const el = ref(null)
const sparkler = new Sparkler(
  {
    mode: SparklerMode.TRAIL,
  },
  {
    opacity: 1,
    zIndex: MAX_Z_INDEX,
  }
)

onMounted(() => {
  sparkler.mount(el.value!)
})

onBeforeUnmount(() => {
  sparkler.unmount()
})
</script>

<template>
  <canvas ref="el"></canvas>
</template>
