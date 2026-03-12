use crate::solver::traits::Solver;
use crate::solver::types::*;
use std::future::Future;
use std::path::PathBuf;
use std::pin::Pin;
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;
use tokio::time::{timeout, Duration};

const IO_TIMEOUT: Duration = Duration::from_secs(30);
const READY_TIMEOUT: Duration = Duration::from_secs(60);

macro_rules! solver_log {
    ($level:expr, $($arg:tt)*) => {
        eprintln!("[solver:{}] {}", $level, format!($($arg)*));
    };
}

struct EmbeddedPythonProcess {
    child: Child,
    stdin: tokio::process::ChildStdin,
    reader: BufReader<tokio::process::ChildStdout>,
}

pub struct AndroidSageSolver {
    process: Arc<Mutex<Option<EmbeddedPythonProcess>>>,
    python_binary: PathBuf,
    python_home: PathBuf,
    bridge_script: PathBuf,
    native_lib_dir: PathBuf,
    backend_info: Arc<Mutex<Option<(String, Option<String>)>>>,
}

impl AndroidSageSolver {
    pub fn new(
        python_binary: PathBuf,
        python_home: PathBuf,
        bridge_script: PathBuf,
        native_lib_dir: PathBuf,
    ) -> Self {
        Self {
            process: Arc::new(Mutex::new(None)),
            python_binary,
            python_home,
            bridge_script,
            native_lib_dir,
            backend_info: Arc::new(Mutex::new(None)),
        }
    }

    async fn ensure_started(&self) -> Result<(), String> {
        let mut proc_guard = self.process.lock().await;
        if proc_guard.is_some() {
            return Ok(());
        }

        if !self.python_binary.exists() {
            let msg = format!("Python binary not found at {}", self.python_binary.display());
            solver_log!("ERROR", "{}", msg);
            return Err(msg);
        }

        if !self.bridge_script.exists() {
            let msg = format!("Bridge script not found at {}", self.bridge_script.display());
            solver_log!("ERROR", "{}", msg);
            return Err(msg);
        }

        let stdlib = self.python_home.join("lib/python3.13");
        let site_packages = stdlib.join("site-packages");
        let python_path = format!("{}:{}", stdlib.display(), site_packages.display());

        solver_log!("INFO",
            "Starting Python: binary={}, script={}, home={}, path={}",
            self.python_binary.display(),
            self.bridge_script.display(),
            self.python_home.display(),
            python_path
        );

        let mut child = Command::new(&self.python_binary)
            .arg("-u")
            .arg(&self.bridge_script)
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .env("PYTHONHOME", self.python_home.to_str().unwrap_or(""))
            .env("PYTHONPATH", &python_path)
            .env("LD_LIBRARY_PATH", self.native_lib_dir.to_str().unwrap_or(""))
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .spawn()
            .map_err(|e| {
                let msg = format!("Failed to start Python: {}", e);
                solver_log!("ERROR", "{}", msg);
                msg
            })?;

        solver_log!("INFO", "Python process spawned (pid={:?})", child.id());

        let stderr = child.stderr.take();
        if let Some(stderr) = stderr {
            tokio::spawn(async move {
                let mut stderr_reader = BufReader::new(stderr);
                let mut line = String::new();
                while let Ok(n) = stderr_reader.read_line(&mut line).await {
                    if n == 0 { break; }
                    eprintln!("[python-stderr] {}", line.trim_end());
                    line.clear();
                }
            });
        }

        let stdin = child.stdin.take().ok_or("Failed to capture stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
        let reader = BufReader::new(stdout);

        let mut proc = EmbeddedPythonProcess {
            child,
            stdin,
            reader,
        };

        solver_log!("INFO", "Waiting for Python ready signal (timeout={}s)...", READY_TIMEOUT.as_secs());
        let mut ready_line = String::new();
        match timeout(READY_TIMEOUT, proc.reader.read_line(&mut ready_line)).await {
            Ok(Ok(n)) if n > 0 => {
                solver_log!("INFO", "Received from Python ({} bytes): {}", n, ready_line.trim());
                if let Ok(ready) = serde_json::from_str::<serde_json::Value>(&ready_line) {
                    if ready.get("type").and_then(|t| t.as_str()) == Some("ready") {
                        let backend = ready.get("backend").and_then(|v| v.as_str()).unwrap_or("unknown").to_string();
                        let version = ready.get("version").and_then(|v| v.as_str()).map(|s| s.to_string());
                        solver_log!("INFO", "Python ready: backend={}, version={:?}", backend, version);
                        *self.backend_info.lock().await = Some((backend, version));
                        *proc_guard = Some(proc);
                        return Ok(());
                    }
                }
                let msg = format!("Unexpected ready message: {}", ready_line.trim());
                solver_log!("ERROR", "{}", msg);
                let _ = proc.child.kill().await;
                Err(msg)
            }
            Ok(Ok(_)) => {
                let msg = "Python process closed stdout immediately".to_string();
                solver_log!("ERROR", "{}", msg);
                let _ = proc.child.kill().await;
                Err(msg)
            }
            Ok(Err(e)) => {
                let msg = format!("IO error reading ready signal: {}", e);
                solver_log!("ERROR", "{}", msg);
                let _ = proc.child.kill().await;
                Err(msg)
            }
            Err(_) => {
                let msg = format!(
                    "Timeout waiting for Python ready signal ({}s). Python may be slow to start on this device.",
                    READY_TIMEOUT.as_secs()
                );
                solver_log!("ERROR", "{}", msg);
                let _ = proc.child.kill().await;
                Err(msg)
            }
        }
    }

    async fn send_request(
        &self,
        request: &serde_json::Value,
    ) -> Result<serde_json::Value, String> {
        let mut proc_guard = self.process.lock().await;
        let proc = proc_guard
            .as_mut()
            .ok_or("Python process not started")?;

        let request_str =
            serde_json::to_string(request).map_err(|e| format!("Serialize error: {}", e))?;

        proc.stdin
            .write_all(format!("{}\n", request_str).as_bytes())
            .await
            .map_err(|e| format!("Write error: {}", e))?;

        proc.stdin
            .flush()
            .await
            .map_err(|e| format!("Flush error: {}", e))?;

        let mut response_line = String::new();
        match timeout(IO_TIMEOUT, proc.reader.read_line(&mut response_line)).await {
            Ok(Ok(n)) if n > 0 => serde_json::from_str(&response_line)
                .map_err(|e| format!("Parse error: {} — raw: {}", e, response_line.trim())),
            Ok(Ok(_)) => {
                drop(proc_guard);
                *self.process.lock().await = None;
                Err("Python process closed unexpectedly".to_string())
            }
            Ok(Err(e)) => Err(format!("IO error: {}", e)),
            Err(_) => {
                solver_log!("ERROR", "Computation timed out (30s), killing Python process");
                if let Some(mut p) = proc_guard.take() {
                    let _ = p.child.kill().await;
                }
                Err("Computation timed out (30s)".to_string())
            }
        }
    }
}

impl Solver for AndroidSageSolver {
    fn solve(
        &self,
        request: SolverRequest,
    ) -> Pin<Box<dyn Future<Output = Result<SolverResponse, String>> + Send + '_>> {
        Box::pin(async move {
            self.ensure_started().await?;

            let operation = match request.operation {
                OperationType::Solve => "solve",
                OperationType::Simplify => "simplify",
                OperationType::Differentiate => "differentiate",
                OperationType::Integrate => "integrate",
                OperationType::Factor => "factor",
                OperationType::Expand => "expand",
                OperationType::Limit => "limit",
                OperationType::Evaluate => "evaluate",
            };

            let json_request = serde_json::json!({
                "latex": request.latex,
                "operation": operation,
                "variable": request.variable.unwrap_or_else(|| "x".to_string()),
            });

            let response = self.send_request(&json_request).await?;

            Ok(SolverResponse {
                success: response
                    .get("success")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false),
                result_latex: response
                    .get("result_latex")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string()),
                steps: response
                    .get("steps")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|step| {
                                Some(SolutionStep {
                                    description: step
                                        .get("description")?
                                        .as_str()?
                                        .to_string(),
                                    latex: step.get("latex")?.as_str()?.to_string(),
                                })
                            })
                            .collect()
                    })
                    .unwrap_or_default(),
                error: response
                    .get("error")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string()),
            })
        })
    }

    fn status(&self) -> Pin<Box<dyn Future<Output = SolverStatus> + Send + '_>> {
        Box::pin(async move {
            {
                let proc = self.process.lock().await;
                if proc.is_none() {
                    drop(proc);
                    if let Err(e) = self.ensure_started().await {
                        solver_log!("ERROR", "Failed to start Python for status check: {}", e);
                    }
                }
            }
            let proc = self.process.lock().await;
            let info = self.backend_info.lock().await;
            let (backend_name, version) = match info.as_ref() {
                Some((b, v)) => (b.clone(), v.clone()),
                None => ("unknown".to_string(), None),
            };
            let connected = proc.is_some();
            solver_log!("INFO", "Status: connected={}, backend={}, version={:?}", connected, backend_name, version);
            SolverStatus {
                connected,
                backend_name,
                version,
            }
        })
    }

    fn shutdown(&self) -> Pin<Box<dyn Future<Output = ()> + Send + '_>> {
        Box::pin(async move {
            if let Some(mut proc) = self.process.lock().await.take() {
                let _ = proc.stdin.write_all(b"quit\n").await;
                let _ = tokio::time::sleep(Duration::from_millis(500)).await;
                let _ = proc.child.kill().await;
            }
        })
    }
}
