import { defineStore } from 'pinia';
import { ref } from 'vue';
import { invoke } from '@tauri-apps/api/core';

// Types
export interface SolutionStep {
  description: string;
  latex: string;
}

export interface SolverResponse {
  success: boolean;
  result_latex: string | null;
  steps: SolutionStep[];
  error: string | null;
}

export interface SolverStatus {
  connected: boolean;
  backend_name: string;
  version: string | null;
}

export interface DebugPathEntry {
  name: string;
  path: string;
  exists: boolean;
}

export interface DebugInfo {
  paths: DebugPathEntry[];
  solver_status: SolverStatus;
  python_stderr: string[];
  startup_error: string | null;
  lib_dynload_files: string[];
  stdlib_entries: string[];
  config_json: string | null;
  extra_info: string[];
}

export const useSolverStore = defineStore('solver', () => {
  // State
  const latex = ref('');
  const resultLatex = ref<string | null>(null);
  const steps = ref<SolutionStep[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const showSteps = ref(false);
  const solverStatus = ref<SolverStatus | null>(null);
  const debugInfo = ref<DebugInfo | null>(null);

  // Actions
  async function solveMath(operation: string = 'solve', variable?: string) {
    // Reset previous state
    error.value = null;
    resultLatex.value = null;
    steps.value = [];
    loading.value = true;

    try {
      const payload: { latex: string; operation: string; variable?: string } = {
        latex: latex.value,
        operation,
      };

      if (variable) {
        payload.variable = variable;
      }

      const response = await invoke<SolverResponse>('solve_math', payload);
      console.log('[DEBUG] Response:', JSON.stringify(response));

      if (response.success) {
        resultLatex.value = response.result_latex;
        steps.value = response.steps || [];
      } else {
        error.value = response.error || 'Unknown error occurred';
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to solve';
      console.error('Solve error:', err);
    } finally {
      loading.value = false;
    }
  }

  function toggleSteps() {
    showSteps.value = !showSteps.value;
  }

  function clearResult() {
    resultLatex.value = null;
    steps.value = [];
    error.value = null;
    showSteps.value = false;
  }

  async function checkStatus() {
    try {
      const status = await invoke<SolverStatus>('get_solver_status');
      solverStatus.value = status;
      return status;
    } catch (err) {
      console.error('Status check error:', err);
      solverStatus.value = null;
      return null;
    }
  }

  async function shutdownSolver() {
    try {
      await invoke('shutdown_solver');
      solverStatus.value = null;
    } catch (err) {
      console.error('Shutdown error:', err);
    }
  }

  async function getDebugInfo() {
    try {
      const info = await invoke<DebugInfo>('get_debug_info');
      debugInfo.value = info;
      return info;
    } catch (err) {
      console.error('Debug info error:', err);
      debugInfo.value = null;
      return null;
    }
  }

  return {
    // State
    latex,
    resultLatex,
    steps,
    loading,
    error,
    showSteps,
    solverStatus,
    debugInfo,
    // Actions
    solveMath,
    toggleSteps,
    clearResult,
    checkStatus,
    shutdownSolver,
    getDebugInfo,
  };
});
