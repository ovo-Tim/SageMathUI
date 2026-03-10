mod solver;

#[cfg(not(target_os = "android"))]
use solver::LocalSageSolver;
#[cfg(target_os = "android")]
use solver::AndroidSageSolver;
use solver::{OperationType, Solver, SolverRequest, SolverResponse, SolverStatus};
use std::sync::Arc;
use tauri::Manager;
use tokio::sync::Mutex;

pub struct SolverState {
    #[cfg(not(target_os = "android"))]
    solver: Arc<Mutex<LocalSageSolver>>,
    #[cfg(target_os = "android")]
    solver: Arc<Mutex<AndroidSageSolver>>,
}

impl SolverState {
    #[cfg(not(target_os = "android"))]
    pub fn new() -> Self {
        Self {
            solver: Arc::new(Mutex::new(LocalSageSolver::new(None))),
        }
    }

    #[cfg(target_os = "android")]
    pub fn from_android_paths(
        python_binary: std::path::PathBuf,
        python_home: std::path::PathBuf,
        bridge_script: std::path::PathBuf,
        native_lib_dir: std::path::PathBuf,
    ) -> Self {
        Self {
            solver: Arc::new(Mutex::new(AndroidSageSolver::new(
                python_binary,
                python_home,
                bridge_script,
                native_lib_dir,
            ))),
        }
    }
}

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

#[tauri::command]
async fn get_solver_status(state: tauri::State<'_, SolverState>) -> Result<SolverStatus, String> {
    let solver = state.solver.lock().await;
    let status = solver.status().await;
    Ok(status)
}

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
        .setup(|app| {
            #[cfg(not(target_os = "android"))]
            {
                app.manage(SolverState::new());
            }
            #[cfg(target_os = "android")]
            {
                let data_dir = app.path().data_dir()
                    .expect("Failed to get Android data directory");

                let config_path = data_dir.join(".solver_config.json");
                let config_path_alt = data_dir.join("files/.solver_config.json");

                let config_str = std::fs::read_to_string(&config_path)
                    .or_else(|_| std::fs::read_to_string(&config_path_alt))
                    .unwrap_or_else(|_| {
                        let fallback_dir = std::path::PathBuf::from("/data/data/com.sagemath.ui/files");
                        format!(
                            r#"{{"native_lib_dir":"/data/data/com.sagemath.ui/lib/arm64","files_dir":"{}"}}"#,
                            fallback_dir.display()
                        )
                    });
                let config: serde_json::Value = serde_json::from_str(&config_str)
                    .expect("Invalid .solver_config.json");

                let native_lib_dir = std::path::PathBuf::from(
                    config["native_lib_dir"].as_str().unwrap_or("/data/data/com.sagemath.ui/lib/arm64")
                );
                let files_dir = std::path::PathBuf::from(
                    config["files_dir"].as_str().unwrap_or("/data/data/com.sagemath.ui/files")
                );

                let python_binary = native_lib_dir.join("libpython_exec.so");
                let python_home = files_dir.join("python");
                let bridge_script = files_dir.join("sage_bridge.py");

                app.manage(SolverState::from_android_paths(
                    python_binary,
                    python_home,
                    bridge_script,
                    native_lib_dir,
                ));
            }
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
