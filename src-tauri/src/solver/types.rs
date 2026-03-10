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
