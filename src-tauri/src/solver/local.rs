#![allow(dead_code)]

use std::env;
use std::future::Future;
use std::path::{Path, PathBuf};
use std::pin::Pin;
use std::sync::Arc;

use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, ChildStdout, Command};
use tokio::sync::Mutex;
use tokio::time::{timeout, Duration};

use super::traits::Solver;
use super::types::*;

const IO_TIMEOUT: Duration = Duration::from_secs(30);

/// Determines how the solver spawns Python/SageMath.
#[derive(Debug, Clone)]
enum SolverMode {
    /// Use system-installed `sage --python` (lite / user-installed SageMath).
    SystemSage { sage_path: String },
    /// Use a bundled portable Python extracted from app resources (full build).
    BundledPython {
        python_bin: PathBuf,
        python_home: PathBuf,
    },
}

pub struct LocalSageSolver {
    process: Arc<Mutex<Option<SageProcess>>>,
    bridge_script: PathBuf,
    mode: SolverMode,
    backend_info: Arc<Mutex<Option<(String, Option<String>)>>>,
}

struct SageProcess {
    child: Child,
    stdin: ChildStdin,
    stdout_reader: BufReader<ChildStdout>,
}

impl LocalSageSolver {
    pub fn new(
        sage_path: Option<String>,
        resource_dir: Option<PathBuf>,
        app_data_dir: Option<PathBuf>,
    ) -> Self {
        let mode = Self::detect_mode(sage_path, resource_dir, app_data_dir);

        Self {
            process: Arc::new(Mutex::new(None)),
            bridge_script: Self::resolve_bridge_script_path(),
            mode,
            backend_info: Arc::new(Mutex::new(None)),
        }
    }

    /// Detect whether a bundled Python is available, falling back to system sage.
    fn detect_mode(
        sage_path: Option<String>,
        resource_dir: Option<PathBuf>,
        app_data_dir: Option<PathBuf>,
    ) -> SolverMode {
        // Try to set up bundled Python from app resources
        if let (Some(res_dir), Some(data_dir)) = (resource_dir, app_data_dir) {
            if let Some((python_bin, python_home)) =
                Self::try_setup_bundle(&res_dir, &data_dir)
            {
                eprintln!(
                    "[solver] Using bundled Python at {}",
                    python_bin.display()
                );
                return SolverMode::BundledPython {
                    python_bin,
                    python_home,
                };
            }
        }

        // Fall back to system sage
        let sage_path = Self::resolve_sage_path(sage_path);
        eprintln!("[solver] Using system SageMath at {}", sage_path);
        SolverMode::SystemSage { sage_path }
    }

    /// Check for a bundled SageMath tarball in resources and extract if needed.
    /// Returns (python_binary, python_home) if bundle is available.
    fn try_setup_bundle(
        resource_dir: &Path,
        app_data_dir: &Path,
    ) -> Option<(PathBuf, PathBuf)> {
        // Tauri v2 preserves directory structure from config, so the tarball
        // ends up at <resource_dir>/resources/sagemath-bundle.tar.gz
        let bundle_tar = resource_dir.join("resources/sagemath-bundle.tar.gz");
        if !bundle_tar.exists() {
            return None;
        }

        eprintln!(
            "[solver] Found SageMath bundle at {}",
            bundle_tar.display()
        );

        let extract_dir = app_data_dir.join("sagemath");
        let python_home = extract_dir.join("python");
        let version_file = extract_dir.join(".bundle-version");
        let current_version = env!("CARGO_PKG_VERSION");

        // Check if already extracted with the correct app version
        let needs_extract = if version_file.exists() {
            let existing = std::fs::read_to_string(&version_file).unwrap_or_default();
            existing.trim() != current_version
        } else {
            true
        };

        if needs_extract {
            eprintln!("[solver] Extracting SageMath bundle (first run or upgrade)...");

            // Ensure extract directory exists
            if let Err(e) = std::fs::create_dir_all(&extract_dir) {
                eprintln!("[solver] Failed to create extract dir: {}", e);
                return None;
            }

            // Extract using system tar (available on all desktop platforms)
            let result = std::process::Command::new("tar")
                .args([
                    "xzf",
                    &bundle_tar.to_string_lossy(),
                    "-C",
                    &extract_dir.to_string_lossy(),
                ])
                .output();

            match result {
                Ok(output) if output.status.success() => {
                    eprintln!("[solver] Bundle extraction complete");
                    // Write version marker
                    let _ = std::fs::write(&version_file, current_version);
                }
                Ok(output) => {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    eprintln!("[solver] Bundle extraction failed: {}", stderr);
                    return None;
                }
                Err(e) => {
                    eprintln!("[solver] Failed to run tar: {}", e);
                    return None;
                }
            }
        }

        // Find the python binary (platform-specific)
        let python_bin = if cfg!(windows) {
            python_home.join("python.exe")
        } else {
            python_home.join("bin/python3")
        };

        if python_bin.exists() {
            Some((python_bin, python_home))
        } else {
            eprintln!(
                "[solver] Bundled Python binary not found at {}",
                python_bin.display()
            );
            None
        }
    }

    fn resolve_sage_path(configured: Option<String>) -> String {
        if let Some(path) = configured {
            if !path.trim().is_empty() {
                return path;
            }
        }

        let candidates = [
            "sage",
            "/usr/bin/sage",
            "/usr/local/bin/sage",
            "/opt/homebrew/bin/sage",
        ];

        for candidate in candidates {
            if candidate == "sage" {
                if Self::find_on_path("sage").is_some() {
                    return "sage".to_string();
                }
            } else if Path::new(candidate).exists() {
                return candidate.to_string();
            }
        }

        "sage".to_string()
    }

    fn find_on_path(binary: &str) -> Option<PathBuf> {
        let path_var = env::var_os("PATH")?;
        for path in env::split_paths(&path_var) {
            let full = path.join(binary);
            if full.exists() {
                return Some(full);
            }
        }
        None
    }

    fn resolve_bridge_script_path() -> PathBuf {
        let mut candidates: Vec<PathBuf> = Vec::new();

        if let Ok(exe_path) = env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                candidates.push(exe_dir.join("sage_bridge.py"));
                candidates.push(exe_dir.join("../Resources/sage_bridge.py"));
                candidates.push(exe_dir.join("../../sage_bridge.py"));
                candidates.push(exe_dir.join("../../../sage_bridge.py"));
            }
        }

        if let Ok(manifest_dir) = env::var("CARGO_MANIFEST_DIR") {
            candidates.push(PathBuf::from(manifest_dir).join("sage_bridge.py"));
        }

        if let Ok(current_dir) = env::current_dir() {
            candidates.push(current_dir.join("src-tauri/sage_bridge.py"));
            candidates.push(current_dir.join("sage_bridge.py"));
        }

        for candidate in candidates {
            if candidate.exists() {
                return candidate;
            }
        }

        PathBuf::from("sage_bridge.py")
    }

    pub async fn start(&self) -> Result<(), String> {
        let mut guard = self.process.lock().await;

        if Self::is_process_running_locked(&mut guard) {
            return Ok(());
        }

        *guard = None;

        if !self.bridge_script.exists() {
            return Err(format!(
                "Sage bridge script not found at '{}'",
                self.bridge_script.display()
            ));
        }

        let mut child = match &self.mode {
            SolverMode::BundledPython {
                python_bin,
                python_home,
            } => {
                // Bundled mode: spawn portable Python directly
                let mut cmd = Command::new(python_bin);
                cmd.arg("-u").arg(&self.bridge_script);

                // Set up Python environment for the bundled installation
                cmd.env("PYTHONHOME", python_home);
                cmd.env("PYTHONDONTWRITEBYTECODE", "1");

                // Build PYTHONPATH for stdlib + site-packages
                let (stdlib, site_packages) = if cfg!(windows) {
                    let lib = python_home.join("Lib");
                    let sp = lib.join("site-packages");
                    (lib, sp)
                } else {
                    // Detect python version from the binary name or lib dir
                    let lib_dir = python_home.join("lib");
                    let python_lib = Self::find_python_lib_dir(&lib_dir)
                        .unwrap_or_else(|| lib_dir.join("python3.12"));
                    let sp = python_lib.join("site-packages");
                    (python_lib, sp)
                };

                let path_sep = if cfg!(windows) { ";" } else { ":" };
                cmd.env(
                    "PYTHONPATH",
                    format!(
                        "{}{}{}",
                        stdlib.display(),
                        path_sep,
                        site_packages.display()
                    ),
                );

                cmd.stdin(std::process::Stdio::piped())
                    .stdout(std::process::Stdio::piped())
                    .stderr(std::process::Stdio::inherit())
                    .spawn()
                    .map_err(|e| {
                        format!(
                            "Failed to start bundled Python at '{}': {}",
                            python_bin.display(),
                            e
                        )
                    })?
            }
            SolverMode::SystemSage { sage_path } => {
                // System mode: spawn sage --python
                Command::new(sage_path)
                    .arg("--python")
                    .arg(&self.bridge_script)
                    .stdin(std::process::Stdio::piped())
                    .stdout(std::process::Stdio::piped())
                    .stderr(std::process::Stdio::inherit())
                    .spawn()
                    .map_err(|e| {
                        format!(
                            "Failed to start SageMath at '{}': {}. Ensure SageMath is installed and available on PATH.",
                            sage_path, e
                        )
                    })?
            }
        };

        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "Failed to capture Sage process stdin".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "Failed to capture Sage process stdout".to_string())?;
        let mut stdout_reader = BufReader::new(stdout);

        let mut ready_line = String::new();
        let ready_len = timeout(IO_TIMEOUT, stdout_reader.read_line(&mut ready_line))
            .await
            .map_err(|_| "Timed out waiting for Sage bridge ready signal".to_string())?
            .map_err(|e| format!("Failed while reading Sage bridge ready signal: {e}"))?;

        if ready_len == 0 {
            let _ = child.kill().await;
            return Err("Sage bridge exited before sending ready signal".to_string());
        }

        let ready_json: serde_json::Value = serde_json::from_str(ready_line.trim()).map_err(|e| {
            format!(
                "Invalid Sage bridge ready payload '{}': {}",
                ready_line.trim(),
                e
            )
        })?;

        let ready_type = ready_json
            .get("type")
            .and_then(|v| v.as_str())
            .unwrap_or_default();
        if ready_type != "ready" {
            let _ = child.kill().await;
            return Err(format!(
                "Sage bridge did not return ready signal: {}",
                ready_json
            ));
        }

        let backend = ready_json
            .get("backend")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string();
        let version = ready_json
            .get("version")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        *self.backend_info.lock().await = Some((backend, version));

        *guard = Some(SageProcess {
            child,
            stdin,
            stdout_reader,
        });

        Ok(())
    }

    /// Find the python3.XX lib directory under lib/
    fn find_python_lib_dir(lib_dir: &Path) -> Option<PathBuf> {
        if !lib_dir.exists() {
            return None;
        }
        if let Ok(entries) = std::fs::read_dir(lib_dir) {
            for entry in entries.flatten() {
                let name = entry.file_name();
                let name_str = name.to_string_lossy();
                if name_str.starts_with("python3.") && entry.path().is_dir() {
                    return Some(entry.path());
                }
            }
        }
        None
    }

    pub async fn send_request(&self, request: &SolverRequest) -> Result<SolverResponse, String> {
        let payload = serde_json::to_string(request)
            .map_err(|e| format!("Failed to serialize solver request: {e}"))?;

        let mut guard = self.process.lock().await;
        let process = guard
            .as_mut()
            .ok_or_else(|| "Sage process is not running".to_string())?;

        process
            .stdin
            .write_all(payload.as_bytes())
            .await
            .map_err(|e| format!("Failed to write solver request: {e}"))?;
        process
            .stdin
            .write_all(b"\n")
            .await
            .map_err(|e| format!("Failed to terminate solver request line: {e}"))?;
        process
            .stdin
            .flush()
            .await
            .map_err(|e| format!("Failed to flush solver request: {e}"))?;

        let mut line = String::new();
        let read_result = timeout(IO_TIMEOUT, process.stdout_reader.read_line(&mut line)).await;
        let read_len = match read_result {
            Ok(Ok(n)) => n,
            Ok(Err(e)) => {
                Self::kill_process_locked(&mut guard).await;
                return Err(format!("Failed reading solver response: {e}"));
            }
            Err(_) => {
                Self::kill_process_locked(&mut guard).await;
                return Err("Timed out waiting for solver response".to_string());
            }
        };

        if read_len == 0 {
            Self::kill_process_locked(&mut guard).await;
            return Err("Sage process closed output stream unexpectedly".to_string());
        }

        serde_json::from_str::<SolverResponse>(line.trim())
            .map_err(|e| format!("Failed to parse solver response '{}': {}", line.trim(), e))
    }

    pub async fn restart(&self) -> Result<(), String> {
        {
            let mut guard = self.process.lock().await;
            Self::kill_process_locked(&mut guard).await;
        }
        self.start().await
    }

    pub async fn is_running(&self) -> bool {
        let mut guard = self.process.lock().await;
        Self::is_process_running_locked(&mut guard)
    }

    async fn kill_process_locked(process: &mut Option<SageProcess>) {
        if let Some(mut proc_handle) = process.take() {
            let _ = proc_handle.stdin.write_all(b"\n").await;
            let _ = proc_handle.stdin.flush().await;

            if let Ok(None) = proc_handle.child.try_wait() {
                let _ = proc_handle.child.kill().await;
            }

            let _ = proc_handle.child.wait().await;
        }
    }

    fn is_process_running_locked(process: &mut Option<SageProcess>) -> bool {
        if let Some(proc_handle) = process.as_mut() {
            match proc_handle.child.try_wait() {
                Ok(None) => true,
                Ok(Some(_)) | Err(_) => {
                    *process = None;
                    false
                }
            }
        } else {
            false
        }
    }

    fn failure_response(message: String) -> SolverResponse {
        SolverResponse {
            success: false,
            result_latex: None,
            steps: Vec::new(),
            error: Some(message),
        }
    }
}

impl Solver for LocalSageSolver {
    fn solve(
        &self,
        request: SolverRequest,
    ) -> Pin<Box<dyn Future<Output = Result<SolverResponse, String>> + Send + '_>> {
        Box::pin(async move {
            if !self.is_running().await {
                if let Err(e) = self.start().await {
                    return Ok(Self::failure_response(e));
                }
            }

            match self.send_request(&request).await {
                Ok(response) => Ok(response),
                Err(first_error) => {
                    if let Err(restart_error) = self.restart().await {
                        return Ok(Self::failure_response(format!(
                            "Solver request failed and restart failed: {first_error}. Restart error: {restart_error}"
                        )));
                    }

                    match self.send_request(&request).await {
                        Ok(response) => Ok(response),
                        Err(second_error) => Ok(Self::failure_response(format!(
                            "Solver request failed after retry: {second_error}"
                        ))),
                    }
                }
            }
        })
    }

    fn status(&self) -> Pin<Box<dyn Future<Output = SolverStatus> + Send + '_>> {
        Box::pin(async move {
            if !self.is_running().await {
                let _ = self.start().await;
            }
            let connected = self.is_running().await;
            let info = self.backend_info.lock().await;
            let (backend_name, version) = match info.as_ref() {
                Some((b, v)) => (b.clone(), v.clone()),
                None => ("unknown".to_string(), None),
            };
            SolverStatus {
                connected,
                backend_name,
                version,
            }
        })
    }

    fn shutdown(&self) -> Pin<Box<dyn Future<Output = ()> + Send + '_>> {
        Box::pin(async move {
            let mut guard = self.process.lock().await;
            Self::kill_process_locked(&mut guard).await;
        })
    }
}
