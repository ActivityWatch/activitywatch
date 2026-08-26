//! Research Edition `/api/0/export` sanitizer.
//!
//! Copied into `aw-server` only by `scripts/patch_research_edition_export.py`
//! when `AW_RESEARCH_EDITION=true`. Standard builds never see this module.
//!
//! Two jobs:
//! 1. Fail closed if currentwindow events still carry raw titles/URLs/app names
//!    (an existing ActivityWatch database is not a study-safe profile).
//! 2. Rewrite each exported bucket's map key, embedded `id`, and `hostname`
//!    so the real machine name never leaves the device. Colliding sanitized
//!    IDs fail the export rather than silently merging two machines.

use std::collections::HashMap;

use aw_models::{Bucket, BucketsExport, TryVec};
use serde_json::Value;

pub const SANITIZED_HOSTNAME: &str = "research-participant";

/// Study categories plus the two "Excluded" spellings the watcher writes.
/// Keep in sync with `scripts/patch_research_edition_config.py`.
const STUDY_CATEGORIES: &[&str] = &[
    "Sensitive / Excluded",
    "Music & Audio",
    "Video Streaming",
    "Games",
    "Travel & Mobility",
    "Search & Navigation",
    "News & Current Affairs",
    "Social Networking",
    "Messaging",
    "Email",
    "AI Chatbots & Assistants",
    "Work & Productivity",
    "Education & Learning",
    "Shopping - Goods",
    "Shopping - Groceries & Food",
    "Banking & Finance",
    "Public Services",
    "Excluded",
    "excluded",
];

/// Browser app names the Research filter leaves in `app` while classifying the
/// title. Copied from `aw-watcher-window/aw_watcher_window/research_filter.py`.
const BROWSER_APPS: &[&str] = &[
    "chrome",
    "google chrome",
    "google chrome canary",
    "google-chrome",
    "google-chrome-beta",
    "google-chrome-unstable",
    "chromium",
    "chromium-browser",
    "brave browser",
    "brave",
    "brave-browser",
    "firefox",
    "firefox developer edition",
    "firefox-esr",
    "safari",
    "edge",
    "microsoft edge",
    "microsoft-edge",
    "microsoft-edge-beta",
    "microsoft-edge-dev",
    "opera",
    "chrome.exe",
    "brave.exe",
    "firefox.exe",
    "msedge.exe",
    "opera.exe",
];

pub fn sanitize_buckets_export(export: BucketsExport) -> Result<BucketsExport, String> {
    let mut checked = HashMap::new();
    for (key, mut bucket) in export.buckets {
        reject_unfiltered(&mut bucket)?;
        checked.insert(key, bucket);
    }
    rewrite_identities(checked)
}

fn reject_unfiltered(bucket: &mut Bucket) -> Result<(), String> {
    let Some(events) = bucket.events.take() else {
        return Ok(());
    };
    let inner = events.take_inner();
    for event in &inner {
        if let Some(reason) = unfiltered_reason(&bucket._type, &event.data) {
            bucket.events = Some(TryVec::new(inner));
            return Err(format!(
                "Research Edition export refused: bucket type '{}' client '{}' contains unfiltered event data ({reason}). \
                 Research filtering only applies to newly captured events. Uninstall ActivityWatch, \
                 delete the existing database, and install the Research Edition on a clean profile.",
                bucket._type, bucket.client
            ));
        }
    }
    bucket.events = Some(TryVec::new(inner));
    Ok(())
}

fn unfiltered_reason(bucket_type: &str, data: &serde_json::Map<String, Value>) -> Option<&'static str> {
    if data.contains_key("url") {
        return Some("url field");
    }
    if bucket_type != "currentwindow" {
        return None;
    }
    if let Some(title) = data.get("title").and_then(Value::as_str) {
        if !is_study_category(title) {
            return Some("non-category window title");
        }
    }
    if let Some(app) = data.get("app").and_then(Value::as_str) {
        if !is_allowed_window_app(app) {
            return Some("non-category window app");
        }
    }
    None
}

fn is_study_category(value: &str) -> bool {
    let trimmed = value.trim();
    STUDY_CATEGORIES
        .iter()
        .any(|category| category.eq_ignore_ascii_case(trimmed))
}

fn is_allowed_window_app(app: &str) -> bool {
    is_study_category(app) || BROWSER_APPS.iter().any(|name| name.eq_ignore_ascii_case(app.trim()))
}

fn rewrite_identities(buckets: HashMap<String, Bucket>) -> Result<BucketsExport, String> {
    let mut out: HashMap<String, Bucket> = HashMap::new();
    for (key, mut bucket) in buckets {
        let original_id = if bucket.id.is_empty() {
            key.clone()
        } else {
            bucket.id.clone()
        };
        let sanitized_id = sanitize_id(&original_id, &bucket.hostname);
        let sanitized_key = sanitize_id(&key, &bucket.hostname);
        if sanitized_id != sanitized_key {
            return Err(
                "Research Edition export refused: bucket key and embedded id sanitize to different identities. \
                 Start from a clean ActivityWatch profile."
                    .to_string(),
            );
        }
        if out.contains_key(&sanitized_key) {
            return Err(format!(
                "Research Edition export refused: two buckets map to the same sanitized identity '{sanitized_key}'. \
                 This usually means data from more than one machine is in the same database. Start from a clean ActivityWatch profile."
            ));
        }
        bucket.id = sanitized_key.clone();
        bucket.hostname = SANITIZED_HOSTNAME.to_string();
        out.insert(sanitized_key, bucket);
    }
    Ok(BucketsExport { buckets: out })
}

pub(crate) fn sanitize_id(id: &str, hostname: &str) -> String {
    if hostname.is_empty() {
        return id.to_string();
    }
    if id == hostname {
        return SANITIZED_HOSTNAME.to_string();
    }
    let suffix = format!("_{hostname}");
    if let Some(prefix) = id.strip_suffix(suffix.as_str()) {
        return format!("{prefix}_{SANITIZED_HOSTNAME}");
    }
    if id.contains(hostname) {
        return id.replace(hostname, SANITIZED_HOSTNAME);
    }
    id.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use aw_models::{BucketMetadata, Event, TryVec};
    use chrono::{Duration, TimeZone, Utc};
    use serde_json::{json, Map};

    fn ts() -> chrono::DateTime<Utc> {
        Utc.with_ymd_and_hms(2026, 8, 24, 12, 0, 0).unwrap()
    }

    fn event(data: serde_json::Value) -> Event {
        Event {
            id: None,
            timestamp: ts(),
            duration: Duration::seconds(1),
            data: data.as_object().cloned().unwrap_or_else(Map::new),
        }
    }

    fn bucket(id: &str, hostname: &str, bucket_type: &str, client: &str, events: Vec<Event>) -> Bucket {
        Bucket {
            bid: None,
            id: id.to_string(),
            _type: bucket_type.to_string(),
            client: client.to_string(),
            hostname: hostname.to_string(),
            created: None,
            data: Map::new(),
            metadata: BucketMetadata::default(),
            events: Some(TryVec::new(events)),
            last_updated: None,
        }
    }

    fn export_of(buckets: Vec<Bucket>) -> BucketsExport {
        BucketsExport {
            buckets: buckets
                .into_iter()
                .map(|b| (b.id.clone(), b))
                .collect(),
        }
    }

    #[test]
    fn rewrites_key_id_and_hostname_together() {
        let host = "Participant-Alice-MacBook";
        let original = export_of(vec![
            bucket(
                &format!("aw-watcher-window_{host}"),
                host,
                "currentwindow",
                "aw-watcher-window",
                vec![event(json!({"app": "Excluded"}))],
            ),
            bucket(
                &format!("aw-watcher-afk_{host}"),
                host,
                "afkstatus",
                "aw-watcher-afk",
                vec![event(json!({"status": "afk"}))],
            ),
        ]);

        let sanitized = sanitize_buckets_export(original).unwrap();
        let window_id = format!("aw-watcher-window_{SANITIZED_HOSTNAME}");
        let afk_id = format!("aw-watcher-afk_{SANITIZED_HOSTNAME}");

        assert_eq!(sanitized.buckets.len(), 2);
        let window = sanitized.buckets.get(&window_id).unwrap();
        assert_eq!(window.id, window_id);
        assert_eq!(window.hostname, SANITIZED_HOSTNAME);
        assert_eq!(
            window.events.as_ref().unwrap().clone().take_inner()[0].data,
            json!({"app": "Excluded"}).as_object().unwrap().clone()
        );

        let afk = sanitized.buckets.get(&afk_id).unwrap();
        assert_eq!(afk.id, afk_id);
        assert_eq!(afk.hostname, SANITIZED_HOSTNAME);
        assert_eq!(
            afk.events.as_ref().unwrap().clone().take_inner()[0].data,
            json!({"status": "afk"}).as_object().unwrap().clone()
        );

        let dump = serde_json::to_string(&sanitized).unwrap();
        assert!(!dump.contains(host), "real hostname must not appear in export JSON");
        assert_eq!(dump.matches(SANITIZED_HOSTNAME).count(), 6); // key + id + hostname, twice
    }

    #[test]
    fn collision_of_two_hostnames_fails_closed() {
        let original = export_of(vec![
            bucket(
                "aw-watcher-window_host-a",
                "host-a",
                "currentwindow",
                "aw-watcher-window",
                vec![event(json!({"app": "Excluded"}))],
            ),
            bucket(
                "aw-watcher-window_host-b",
                "host-b",
                "currentwindow",
                "aw-watcher-window",
                vec![event(json!({"app": "Excluded"}))],
            ),
        ]);

        let err = match sanitize_buckets_export(original) {
            Err(err) => err,
            Ok(_) => panic!("expected hostname collision to fail closed"),
        };
        assert!(err.contains("same sanitized identity"));
        assert!(!err.contains("host-a"));
        assert!(!err.contains("host-b"));
    }

    #[test]
    fn unfiltered_title_fails_closed() {
        let original = export_of(vec![bucket(
            "aw-watcher-window_host",
            "host",
            "currentwindow",
            "aw-watcher-window",
            vec![event(json!({"app": "Code", "title": "secret.rs"}))],
        )]);

        let err = match sanitize_buckets_export(original) {
            Err(err) => err,
            Ok(_) => panic!("expected unfiltered title to fail closed"),
        };
        assert!(err.contains("unfiltered"));
        assert!(err.contains("clean profile"));
        assert!(!err.contains("secret.rs"));
        assert!(!err.contains("Code"));
    }

    #[test]
    fn unfiltered_url_fails_closed_even_outside_window_buckets() {
        let original = export_of(vec![bucket(
            "aw-watcher-web_host",
            "host",
            "web.tab.current",
            "aw-watcher-web",
            vec![event(json!({"url": "https://mail.example/inbox", "title": "Inbox"}))],
        )]);

        let err = match sanitize_buckets_export(original) {
            Err(err) => err,
            Ok(_) => panic!("expected url field to fail closed"),
        };
        assert!(err.contains("url field"));
        assert!(!err.contains("mail.example"));
    }

    #[test]
    fn browser_event_with_classified_title_is_allowed() {
        let original = export_of(vec![bucket(
            "aw-watcher-window_host",
            "host",
            "currentwindow",
            "aw-watcher-window",
            vec![event(json!({"app": "Firefox", "title": "Work & Productivity"}))],
        )]);

        let sanitized = sanitize_buckets_export(original).unwrap();
        let bucket = sanitized
            .buckets
            .get(&format!("aw-watcher-window_{SANITIZED_HOSTNAME}"))
            .unwrap();
        assert_eq!(
            bucket.events.as_ref().unwrap().clone().take_inner()[0].data,
            json!({"app": "Firefox", "title": "Work & Productivity"})
                .as_object()
                .unwrap()
                .clone()
        );
    }

    #[test]
    fn sanitize_id_replaces_suffix_and_embedded_hostname() {
        assert_eq!(
            sanitize_id("aw-watcher-window_Participant-Alice-MacBook", "Participant-Alice-MacBook"),
            format!("aw-watcher-window_{SANITIZED_HOSTNAME}")
        );
        assert_eq!(
            sanitize_id("Participant-Alice-MacBook", "Participant-Alice-MacBook"),
            SANITIZED_HOSTNAME
        );
        assert_eq!(sanitize_id("id1", "hostname"), "id1");
        assert_eq!(sanitize_id("keep_me", ""), "keep_me");
    }
}
