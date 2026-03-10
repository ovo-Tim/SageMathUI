<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import 'mathlive';
import type { MathfieldElement } from 'mathlive';

const props = defineProps<{
  modelValue?: string;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'update:latex', value: string): void;
}>();

const mfe = ref<MathfieldElement | null>(null);

onMounted(() => {
  if (mfe.value) {
    const mathfield = mfe.value;
    
    // Set the policy to manual so we control when the keyboard appears
    mathfield.mathVirtualKeyboardPolicy = 'manual';

    // Configure Custom Keyboard Layouts
    if (window.mathVirtualKeyboard) {
      window.mathVirtualKeyboard.layouts = [
        {
          label: '123',
          tooltip: 'Basic',
          rows: [
            [
              { latex: 'x' }, { latex: '^' }, { latex: '\\sqrt{#0}' }, { latex: '(' }, { latex: ')' }
            ],
            [
              { latex: '7' }, { latex: '8' }, { latex: '9' }, { latex: '\\times' }, { latex: '\\div' }
            ],
            [
              { latex: '4' }, { latex: '5' }, { latex: '6' }, { latex: '+' }, { latex: '-' }
            ],
            [
              { latex: '1' }, { latex: '2' }, { latex: '3' }, { latex: '=' }, {
                class: 'action',
                label: "<svg><use xlink:href='#svg-delete-backward' /></svg>",
                command: ['performWithFeedback', 'deleteBackward']
              }
            ],
            [
              { latex: '0', width: 2 }, { latex: '.' }, { latex: ',' }
            ]
          ]
        },
        {
          label: 'ƒ(x)',
          tooltip: 'Functions',
          rows: [
            [
              { latex: '\\sin' }, { latex: '\\cos' }, { latex: '\\tan' }
            ],
            [
              { latex: '\\log' }, { latex: '\\ln' }, { latex: '\\vert #0 \\vert' }
            ],
            [
              { latex: '!' }, { latex: '\\pi' }, { latex: 'e' }, { latex: '\\infty' }
            ]
          ]
        },
        {
          label: 'Trig',
          tooltip: 'Trig',
          rows: [
            [
              { latex: '\\sin^{-1}' }, { latex: '\\cos^{-1}' }, { latex: '\\tan^{-1}' }
            ],
            [
              { latex: '\\sinh' }, { latex: '\\cosh' }, { latex: '\\tanh' }
            ],
            [
              { latex: '\\sec' }, { latex: '\\csc' }, { latex: '\\cot' }
            ]
          ]
        },
        {
          label: '∫ d/dx',
          tooltip: 'Calculus',
          rows: [
            [
              { latex: '\\int' }, { latex: '\\frac{d}{dx}' }, { latex: '\\lim' }
            ],
            [
              { latex: '\\sum' }, { latex: '\\prod' }, { latex: '\\partial' }
            ],
            [
              { latex: 'dx' }, { latex: 'dy' }, { latex: 'dz' }
            ]
          ]
        }
      ];
    }

    // Set initial value
    if (props.modelValue) {
      mathfield.value = props.modelValue;
    }

    // Listeners
    mathfield.addEventListener('input', handleInput);
    mathfield.addEventListener('focus', handleFocus);
    mathfield.addEventListener('blur', handleBlur);
  }
});

onBeforeUnmount(() => {
  if (mfe.value) {
    mfe.value.removeEventListener('input', handleInput);
    mfe.value.removeEventListener('focus', handleFocus);
    mfe.value.removeEventListener('blur', handleBlur);
  }
});

watch(() => props.modelValue, (newVal) => {
  if (mfe.value && newVal !== undefined && mfe.value.value !== newVal) {
    mfe.value.value = newVal;
  }
});

function handleInput(e: Event) {
  const target = e.target as MathfieldElement;
  const val = target.value;
  emit('update:modelValue', val);
  emit('update:latex', val);
}

function handleFocus() {
  if (window.mathVirtualKeyboard) {
    window.mathVirtualKeyboard.show();
  }
}

function handleBlur() {
  // Keep keyboard visible — calculator always shows its keypad
}

function clearField() {
  if (mfe.value) {
    mfe.value.value = '';
    mfe.value.focus();
    emit('update:modelValue', '');
    emit('update:latex', '');
  }
}
</script>

<template>
  <div class="math-input-wrapper">
    <div class="input-container">
      <math-field ref="mfe" class="math-field"></math-field>
      <button class="clear-btn" @click="clearField" aria-label="Clear input">
        <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.math-input-wrapper {
  width: 100%;
  display: flex;
  justify-content: flex-end;
}

.input-container {
  display: flex;
  align-items: center;
  width: 100%;
  background-color: var(--color-white);
  border-bottom: 2px solid transparent;
  transition: border-color var(--transition-normal);
  padding: 8px 0;
  min-height: 44px;
}

.input-container:focus-within {
  border-bottom-color: var(--color-accent-red);
}

.math-field {
  flex-grow: 1;
  font-size: 28px;
  font-family: var(--font-math);
  text-align: right;
  --caret-color: var(--color-accent-red);
  background-color: transparent;
  padding: 8px 12px;
  border: none;
  outline: none;
  color: var(--color-text-primary);
  --contains-highlight-back-color: transparent;
  --selection-background-color: rgba(163, 0, 33, 0.15);
  --smart-fence-color: var(--color-text-secondary);
  --placeholder-color: var(--color-text-hint);
}

math-field::part(virtual-keyboard-toggle) {
  display: none;
}

.clear-btn {
  background: none;
  border: none;
  color: var(--color-text-hint);
  cursor: pointer;
  padding: 10px;
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  border-radius: 50%;
  flex-shrink: 0;
}

.clear-btn:hover {
  color: var(--color-accent-red);
  background-color: var(--color-accent-red-light);
}

.clear-btn:active {
  transform: scale(0.9);
  background-color: rgba(163, 0, 33, 0.12);
}
</style>