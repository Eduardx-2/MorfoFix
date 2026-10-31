pub mod doc;
pub mod engine;
pub mod error;
pub mod logging;
pub mod settings;
pub mod temp;

#[cfg(feature = "desktop")]
pub mod cmds;
#[cfg(feature = "desktop")]
pub mod menu;
#[cfg(feature = "desktop")]
pub mod state;

#[cfg(feature = "desktop")]
mod desktop;

#[cfg(feature = "desktop")]
pub use desktop::run;
