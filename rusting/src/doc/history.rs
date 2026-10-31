use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};

use super::edit_state::EditState;

const COALESCE_MS: u64 = 400;
pub const DEFAULT_LIMIT: usize = 100;
pub const DEFAULT_MAX_BYTES: usize = 64 * 1024 * 1024;

#[derive(Clone, Debug)]
pub struct History {
    undo: Vec<Entry>,
    redo: Vec<Entry>,
    limit: usize,
    bytes: usize,
    max_bytes: usize,
}

#[derive(Clone, Debug)]
pub struct Entry {
    pub state: EditState,
    pub label: String,
    pub at: Instant,
    pub size: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HistoryInfo {
    pub state: EditState,
    pub can_undo: bool,
    pub can_redo: bool,
    pub undo_label: Option<String>,
    pub redo_label: Option<String>,
}

impl History {
    pub fn new(limit: usize, max_bytes: usize) -> Self {
        Self {
            undo: Vec::new(),
            redo: Vec::new(),
            limit: limit.max(1),
            bytes: 0,
            max_bytes,
        }
    }

    pub fn commit(&mut self, prev: EditState, label: &str) {
        if let Some(last) = self.undo.last() {
            if last.label == label && last.at.elapsed() < Duration::from_millis(COALESCE_MS) {
                self.redo.clear();
                return;
            }
        }
        let size = estimate_size(&prev);
        self.undo.push(Entry {
            state: prev,
            label: label.to_string(),
            at: Instant::now(),
            size,
        });
        self.bytes = self.bytes.saturating_add(size);
        self.redo.clear();
        self.trim();
    }

    pub fn undo(&mut self, current: EditState) -> Option<EditState> {
        let prev = self.undo.pop()?;
        self.bytes = self.bytes.saturating_sub(prev.size);
        let size = estimate_size(&current);
        self.redo.push(Entry {
            label: prev.label.clone(),
            state: current,
            at: Instant::now(),
            size,
        });
        Some(prev.state)
    }

    pub fn redo(&mut self, current: EditState) -> Option<EditState> {
        let next = self.redo.pop()?;
        let size = estimate_size(&current);
        self.undo.push(Entry {
            label: next.label.clone(),
            state: current,
            at: Instant::now(),
            size,
        });
        self.bytes = self.bytes.saturating_add(size);
        self.trim();
        Some(next.state)
    }

    pub fn can_undo(&self) -> bool {
        !self.undo.is_empty()
    }

    pub fn can_redo(&self) -> bool {
        !self.redo.is_empty()
    }

    pub fn undo_label(&self) -> Option<String> {
        self.undo.last().map(|e| e.label.clone())
    }

    pub fn redo_label(&self) -> Option<String> {
        self.redo.last().map(|e| e.label.clone())
    }

    pub fn clear(&mut self) {
        self.undo.clear();
        self.redo.clear();
        self.bytes = 0;
    }

    pub fn info(&self, state: EditState) -> HistoryInfo {
        HistoryInfo {
            state,
            can_undo: self.can_undo(),
            can_redo: self.can_redo(),
            undo_label: self.undo_label(),
            redo_label: self.redo_label(),
        }
    }

    pub fn snapshot_undo(&self, keep: usize) -> Vec<EditState> {
        self.undo.iter().rev().take(keep).rev().map(|e| e.state.clone()).collect()
    }

    pub fn restore_undo(&mut self, states: Vec<(EditState, String)>) {
        self.clear();
        for (state, label) in states {
            let size = estimate_size(&state);
            self.bytes = self.bytes.saturating_add(size);
            self.undo.push(Entry {
                state,
                label,
                at: Instant::now(),
                size,
            });
        }
        self.trim();
    }

    fn trim(&mut self) {
        while !self.undo.is_empty()
            && (self.undo.len() > self.limit || (self.max_bytes > 0 && self.bytes > self.max_bytes))
        {
            let old = self.undo.remove(0);
            self.bytes = self.bytes.saturating_sub(old.size);
        }
    }
}

fn estimate_size(state: &EditState) -> usize {
    serde_json::to_vec(state).map(|v| v.len()).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::doc::edit_state::ui_to_intensity;
    use std::collections::BTreeMap;

    fn state_with_jaw(v: f32) -> EditState {
        let mut s = EditState::new();
        s.face
            .insert("0".into(), BTreeMap::from([("intensity_jaw".into(), v)]));
        s
    }

    #[test]
    fn commit_undo_redo() {
        let mut h = History::new(100, DEFAULT_MAX_BYTES);
        let s0 = EditState::new();
        let s1 = state_with_jaw(0.1);
        let s2 = state_with_jaw(0.2);
        let s3 = state_with_jaw(0.3);
        h.commit(s0.clone(), "a");
        h.commit(s1.clone(), "b");
        h.commit(s2.clone(), "c");
        let u1 = h.undo(s3.clone()).unwrap();
        assert_eq!(u1, s2);
        let u2 = h.undo(u1.clone()).unwrap();
        assert_eq!(u2, s1);
        let r1 = h.redo(u2.clone()).unwrap();
        assert_eq!(r1, s2);
    }

    #[test]
    fn commit_after_undo_clears_redo() {
        let mut h = History::new(100, DEFAULT_MAX_BYTES);
        h.commit(EditState::new(), "a");
        h.commit(state_with_jaw(0.1), "b");
        let current = state_with_jaw(0.2);
        let _ = h.undo(current);
        assert!(h.can_redo());
        h.commit(state_with_jaw(0.1), "c");
        assert!(!h.can_redo());
    }

    #[test]
    fn limit_discards_oldest() {
        let mut h = History::new(100, DEFAULT_MAX_BYTES);
        for i in 0..101 {
            h.commit(state_with_jaw(ui_to_intensity(i as i32 % 90)), &format!("n{i}"));
        }
        assert_eq!(h.undo.len(), 100);
        assert_eq!(h.undo.first().unwrap().label, "n1");
    }

    #[test]
    fn identical_commit_is_noop_at_caller() {
        let a = state_with_jaw(0.2);
        let b = state_with_jaw(0.2);
        assert_eq!(a, b);
    }

    #[test]
    fn coalescing_same_label() {
        let mut h = History::new(100, DEFAULT_MAX_BYTES);
        h.commit(EditState::new(), "Mandíbula");
        h.commit(state_with_jaw(0.1), "Mandíbula");
        assert_eq!(h.undo.len(), 1);
        assert_eq!(h.undo[0].state, EditState::new());
    }
}
