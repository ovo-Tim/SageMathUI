<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue';

let cleanupGeometry: (() => void) | null = null;

onMounted(() => {
  const container = document.getElementById('keyboard-container');
  if (container && window.mathVirtualKeyboard) {
    window.mathVirtualKeyboard.container = container;

    // Dynamically resize container to match keyboard height (fixes top-alignment)
    const onGeometryChange = () => {
      const rect = window.mathVirtualKeyboard.boundingRect;
      if (rect && rect.height > 0) {
        container.style.height = `${rect.height}px`;
      }
    };

    window.mathVirtualKeyboard.addEventListener('geometrychange', onGeometryChange);
    cleanupGeometry = () => {
      window.mathVirtualKeyboard.removeEventListener('geometrychange', onGeometryChange);
    };

    window.mathVirtualKeyboard.show();
  }
});

onBeforeUnmount(() => {
  cleanupGeometry?.();
});
</script>

<template>
  <div id="keyboard-container" class="math-keyboard-container"></div>
</template>

<style scoped>
.math-keyboard-container {
  display: flex;
  justify-content: center;
  align-items: flex-start;
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
  --keycap-height: 48px;
  --keycap-max-width: 200px;
  --keycap-width: 15.5cqw;
  --keycap-gap: 2px;
  --keycap-font-size: 16px;
  --keycap-small-font-size: 12px;
  --keycap-extra-small-font-size: 10px;
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
