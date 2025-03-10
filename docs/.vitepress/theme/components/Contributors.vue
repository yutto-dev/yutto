<script setup lang="ts">
import GitHubUser from './GitHubUser.vue'
import { ref, onMounted, type Ref } from 'vue'

interface Contributor {
  login: string
  avatar_url: string
}

const props = defineProps<{
  owner: string
  repo: string
}>()

const contributors: Ref<Contributor[]> = ref([])

onMounted(() => {
  const url = `https://api.github.com/repos/${props.owner}/${props.repo}/contributors`
  fetch(url)
    .then((response) => {
      return response.json()
    })
    .then((res) => {
      return res.filter((contributor: Contributor) => {
        return !contributor.login.endsWith('[bot]')
      })
    })
    .then((res) => {
      contributors.value = res
    })
})
</script>

<template>
  <div class="github-contributors">
    <GitHubUser
      v-for="contributor in contributors"
      :username="contributor.login"
      :avatar="contributor.avatar_url"
    />
  </div>
</template>
