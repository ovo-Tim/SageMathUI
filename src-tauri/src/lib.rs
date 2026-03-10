mod solver;

use solver::{LocalSageSolver, OperationType, Solver, SolverRequest, SolverResponse, SolverStatus};
use std::sync::Arc;
use tokio::sync::Mutex;

/// Managed state containing the solver instance
pub struct SolverState {
    solver: Arc<Mutex<LocalSageSolver>>,
}

impl SolverState {
    /// Create a new SolverState with auto-detected sage path
    pub fn new() -> Self {
        Self {
            solver: Arc::new(Mutex::new(LocalSageSolver::new(None))),
        }
    }
}

/// Solve a math expression
#[tauri::command]
async fn solve_math(
    latex: String,
    operation: String,
    variable: Option<String>,
    state: tauri::State<'_, SolverState>,
) -> Result<SolverResponse, String> {
    let op_type = match operation.to_lowercase().as_str() {
        "solve" => OperationType::Solve,
        "simplify" => OperationType::Simplify,
        "differentiate" => OperationType::Differentiate,
        "integrate" => OperationType::Integrate,
        "factor" => OperationType::Factor,
        "expand" => OperationType::Expand,
        "limit" => OperationType::Limit,
        "evaluate" => OperationType::Evaluate,
        _ => return Err(format!("Unknown operation: {}", operation)),
    };

    let request = SolverRequest {
        latex,
        operation: op_type,
        variable,
    };

    let solver = state.solver.lock().await;
    solver.solve(request).await
}

/// Get solver status
#[tauri::command]
async fn get_solver_status(state: tauri::State<'_, SolverState>) -> Result<SolverStatus, String> {
    let solver = state.solver.lock().await;
    let status = solver.status().await;
    Ok(status)
}

/// Shutdown the solver
#[tauri::command]
async fn shutdown_solver(state: tauri::State<'_, SolverState>) -> Result<String, String> {
    let solver = state.solver.lock().await;
    solver.shutdown().await;
    Ok("Solver shut down".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(SolverState::new())
        .setup(|_app| {
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            solve_math,
            get_solver_status,
            shutdown_solver
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
