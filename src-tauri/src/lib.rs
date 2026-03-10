mod solver;

use solver::{OperationType, SolverRequest, SolverResponse, SubprocessSolver, Solver};
use std::sync::Arc;
use tokio::sync::Mutex;

// Global solver instance (will be initialized at app startup)
lazy_static::lazy_static! {
    static ref SOLVER: Arc<Mutex<Option<Arc<dyn Solver>>>> = Arc::new(Mutex::new(None));
}

/// Initialize the math solver with paths to Python and bridge script
#[tauri::command]
async fn initialize_solver(python_path: String, bridge_script: String) -> Result<String, String> {
    let solver = Arc::new(SubprocessSolver::new(python_path, bridge_script));
    let mut global_solver = SOLVER.lock().await;
    *global_solver = Some(solver);
    Ok("Solver initialized successfully".to_string())
}

/// Solve a math expression
#[tauri::command]
async fn solve_math(
    latex: String,
    operation: String,
    variable: Option<String>,
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

    let global_solver = SOLVER.lock().await;
    match global_solver.as_ref() {
        Some(solver) => solver.solve(request).await,
        None => Err("Solver not initialized. Call initialize_solver first.".to_string()),
    }
}

/// Get solver status
#[tauri::command]
async fn get_solver_status() -> Result<String, String> {
    let global_solver = SOLVER.lock().await;
    match global_solver.as_ref() {
        Some(solver) => {
            let status = solver.status().await;
            Ok(format!(
                "Backend: {}, Connected: {}, Version: {:?}",
                status.backend_name, status.connected, status.version
            ))
        }
        None => Ok("Solver not initialized".to_string()),
    }
}

/// Shutdown the solver
#[tauri::command]
async fn shutdown_solver() -> Result<String, String> {
    let global_solver = SOLVER.lock().await;
    if let Some(solver) = global_solver.as_ref() {
        solver.shutdown().await;
    }
    Ok("Solver shut down".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            initialize_solver,
            solve_math,
            get_solver_status,
            shutdown_solver
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// Simple greeting function for compatibility
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}
