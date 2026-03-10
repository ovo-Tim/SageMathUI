<script setup lang="ts">
import MathInput from './components/MathInput.vue';
import MathKeyboard from './components/MathKeyboard.vue';
import ResultDisplay from './components/ResultDisplay.vue';
import StepByStep from './components/StepByStep.vue';
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
        <MathInput />
        <!-- Placeholder for math input -->
        <div class="math-expression">2x + 5 = 11</div>
      </div>
      
      <div class="divider"></div>
      
      <div class="result-zone">
        <div class="result-content">
          <ResultDisplay />
          <!-- Placeholder for result -->
          <div class="math-result serif-font">x = 3</div>
        </div>
        
        <button class="show-solution-btn">
          <span>Show Solution</span>
          <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>

        <StepByStep />
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
  padding: 0 16px;
  flex-shrink: 0;
}

.icon-button {
  background: none;
  border: none;
  color: var(--color-white);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
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
  align-items: flex-end;
  min-height: 80px;
  margin-bottom: 20px;
}

.math-expression {
  font-size: 28px;
  color: var(--color-text-primary);
  width: 100%;
  text-align: right;
}

.divider {
  border-top: 1px dashed var(--color-divider);
  margin: 0 -20px 20px -20px; /* Bleed to edges */
}

.result-zone {
  display: flex;
  flex-direction: column;
}

.result-content {
  display: flex;
  flex-direction: column;
  border-left: 4px solid var(--color-result-bar);
  padding-left: 16px;
  margin-bottom: 24px;
}

.math-result {
  font-size: 24px;
  font-weight: bold;
  color: var(--color-text-primary);
  text-align: left;
}

.show-solution-btn {
  align-self: flex-start;
  background-color: var(--color-accent-red);
  color: var(--color-white);
  border: none;
  border-radius: 999px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  margin-left: 20px; /* align with result text visually */
}

.app-keyboard {
  height: 280px;
  background-color: var(--color-keyboard-bg);
  flex-shrink: 0;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
}
</style>
