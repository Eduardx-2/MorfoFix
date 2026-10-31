use std::sync::Arc;
use std::time::{Duration, Instant};

use tokio::sync::{Mutex, oneshot};

use super::client::{RenderOut, RenderReq};
use crate::error::AppError;

type RenderFn = Arc<dyn Fn(RenderReq) -> futures::future::BoxFuture<'static, Result<RenderOut, AppError>> + Send + Sync>;

struct Pending {
    req: RenderReq,
    tx: oneshot::Sender<Result<RenderOut, AppError>>,
}

struct Inner {
    inflight: Option<u64>,
    pending: Option<Pending>,
    last_delivered: u64,
    last_send: Option<Instant>,
}

pub struct PreviewScheduler {
    inner: Arc<Mutex<Inner>>,
}

impl Default for PreviewScheduler {
    fn default() -> Self {
        Self::new()
    }
}

impl PreviewScheduler {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(Mutex::new(Inner {
                inflight: None,
                pending: None,
                last_delivered: 0,
                last_send: None,
            })),
        }
    }

    pub async fn submit_with<F, Fut>(&self, req: RenderReq, exec: F) -> Result<RenderOut, AppError>
    where
        F: Fn(RenderReq) -> Fut + Send + Sync + Clone + 'static,
        Fut: std::future::Future<Output = Result<RenderOut, AppError>> + Send + 'static,
    {
        let runner: RenderFn = Arc::new(move |req| Box::pin(exec.clone()(req)));
        self.submit_runner(req, runner).await
    }

    async fn submit_runner(&self, req: RenderReq, exec: RenderFn) -> Result<RenderOut, AppError> {
        let (tx, rx) = oneshot::channel();
        let start = {
            let mut g = self.inner.lock().await;
            if g.inflight.is_some() {
                if let Some(prev) = g.pending.take() {
                    let _ = prev.tx.send(Err(AppError::Superseded));
                }
                g.pending = Some(Pending { req, tx });
                None
            } else {
                g.inflight = Some(req.rev);
                Some((req, tx))
            }
        };
        if let Some((req, tx)) = start {
            let inner = self.inner.clone();
            tokio::spawn(async move {
                drive(inner, req, tx, exec).await;
            });
        }
        rx.await.unwrap_or(Err(AppError::Superseded))
    }
}

async fn drive(
    inner: Arc<Mutex<Inner>>,
    mut req: RenderReq,
    mut tx: oneshot::Sender<Result<RenderOut, AppError>>,
    exec: RenderFn,
) {
    loop {
        {
            let g = inner.lock().await;
            if let Some(last) = g.last_send {
                let elapsed = last.elapsed();
                if elapsed < Duration::from_millis(16) {
                    drop(g);
                    tokio::time::sleep(Duration::from_millis(16).saturating_sub(elapsed)).await;
                }
            }
        }
        {
            let mut g = inner.lock().await;
            g.last_send = Some(Instant::now());
            g.inflight = Some(req.rev);
        }
        let result = (exec)(req.clone()).await;
        let outcome = {
            let mut g = inner.lock().await;
            match result {
                Ok(out) if out.rev < g.last_delivered => Err(AppError::Superseded),
                Ok(out) => {
                    g.last_delivered = g.last_delivered.max(out.rev);
                    Ok(out)
                }
                Err(err) => Err(err),
            }
        };
        let _ = tx.send(outcome);
        let next = {
            let mut g = inner.lock().await;
            if let Some(pending) = g.pending.take() {
                g.inflight = Some(pending.req.rev);
                Some(pending)
            } else {
                g.inflight = None;
                None
            }
        };
        match next {
            Some(pending) => {
                req = pending.req;
                tx = pending.tx;
            }
            None => break,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::doc::edit_state::EditState;
    use std::sync::atomic::{AtomicUsize, Ordering};

    fn req(rev: u64) -> RenderReq {
        RenderReq {
            rev,
            state: EditState::new(),
            target: "preview".into(),
            max_side: 1600,
            format: "jpeg".into(),
            quality: 85,
            overlay: None,
        }
    }

    #[tokio::test]
    async fn latest_wins_with_slow_engine() {
        let sched = Arc::new(PreviewScheduler::new());
        let sent = Arc::new(AtomicUsize::new(0));
        let exec = {
            let sent = sent.clone();
            move |req: RenderReq| {
                let sent = sent.clone();
                async move {
                    sent.fetch_add(1, Ordering::SeqCst);
                    tokio::time::sleep(Duration::from_millis(200)).await;
                    Ok(RenderOut {
                        bytes: vec![req.rev as u8],
                        rev: req.rev,
                        ms: 200.0,
                        warnings: vec![],
                    })
                }
            }
        };
        let mut handles = Vec::new();
        for i in 1..=50 {
            let sched = sched.clone();
            let exec = exec.clone();
            handles.push(tokio::spawn(async move { sched.submit_with(req(i), exec).await }));
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        let results: Vec<_> = futures::future::join_all(handles).await;
        let mut last_ok = None;
        let mut superseded = 0;
        let mut ok = 0;
        for r in results {
            match r.unwrap() {
                Ok(out) => {
                    ok += 1;
                    last_ok = Some(out.rev);
                }
                Err(AppError::Superseded) => superseded += 1,
                Err(other) => panic!("{other}"),
            }
        }
        assert!(sent.load(Ordering::SeqCst) <= 8, "sent={}", sent.load(Ordering::SeqCst));
        assert!(ok >= 1);
        assert!(superseded > 0);
        assert_eq!(last_ok, Some(50));
    }
}
