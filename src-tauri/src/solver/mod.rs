#[cfg(not(target_os = "android"))]
pub mod local;
pub mod subprocess;
pub mod traits;
pub mod types;
#[cfg(target_os = "android")]
pub mod android;

#[cfg(not(target_os = "android"))]
pub use local::LocalSageSolver;
pub use subprocess::SubprocessSolver;
pub use traits::Solver;
pub use types::*;
#[cfg(target_os = "android")]
pub use android::AndroidSageSolver;
