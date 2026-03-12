use serde::{Deserialize, Serialize};

/// The type of math operation requested
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OperationType {
    Solve,         // solve equations
    Simplify,      // simplify expressions
    Differentiate, // differentiate
    Integrate,     // integrate
    Factor,        // factor polynomials
    Expand,        // expand expressions
    Limit,         // compute limits
    Evaluate,      // evaluate numerically
}

/// Request sent to the solver
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolverRequest {
    /// LaTeX input expression
    pub latex: String,
    /// Type of operation to perform
    pub operation: OperationType,
    /// Optional variable to solve for / differentiate with respect to
    pub variable: Option<String>,
}

/// A single step in the solution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolutionStep {
    /// Human-readable description of this step
    pub description: String,
    /// LaTeX representation of the expression at this step
    pub latex: String,
}

/// Response from the solver
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolverResponse {
    /// Whether the solve was successful
    pub success: bool,
    /// The result as LaTeX (if successful)
    pub result_latex: Option<String>,
    /// Step-by-step solution (may be empty if not available)
    pub steps: Vec<SolutionStep>,
    /// Error message (if failed)
    pub error: Option<String>,
}

/// Status of the solver backend
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolverStatus {
    pub connected: bool,
    pub backend_name: String,
    pub version: Option<String>,
}

/// A single path entry for debug info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DebugPathEntry {
    pub name: String,
    pub path: String,
    pub exists: bool,
}

/// Debug information for diagnosing Android issues
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DebugInfo {
    /// Key paths and whether they exist
    pub paths: Vec<DebugPathEntry>,
    /// Current solver status
    pub solver_status: SolverStatus,
    /// Captured Python stderr lines (last N lines)
    pub python_stderr: Vec<String>,
    /// Startup error if Python failed to start
    pub startup_error: Option<String>,
    /// Files in lib-dynload/ directory
    pub lib_dynload_files: Vec<String>,
    /// Top-level entries in python/lib/python3.13/
    pub stdlib_entries: Vec<String>,
    /// Raw config JSON that was read
    pub config_json: Option<String>,
    /// Device/environment info
    pub extra_info: Vec<String>,
}
