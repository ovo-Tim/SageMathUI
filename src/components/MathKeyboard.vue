<script setup lang="ts">
import { onMounted } from 'vue';

onMounted(() => {
  const container = document.getElementById('keyboard-container');
  if (container && window.mathVirtualKeyboard) {
    window.mathVirtualKeyboard.container = container;
    window.mathVirtualKeyboard.show();
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
  
  /* MathLive keyboard theme — CSS custom properties cascade into shadow DOM */
  --keyboard-background: var(--color-keyboard-bg);

  /* Toolbar (tab bar) */
  --keyboard-toolbar-text: var(--color-text-primary);
  --keyboard-toolbar-text-active: var(--color-accent-red);
  --keyboard-toolbar-background: transparent;
  --keyboard-toolbar-background-hover: #e8e8ed;
  --keyboard-toolbar-background-selected: transparent;

  /* Keycaps */
  --keycap-background: #ffffff;
  --keycap-background-hover: #f5f5f7;
  --keycap-background-active: #e5e5ea;
  --keycap-text: var(--color-text-primary);
  --keycap-secondary-text: var(--color-text-secondary);
  --keycap-border: transparent;

  /* Variant / action / primary keycaps */
  --variant-keycap-background: #e8e8ed;
  --variant-keycap-text: var(--color-text-primary);

  --action-keycap-background: #d1d1d6;
  --action-keycap-background-active: #c7c7cc;

  --primary-keycap-background: var(--color-accent-red);
  --primary-keycap-background-active: var(--color-accent-red-hover);
  --primary-keycap-text: #ffffff;
}
</style>
