<script setup lang="ts">
defineProps<{ name: keyof typeof paths }>()

const paths = {
  add: 'M12 5v14M5 12h14',
  rules: 'M10 6h11M10 12h11M10 18h11M3 5l1 1 2-2M3 11l1 1 2-2M3 17l1 1 2-2',
  chevron: 'm9 5 7 7-7 7',
}
</script>

<template>
  <svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path :d="paths[name]" /></svg>
</template>
