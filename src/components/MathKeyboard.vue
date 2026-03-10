<script setup lang="ts">
import { onMounted } from 'vue';

onMounted(() => {
  const container = document.getElementById('keyboard-container');
  if (container && window.mathVirtualKeyboard) {
    window.mathVirtualKeyboard.container = container;
  }
});
</script>

<template>
  <div id="keyboard-container" class="math-keyboard-container"></div>
</template>

<style scoped>
.math-keyboard-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  width: 100%;
  background-color: var(--color-keyboard-bg);
  
  --keyboard-background: var(--color-keyboard-bg);
  --keycap-background: #ffffff;
  --keycap-background-hover: #f5f5f7;
  --keycap-background-active: #e5e5ea;
  --keycap-text: var(--color-text-primary);
  --keycap-secondary-text: var(--color-text-secondary);
  --keycap-border: transparent;
  --keycap-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  
  --variant-keycap-background: #e8e8ed;
  --variant-keycap-text: var(--color-text-primary);
  
  --action-keycap-background: #d1d1d6;
  --action-keycap-background-active: #c7c7cc;
  
  --primary-keycap-background: var(--color-accent-red);
  --primary-keycap-background-active: var(--color-accent-red-hover);
  --primary-keycap-text: #ffffff;
}

:deep(.ML__keyboard) {
  width: 100% !important;
  height: 100% !important;
  max-height: none !important;
  --keyboard-toolbar-background: transparent !important;
  font-family: var(--font-ui) !important;
}

:deep(.ML__keycap) {
  border-radius: 6px !important;
  transition: transform var(--transition-fast), background-color var(--transition-fast) !important;
  margin: 3px !important;
  font-weight: 500 !important;
}

:deep(.ML__keycap:hover) {
  transform: scale(1.03);
}

:deep(.ML__keycap:active),
:deep(.ML__keycap.is-pressed) {
  transform: scale(0.95);
}

:deep(.ML__toolbar) {
  border-bottom: 1px solid var(--color-divider-light) !important;
}
</style>