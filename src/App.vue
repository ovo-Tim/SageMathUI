<script setup lang="ts">
import MathInput from './components/MathInput.vue';
import MathKeyboard from './components/MathKeyboard.vue';
import ResultDisplay from './components/ResultDisplay.vue';
import StepByStep from './components/StepByStep.vue';
import { useSolverStore } from './stores/solver';

const solver = useSolverStore();

function handleSolve() {
  if (solver.latex.trim()) {
    const operation = solver.latex.includes('=') ? 'solve' : 'simplify';
    solver.solveMath(operation);
  }
}
</script>

<template>
  <div class="calculator-app">
    <!-- Header -->
    <header class="app-header">
      <button class="icon-button" aria-label="Back">
        <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
      </button>
      <h1 class="header-title">Calculator</h1>
      <button class="icon-button" aria-label="History">
        <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <polyline points="12 6 12 12 16 14"></polyline>
        </svg>
      </button>
    </header>

    <!-- Main Content -->
    <main class="app-content">
      <div class="input-zone serif-font">
        <MathInput v-model="solver.latex" />
      </div>

      <div class="divider-wrapper">
        <div class="divider"></div>
        <button class="solve-button" @click="handleSolve" :disabled="!solver.latex.trim() || solver.loading">
          <span v-if="solver.loading" class="spinner"></span>
          <template v-else>
            <span class="solve-text">Solve</span>
            <svg class="solve-arrow" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </template>
        </button>
      </div>
      
      <div class="result-zone">
        <ResultDisplay
          :result-latex="solver.resultLatex"
          :loading="solver.loading"
          :error="solver.error"
          @show-steps="solver.toggleSteps"
        />

        <StepByStep
          :steps="solver.steps"
          :visible="solver.showSteps"
          @close="solver.toggleSteps"
        />
      </div>
    </main>

    <!-- Keyboard Area -->
    <footer class="app-keyboard">
      <MathKeyboard />
    </footer>
  </div>
</template>

<style scoped>
.calculator-app {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background-color: var(--color-white);
}

.app-header {
  height: 50px;
  background-color: var(--color-header-bg);
  color: var(--color-white);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  flex-shrink: 0;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  z-index: 10;
}

.icon-button {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.85);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  min-width: 44px;
  min-height: 44px;
  border-radius: 50%;
  transition: all var(--transition-fast);
}

.icon-button:hover {
  color: var(--color-white);
  background-color: rgba(255, 255, 255, 0.1);
}

.icon-button:active {
  transform: scale(0.92);
  background-color: rgba(255, 255, 255, 0.15);
}

.header-title {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
  font-family: var(--font-ui);
  letter-spacing: 0.01em;
}

.app-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 24px 20px;
}

.input-zone {
  display: flex;
  flex-direction: column;
  min-height: 80px;
  margin-bottom: 16px;
  width: 100%;
}

.divider-wrapper {
  position: relative;
  margin-bottom: 24px;
}

.solve-button {
  position: absolute;
  top: 50%;
  right: 0;
  transform: translateY(-50%);
  z-index: 2;
  background: var(--color-accent-red);
  color: var(--color-white);
  border: none;
  border-radius: var(--radius-pill);
  padding: 0 28px;
  min-width: 110px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  box-shadow: var(--shadow-accent);
  transition: all var(--transition-normal);
  font-family: var(--font-ui);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.solve-button:hover:not(:disabled) {
  background: var(--color-accent-red-hover);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(163, 0, 33, 0.3);
}

.solve-button:active:not(:disabled) {
  transform: scale(0.97) translateY(1px);
  box-shadow: 0 2px 6px rgba(163, 0, 33, 0.2);
}

.solve-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.solve-text {
  line-height: 1;
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2.5px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #fff;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.divider {
  border: none;
  border-top: 1px dashed var(--color-divider);
  margin: 0 -20px;
}

.result-zone {
  display: flex;
  flex-direction: column;
}

.app-keyboard {
  height: 280px;
  background-color: var(--color-keyboard-bg);
  flex-shrink: 0;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.08);
  z-index: 10;
}
</style>