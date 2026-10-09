<script setup lang="ts">
import { onBeforeUnmount, useId, useTemplateRef, watch } from 'vue'

defineProps<{
  id?: string
  title: string
  eyebrow?: string
  description?: string
}>()

const isOpen = defineModel<boolean>({ required: true })
const dialog = useTemplateRef<HTMLDialogElement>('dialog')
const titleId = useId()
const descriptionId = useId()
let returnFocus: HTMLElement | null = null
let pointerStartedOutside = false

function close() {
  isOpen.value = false
}

function handleClose() {
  // A queued close event must not close a dialog that was reopened meanwhile.
  if (!dialog.value?.open) isOpen.value = false
}

function isOutside(event: PointerEvent | MouseEvent) {
  const element = dialog.value
  if (!element || event.target !== element) return false
  const bounds = element.getBoundingClientRect()
  return event.clientX < bounds.left || event.clientX > bounds.right
    || event.clientY < bounds.top || event.clientY > bounds.bottom
}

function handleBackdropClick(event: MouseEvent) {
  if (pointerStartedOutside && isOutside(event)) close()
  pointerStartedOutside = false
}

watch([isOpen, dialog], ([open, element]) => {
  if (!element) return
  if (open && !element.open) {
    returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    element.showModal()
  } else if (!open && element.open) {
    element.close()
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true })
    returnFocus = null
  }
}, { flush: 'post' })

onBeforeUnmount(() => {
  dialog.value?.close()
  if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true })
})
</script>

<template>
  <Teleport to="body">
    <dialog
      :id="id"
      ref="dialog"
      class="app-modal m-auto rounded-[15px] border border-line bg-porcelain p-0 text-ink shadow-2xl shadow-ink/25 backdrop:bg-ink/55"
      :aria-labelledby="titleId"
      :aria-describedby="description ? descriptionId : undefined"
      @cancel.prevent="close"
      @close="handleClose"
      @pointerdown="pointerStartedOutside = isOutside($event)"
      @click="handleBackdropClick"
    >
      <header class="modal-header flex shrink-0 items-start justify-between gap-5 border-b border-line">
        <div class="flex min-w-0 items-center gap-[13px]">
          <span v-if="$slots.icon" class="grid h-11 w-[41px] shrink-0 place-items-center rounded-[10px] bg-cobalt-soft text-cobalt">
            <slot name="icon" />
          </span>
          <div>
            <p v-if="eyebrow" class="mb-1 text-[9px] font-[650] tracking-[0.14em] text-muted">{{ eyebrow }}</p>
            <h2 :id="titleId" class="text-[22px] font-semibold tracking-[-0.5px] max-[540px]:text-[19px]">{{ title }}</h2>
            <p v-if="description" :id="descriptionId" class="mt-1 text-xs text-muted">{{ description }}</p>
          </div>
        </div>
        <button
          type="button"
          class="grid size-[30px] shrink-0 cursor-pointer place-items-center rounded-md border border-line bg-porcelain hover:bg-ivory"
          :aria-label="`Close ${title}`"
          autofocus
          @click="close"
        >
          <svg class="ui-icon size-[15px]" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M6 18 18 6" /></svg>
        </button>
      </header>
      <div class="modal-body min-h-0 overflow-auto"><slot /></div>
      <footer v-if="$slots.footer" class="modal-footer flex shrink-0 flex-wrap items-center justify-between gap-5 border-t border-line bg-ivory">
        <slot name="footer" :close="close" />
      </footer>
    </dialog>
  </Teleport>
</template>

<style scoped>
.app-modal { width: min(1040px, calc(100vw - 40px)); max-height: calc(100dvh - 64px); }
.app-modal[open] { display: flex; flex-direction: column; }
.modal-header { padding: 23px 25px 20px; }
.modal-body { padding: 21px 25px 24px; }
.modal-footer { padding: 18px 25px; }

@media (max-width: 540px) {
  .app-modal { width: calc(100vw - 20px); max-height: calc(100dvh - 32px); border-radius: 11px; }
  .modal-header, .modal-body { padding: 17px 15px; }
  .modal-footer { padding: 15px; gap: 12px; }
}
</style>
