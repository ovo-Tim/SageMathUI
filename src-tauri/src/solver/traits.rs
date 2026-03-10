use std::pin::Pin;
use std::future::Future;

use super::types::{SolverRequest, SolverResponse, SolverStatus};

/// Trait for math solver backends
pub trait Solver: Send + Sync {
    /// Solve a math expression
    fn solve(
        &self,
        request: SolverRequest,
    ) -> Pin<Box<dyn Future<Output = Result<SolverResponse, String>> + Send + '_>>;

    /// Get solver status
    fn status(&self) -> Pin<Box<dyn Future<Output = SolverStatus> + Send + '_>>;

    /// Shutdown the solver backend gracefully
    fn shutdown(&self) -> Pin<Box<dyn Future<Output = ()> + Send + '_>>;
}
