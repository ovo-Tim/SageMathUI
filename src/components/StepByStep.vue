<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue';
import katex from 'katex';
import 'katex/dist/katex.min.css';

interface Step {
  description: string;
  latex: string;
}

const props = withDefaults(defineProps<{
  steps?: Step[];
  visible?: boolean;
}>(), {
  steps: () => [],
  visible: false
});

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const mathRefs = ref<HTMLElement[]>([]);

const renderMath = () => {
  nextTick(() => {
    if (!props.steps || !mathRefs.value) return;
    
    props.steps.forEach((step, index) => {
      const el = mathRefs.value[index];
      if (el && step.latex) {
        try {
          katex.render(step.latex, el, {
            throwOnError: false,
            displayMode: true,
          });
        } catch (e) {
          console.error('KaTeX render error:', e);
          el.textContent = step.latex;
        }
      }
    });
  });
};

onMounted(() => {
  if (props.visible) {
    renderMath();
  }
});

watch(() => props.steps, () => {
  if (props.visible) {
    renderMath();
  }
}, { deep: true });

watch(() => props.visible, (newVal) => {
  if (newVal) {
    renderMath();
  }
});
</script>

<template>
  <Transition name="expand">
    <div v-show="visible" class="step-by-step-container">
      <div class="header">
        <h3 class="title">Solution Steps</h3>
        <button class="close-btn" @click="emit('close')" aria-label="Close">×</button>
      </div>

      <div class="steps-content" v-if="steps && steps.length > 0">
        <div v-for="(step, index) in steps" :key="index" class="step-item">
          <div class="timeline">
            <div class="circle">{{ index + 1 }}</div>
            <div class="line" v-if="index < steps.length - 1"></div>
          </div>
          <div class="content">
            <div class="description">{{ step.description }}</div>
            <div class="math-content" ref="mathRefs"></div>
          </div>
        </div>
      </div>
      
      <div class="empty-state" v-else>
        No steps available
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.step-by-step-container {
  background: var(--color-white);
  border-radius: var(--radius-card);
  padding: 24px;
  margin-top: 16px;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  border: 1px solid var(--color-divider-light);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-divider-light);
}

.title {
  margin: 0;
  font-size: 16px;
  color: var(--color-text-primary);
  font-weight: 700;
  font-family: var(--font-ui);
  letter-spacing: -0.01em;
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 24px;
  line-height: 1;
  color: var(--color-text-hint);
  cursor: pointer;
  padding: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  border-radius: 50%;
}

.close-btn:hover {
  color: var(--color-accent-red);
  background-color: var(--color-accent-red-light);
}

.close-btn:active {
  transform: scale(0.9);
}

.steps-content {
  display: flex;
  flex-direction: column;
}

.step-item {
  display: flex;
  position: relative;
  align-items: stretch;
}

.timeline {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-right: 16px;
  min-width: 28px;
}

.circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background-color: var(--color-accent-red);
  color: var(--color-white);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  z-index: 2;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(163, 0, 33, 0.2);
  font-family: var(--font-ui);
}

.line {
  width: 2px;
  background: linear-gradient(to bottom, var(--color-divider), var(--color-divider-light));
  flex-grow: 1;
  margin-top: 6px;
  margin-bottom: 6px;
  min-height: 20px;
  border-radius: 1px;
}

.content {
  flex-grow: 1;
  padding-bottom: 24px;
}

.step-item:last-child .content {
  padding-bottom: 4px;
}

.description {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 10px;
  line-height: 1.5;
  font-family: var(--font-ui);
  font-weight: 500;
}

.math-content {
  overflow-x: auto;
  padding: 10px 0;
  font-family: var(--font-math);
  font-size: 18px;
  color: var(--color-text-primary);
}

.empty-state {
  text-align: center;
  color: var(--color-text-hint);
  font-size: 14px;
  padding: 24px 0;
  font-family: var(--font-ui);
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
  max-height: 2000px;
  opacity: 1;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  margin-top: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>