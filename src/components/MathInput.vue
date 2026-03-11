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
      const backspaceKey = {
        class: 'action',
        label: "<svg><use xlink:href='#svg-delete-backward' /></svg>",
        command: ['performWithFeedback', 'deleteBackward']
      };

      window.mathVirtualKeyboard.layouts = [
        // Tab 1: Arithmetic — matches PhotoMath key4.jpeg
        {
          label: '+ ×',
          tooltip: 'Numbers & Operators',
          rows: [
            [
              { latex: '(#0)', label: '( )' },
              { latex: '>' },
              { latex: '7' },
              { latex: '8' },
              { latex: '9' },
              { latex: '\\div' }
            ],
            [
              { latex: '\\frac{#0}{#0}', class: 'small' },
              { latex: '\\sqrt{#0}' },
              { latex: '4' },
              { latex: '5' },
              { latex: '6' },
              { latex: '\\times' }
            ],
            [
              { latex: '^{#?}', label: 'x<sup>□</sup>' },
              { latex: 'x' },
              { latex: '1' },
              { latex: '2' },
              { latex: '3' },
              { latex: '-' }
            ],
            [
              { latex: '\\pi' },
              { latex: '\\%', label: '%' },
              { latex: '0' },
              { latex: '.' },
              { latex: '=' },
              { latex: '+' }
            ]
          ]
        },
        // Tab 2: Functions — matches PhotoMath key3.jpeg
        {
          label: 'f(x)',
          tooltip: 'Functions',
          rows: [
            [
              { latex: '\\vert #0 \\vert', class: 'small', label: '|□|' },
              { latex: '\\log_{10}', class: 'small', label: 'log₁₀' },
              { latex: '\\log_{2}', class: 'small', label: 'log₂' },
              { latex: '\\log_{#?}', class: 'small', label: 'log<sub>□</sub>' },
              { latex: 'i' },
              { latex: '!' }
            ],
            [
              { latex: '_{#?}', label: 'x<sub>n</sub>' },
              { latex: 'e' },
              { latex: '\\exp', class: 'small' },
              { latex: '\\ln' },
              { latex: '\\overline{#0}', label: 'z̄' },
              { latex: '\\infty' }
            ],
            [
              { latex: '\\sqrt[#?]{#0}', class: 'small', label: '<sup>n</sup>√' },
              { latex: '\\binom{#?}{#?}', class: 'small' },
              { latex: '\\begin{pmatrix}#?&#?\\\\#?&#?\\end{pmatrix}', class: 'small', label: '2×2' },
              { latex: '\\begin{pmatrix}#?&#?&#?\\\\#?&#?&#?\\\\#?&#?&#?\\end{pmatrix}', class: 'small', label: '3×3' },
              { latex: '\\begin{vmatrix}#?&#?\\\\#?&#?\\end{vmatrix}', class: 'small', label: 'det' },
              { latex: '\\operatorname{sign}', class: 'small', label: 'sign' }
            ],
            [
              { latex: '\\le', label: '≤' },
              { latex: '\\ge', label: '≥' },
              { latex: '\\ne', label: '≠' },
              { latex: '\\pm', label: '±' },
              { latex: '<' },
              backspaceKey
            ],
            [
              { latex: '\\cdot', label: '·' },
              { latex: '\\arg', class: 'small', label: 'arg' },
              { latex: '\\Re', label: 'ℜ' },
              { latex: '\\Im', label: 'ℑ' },
              { latex: '\\vec{#0}', class: 'small', label: 'x⃗' },
              { latex: '\\hat{#0}', class: 'small', label: 'x̂' }
            ]
          ]
        },
        // Tab 3: Trigonometry — matches PhotoMath keyboard2.jpeg
        {
          label: 'sin cos',
          tooltip: 'Trigonometry',
          rows: [
            [
              { latex: '^{\\circ}', label: '°' },
              { latex: '\\sin' },
              { latex: '\\cos' },
              { latex: '\\tan' },
              { latex: '\\cot' },
              { latex: '\\sec' }
            ],
            [
              { latex: '\\csc' },
              { latex: '\\arcsin', class: 'small' },
              { latex: '\\arccos', class: 'small' },
              { latex: '\\arctan', class: 'small' },
              { latex: '\\operatorname{arccot}', class: 'small', label: 'arccot' },
              { latex: '\\operatorname{arcsec}', class: 'small', label: 'arcsec' }
            ],
            [
              { latex: '\\theta' },
              { latex: '\\sinh', class: 'small' },
              { latex: '\\cosh', class: 'small' },
              { latex: '\\tanh', class: 'small' },
              { latex: '\\coth', class: 'small' },
              { latex: '\\operatorname{sech}', class: 'small', label: 'sech' }
            ],
            [
              backspaceKey,
              { latex: '\\operatorname{arcsinh}', class: 'small', label: 'arsinh' },
              { latex: '\\operatorname{arccosh}', class: 'small', label: 'arcosh' },
              { latex: '\\operatorname{arctanh}', class: 'small', label: 'artanh' },
              { latex: '\\operatorname{arccoth}', class: 'small', label: 'arcoth' },
              { latex: '\\operatorname{arcsech}', class: 'small', label: 'arsech' }
            ]
          ]
        },
        // Tab 4: Calculus — matches PhotoMath keyboard1.jpeg
        {
          label: '∫ Σ',
          tooltip: 'Calculus',
          rows: [
            [
              { latex: '\\lim_{#? \\to #?}', class: 'small', label: 'lim' },
              { latex: '\\frac{d}{dx}', class: 'small' },
              { latex: '\\int' },
              { latex: '\\frac{dy}{dx}', class: 'small' },
              { latex: 'a_{#?}', class: 'small', label: 'a<sub>n</sub>' },
              { latex: '\\partial' }
            ],
            [
              { latex: '\\lim_{#? \\to #?^{+}}', class: 'small', label: 'lim⁺' },
              { latex: '\\frac{d}{d#?}', class: 'small' },
              { latex: '\\int_{#?}^{#?}', class: 'small' },
              { latex: 'dx' },
              { latex: 'dy' },
              { latex: 'dz' }
            ],
            [
              { latex: '\\lim_{#? \\to #?^{-}}', class: 'small', label: 'lim⁻' },
              { latex: '\\frac{d^{2}}{d#?^{2}}', class: 'small' },
              { latex: '\\sum_{#?}^{#?}', class: 'small' },
              { latex: '\\prod_{#?}^{#?}', class: 'small' },
              { latex: 'dt' },
              { latex: '\\infty' }
            ],
            [
              { latex: "'", label: "y'" },
              { latex: '\\sum', class: 'small' },
              { latex: '\\prod', class: 'small' },
              { latex: '\\to', label: '→' },
              { latex: '\\Rightarrow', label: '⇒' },
              backspaceKey
            ]
          ]
        }
      ];
    }

    // Disable context-menu items that cause "Malformed expression" errors
    mathfield.menuItems = mathfield.menuItems.filter(
      (item: any) => !['color', 'background-color', 'variant'].includes(item.id)
    );

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