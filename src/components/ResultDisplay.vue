<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const props = withDefaults(defineProps<{
  resultLatex?: string | null
  loading?: boolean
  error?: string | null
}>(), {
  resultLatex: null,
  loading: false,
  error: null
})

const emit = defineEmits<{
  (e: 'show-steps'): void
}>()

const katexContainer = ref<HTMLDivElement | null>(null)

watchEffect(() => {
  if (katexContainer.value) {
    if (props.resultLatex) {
      katex.render(props.resultLatex, katexContainer.value, {
        displayMode: true,
        throwOnError: false
      })
    } else {
      katexContainer.value.innerHTML = ''
    }
  }
})
</script>

<template>
  <Transition name="fade" mode="out-in">
    <div class="result-wrapper" :key="loading ? 'loading' : (error ? 'error' : (resultLatex ? 'result' : 'empty'))">
      <div v-if="loading" class="state-container loading-state">
        <span class="pulse">Solving...</span>
      </div>
      
      <div v-else-if="error" class="state-container error-state">
        {{ error }}
      </div>
      
      <div v-else-if="!resultLatex" class="state-container empty-state">
        Enter an expression above
      </div>
      
      <div v-show="resultLatex && !loading && !error" class="result-content">
        <div ref="katexContainer" class="katex-container serif-font"></div>
        <button 
          v-if="resultLatex" 
          class="show-solution-btn" 
          @click="emit('show-steps')"
        >
          Show Solution
          <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"></line>
            <polyline points="12 5 19 12 12 19"></polyline>
          </svg>
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-slow), transform var(--transition-slow);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.result-wrapper {
  border-left: 3px solid var(--color-accent-red);
  padding: 20px 24px;
  background-color: var(--color-white);
  min-height: 100px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-radius: 0 var(--radius-card) var(--radius-card) 0;
  box-shadow: var(--shadow-sm);
  margin-bottom: 16px;
  transition: all var(--transition-slow);
}

.state-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  min-height: 60px;
  font-family: var(--font-ui);
}

.loading-state .pulse {
  color: var(--color-text-hint);
  font-size: 15px;
  font-weight: 500;
  animation: pulse 1.5s infinite ease-in-out;
}

.error-state {
  color: var(--color-accent-red);
  font-size: 14px;
  text-align: center;
  line-height: 1.5;
}

.empty-state {
  color: var(--color-text-hint);
  font-size: 15px;
}

@keyframes pulse {
  0% { opacity: 0.3; }
  50% { opacity: 1; }
  100% { opacity: 0.3; }
}

.result-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 20px;
  width: 100%;
}

.katex-container {
  width: 100%;
  overflow-x: auto;
  color: var(--color-text-primary);
  display: flex;
  justify-content: flex-end;
  font-size: 24px;
}

.show-solution-btn {
  border: 2px solid var(--color-accent-red);
  border-radius: var(--radius-pill);
  background-color: var(--color-accent-red);
  color: var(--color-white);
  padding: 0 24px;
  min-height: 42px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-normal);
  font-family: var(--font-ui);
  box-shadow: var(--shadow-accent);
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 0.01em;
}

.show-solution-btn:hover {
  background-color: var(--color-accent-red-hover);
  border-color: var(--color-accent-red-hover);
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(163, 0, 33, 0.25);
}

.show-solution-btn:active {
  transform: scale(0.97) translateY(1px);
  box-shadow: 0 2px 6px rgba(163, 0, 33, 0.15);
}
</style>