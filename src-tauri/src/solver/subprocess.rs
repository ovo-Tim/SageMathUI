use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};
use std::sync::Arc;
use std::pin::Pin;
use std::future::Future;
use tokio::sync::Mutex;

use super::types::{SolverRequest, SolverResponse, SolverStatus};
use super::Solver;

/// Subprocess-based solver that communicates with sage_bridge.py via JSON stdin/stdout
pub struct SubprocessSolver {
    /// Path to the Python interpreter (e.g., /data/data/com.example.app/files/python)
    python_path: String,
    /// Path to sage_bridge.py
    bridge_script: String,
    /// Cached solver status
    status: Arc<Mutex<SolverStatus>>,
}

impl SubprocessSolver {
    /// Create a new subprocess solver
    /// 
    /// # Arguments
    /// * `python_path` - Path to python3 executable
    /// * `bridge_script` - Path to sage_bridge.py
    pub fn new(python_path: String, bridge_script: String) -> Self {
        Self {
            python_path,
            bridge_script,
            status: Arc::new(Mutex::new(SolverStatus {
                connected: false,
                backend_name: "SageSubprocess".to_string(),
                version: Some("0.1.0".to_string()),
            })),
        }
    }

    /// Spawn and communicate with the bridge process
    async fn communicate(&self, request: &SolverRequest) -> Result<SolverResponse, String> {
        let mut child = Command::new(&self.python_path)
            .arg(&self.bridge_script)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn solver process: {}", e))?;

        // Write request to stdin
        {
            let stdin = child.stdin.as_mut().ok_or("Failed to open stdin")?;
            let request_json = serde_json::json!({
                "operation": format!("{:?}", request.operation).to_lowercase(),
                "latex": request.latex,
                "variable": request.variable.as_deref().unwrap_or("x"),
            });
            stdin
                .write_all(serde_json::to_string(&request_json).unwrap().as_bytes())
                .map_err(|e| format!("Failed to write to solver: {}", e))?;
            stdin.write_all(b"\n").map_err(|e| format!("Failed to write newline: {}", e))?;
        }

        // Read response from stdout
        let stdout = child.stdout.take().ok_or("Failed to open stdout")?;
        let reader = BufReader::new(stdout);
        let mut lines = reader.lines();

        // Skip ready message (first line)
        let _ready = lines.next();

        // Read actual response (second line)
        match lines.next() {
            Some(Ok(line)) => {
                let response: SolverResponse = serde_json::from_str(&line)
                    .map_err(|e| format!("Failed to parse response: {}", e))?;
                
                // Kill the child process
                let _ = child.kill();
                Ok(response)
            }
            Some(Err(e)) => {
                let _ = child.kill();
                Err(format!("Failed to read response: {}", e))
            }
            None => {
                let _ = child.kill();
                Err("No response from solver".to_string())
            }
        }
    }
}

impl Solver for SubprocessSolver {
    fn solve(
        &self,
        request: SolverRequest,
    ) -> Pin<Box<dyn Future<Output = Result<SolverResponse, String>> + Send + '_>> {
        Box::pin(async move { self.communicate(&request).await })
    }

    fn status(&self) -> Pin<Box<dyn Future<Output = SolverStatus> + Send + '_>> {
        Box::pin(async move { self.status.lock().await.clone() })
    }

    fn shutdown(&self) -> Pin<Box<dyn Future<Output = ()> + Send + '_>> {
        Box::pin(async move {
            // No persistent process to shut down in this implementation
            let mut status = self.status.lock().await;
            status.connected = false;
        })
    }
}
