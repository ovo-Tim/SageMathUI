<script setup lang="ts">
import { ref, onMounted } from 'vue';
import MathInput from './components/MathInput.vue';
import MathKeyboard from './components/MathKeyboard.vue';
import ResultDisplay from './components/ResultDisplay.vue';
import StepByStep from './components/StepByStep.vue';
import { useSolverStore } from './stores/solver';

const solver = useSolverStore();
const statusChecking = ref(true);  // Start as "checking" (yellow dot)
const showStatusPopup = ref(false);

function handleSolve() {
  if (solver.latex.trim()) {
    const operation = solver.latex.includes('=') ? 'solve' : 'simplify';
    solver.solveMath(operation);
  }
}

function formatBackendName(name: string): string {
  const map: Record<string, string> = { sage: 'SageMath', sympy: 'SymPy' };
  return map[name] || name;
}

async function handleStatusCheck() {
  statusChecking.value = true;
  showStatusPopup.value = true;
  await solver.checkStatus();
  statusChecking.value = false;
  // Auto-hide after 4 seconds
  setTimeout(() => {
    showStatusPopup.value = false;
  }, 4000);
}

onMounted(async () => {
  // Retry with delay to allow solver subprocess to initialize
  for (let i = 0; i < 3; i++) {
    await new Promise(r => setTimeout(r, 1500));
    await solver.checkStatus();
    if (solver.solverStatus?.connected) break;
  }
  statusChecking.value = false;
});
</script>

<template>
  <div class="calculator-app">
    <!-- Header -->
    <header class="app-header">
      <button class="icon-button status-button" aria-label="Solver Status" @click="handleStatusCheck">
        <span
          class="status-dot"
          :class="{
            'status-sage': solver.solverStatus?.connected && solver.solverStatus?.backend_name === 'sage',
            'status-sympy': solver.solverStatus?.connected && solver.solverStatus?.backend_name === 'sympy',
            'status-disconnected': solver.solverStatus && !solver.solverStatus.connected,
            'status-unknown': !solver.solverStatus,
            'status-checking': statusChecking,
          }"
        ></span>
        <transition name="popup-fade">
          <div v-if="showStatusPopup" class="status-popup">
            <template v-if="statusChecking">
              <span class="status-popup-label">Checking...</span>
            </template>
            <template v-else-if="solver.solverStatus">
              <span class="status-popup-icon" :class="solver.solverStatus.connected ? 'ok' : 'err'">
                {{ solver.solverStatus.connected ? '✓' : '✗' }}
              </span>
              <span class="status-popup-label">{{ formatBackendName(solver.solverStatus.backend_name) }}</span>
              <span v-if="solver.solverStatus.version" class="status-popup-version">
                v{{ solver.solverStatus.version }}
              </span>
            </template>
            <template v-else>
              <span class="status-popup-icon err">✗</span>
              <span class="status-popup-label">No solver</span>
            </template>
          </div>
        </transition>
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

/* Status button & dot */
.status-button {
  position: relative;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: block;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.status-dot.status-sage {
  background-color: #4ade80;
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.6);
}

.status-dot.status-sympy {
  background-color: #fb923c;
  box-shadow: 0 0 6px rgba(251, 146, 60, 0.6);
}

.status-dot.status-disconnected {
  background-color: #f87171;
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.6);
}

.status-dot.status-unknown {
  background-color: #a1a1aa;
  box-shadow: none;
}

.status-dot.status-checking {
  background-color: #facc15;
  box-shadow: 0 0 6px rgba(250, 204, 21, 0.6);
  animation: pulse-dot 1s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Status popup */
.status-popup {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  background: rgba(30, 30, 30, 0.95);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  padding: 8px 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  z-index: 100;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  font-family: var(--font-ui);
  font-size: 13px;
  color: #fff;
}

.status-popup-icon {
  font-size: 14px;
  font-weight: 700;
}

.status-popup-icon.ok {
  color: #4ade80;
}

.status-popup-icon.err {
  color: #f87171;
}

.status-popup-label {
  font-weight: 500;
}

.status-popup-version {
  color: rgba(255, 255, 255, 0.5);
  font-size: 11px;
}

.popup-fade-enter-active,
.popup-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.popup-fade-enter-from,
.popup-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
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
  background-color: var(--color-keyboard-bg);
  flex-shrink: 0;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.08);
  z-index: 10;
  /* Height is set dynamically by MathKeyboard via geometrychange event */
}
</style>