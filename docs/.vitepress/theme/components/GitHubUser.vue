<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  username: string
  avatar?: string
}>()

const link = computed(() => `https://github.com/${props.username}`)
const avatarUrl = computed(() => props.avatar || `https://github.com/${props.username}.png`)
</script>

<template>
  <a :href="link" :title="username" target="_blank" class="user">
    <img :src="avatarUrl" :title="username" class="avatar" />
  </a>
</template>

<style scoped>
.user {
  margin: 10px 10px;
  display: inline-block;
}

.avatar {
  border-radius: 10px;
  border: 2px solid white;
  box-shadow: 2px 2px 2px 2px;
  width: 100%;
  height: 100%;
  width: 54px;
  height: 54px;
}

.avatar:hover {
  animation: tada 1s 0.2s ease both;
  -moz-animation: tada 1s 0.2s ease both;
}

@keyframes tada {
  0% {
    -webkit-transform: scale(1);
  }

  10%,
  20% {
    -webkit-transform: scale(0.9) rotate(-3deg);
  }

  30%,
  50%,
  70%,
  90% {
    -webkit-transform: scale(1.1) rotate(3deg);
  }

  40%,
  60%,
  80% {
    -webkit-transform: scale(1.1) rotate(-3deg);
  }

  100% {
    -webkit-transform: scale(1) rotate(0);
  }
}
</style>
