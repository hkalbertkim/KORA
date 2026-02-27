# KORA Studio Packaging & Distribution Specification v1.0

Status: Release Engineering Draft  
Language: English (Official Document)  
Purpose: Define packaging, distribution, update, and local data layout standards for shipping KORA Studio as a standalone desktop product.

---

# 1. Goals

KORA Studio distribution must:

• Provide a frictionless install experience  
• Support fully offline operation after install  
• Manage local models safely (download, verify, register)  
• Support Basic and Advanced modes  
• Support optional cloud plugin installation without coupling

---

# 2. Supported Platforms

Initial targets:

• macOS (Apple Silicon + Intel)  
• Windows 10/11  
• Linux (Ubuntu baseline)

Architecture targets:

• x86_64  
• arm64

---

# 3. Packaging Options

KORA Studio may ship using one of these packaging models.

## 3.1 Preferred: Desktop Wrapper + Local Web UI

• Local web UI served from embedded runtime  
• Desktop wrapper provides:
  - Tray/menu integration
  - Auto-start (optional)
  - Local file permissions

Implementation options:

• Tauri  
• Electron

This document is UI-framework neutral.

---

# 4. Installer Requirements

Installers must:

• Install Studio runtime binaries  
• Configure local ports  
• Create local data directory  
• Register OS-level app entry

Optional:

• Install a supported local model runtime dependency (Ollama) if user opts in.

---

# 5. Local Data Layout

Studio must use a single user-scoped data root.

Default paths:

macOS:
• ~/Library/Application Support/KORA-Studio/

Windows:
• %APPDATA%\\KORA-Studio\\

Linux:
• ~/.local/share/kora-studio/

Within data root:

• models/  
• configs/  
• telemetry/  
• caches/  
• exports/

---

# 6. Model Management

## 6.1 Model Catalog

Studio maintains a local model catalog:

models/catalog.json

Each entry includes:

• model_id  
• provider (ollama/lmstudio/llamacpp)  
• quantization  
• context_tokens  
• required_vram_mb (estimated)  
• file_paths  
• checksum  
• installed_at

---

## 6.2 Model Download

Model download flow:

1. User selects model from curated list.  
2. Studio downloads model files.  
3. Studio verifies checksum.  
4. Studio registers model in catalog.  
5. Model becomes selectable.

Rules:

• Downloads must be resumable.  
• Checksum verification required.  
• Partial downloads must not be treated as installed.

---

# 7. Runtime Backend Integration

Studio supports local inference backends.

## 7.1 Backend Connector Policy

Backends are integrated via the Reasoning Adapter.

Connector examples:

• Ollama connector  
• LM Studio connector  
• llama.cpp connector

Connectors must:

• expose model list  
• provide health status  
• provide token usage if possible  

---

# 8. Update Strategy

## 8.1 Auto-Update

Auto-update is optional and must be opt-in.

Modes:

• Manual update (default)  
• Auto-update (opt-in)

Update channel:

• stable  
• beta

Rules:

• Update must preserve local data directory.  
• Update must never delete models without explicit user action.

---

# 9. Offline Operation Guarantees

Studio must be usable without internet after installation.

Offline requirements:

• Local chat works  
• Local API works  
• Telemetry and exports work  

Only online-dependent features:

• model download  
• cloud backend usage

If offline:

• Cloud backend option disabled  
• Clear UX message shown

---

# 10. Export and Sharing

Studio supports exporting artifacts:

• TaskGraph JSON  
• Telemetry JSON  
• Markdown summary

Exports are written to:

exports/

No export is transmitted automatically.

---

# 11. Cloud Plugin Packaging

Krako cloud connectivity is packaged separately as:

• krako-backend-client plugin

Rules:

• Plugin installation requires explicit opt-in.  
• Studio runs without plugin.  
• Plugin may be removed without breaking Studio.

---

# 12. Logging & Diagnostics

Studio maintains:

• local logs (rotating)  
• crash reports (local)  
• diagnostics export bundle

Crash reports must be:

• opt-in to share externally

---

# 13. Release Artifact Checklist

Each release must include:

• signed installer (macOS notarized if required)  
• checksums for binaries  
• release notes  
• compatibility matrix (backend runtimes supported)

---

# Final Position

KORA Studio is a standalone local product.

Packaging must preserve:

• independence  
• offline capability  
• deterministic execution transparency

Cloud remains optional and plugin-based.

---

End of Document
