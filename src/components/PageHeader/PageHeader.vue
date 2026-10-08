<script setup lang="ts">
defineProps<{
  title: string
  subtitle: string
}>()
</script>

<template>
  <header>
    <h1 class="text-[31px] leading-[1.2] font-[620] tracking-[-0.9px] text-ink max-[540px]:text-[29px]">
      {{ title }}
    </h1>
    <p class="mt-2 text-[13px] leading-[1.7] text-muted max-[540px]:text-xs">
      {{ subtitle }}
    </p>
  </header>
</template>
