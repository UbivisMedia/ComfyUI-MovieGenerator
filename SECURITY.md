# Security Policy

## Supported Versions

We actively maintain and support security updates for the following versions:

| Version / Branch | Supported          |
| ---------------- | ------------------ |
| `main`           | :white_check_mark: |
| Releases (< 1.0) | :x:                |

---

## Reporting a Vulnerability

If you discover a security vulnerability or potential exploit in **MovieGenerator**, please report it responsibly:

1. **Do NOT open a public GitHub Issue.** Public issues expose users before a fix can be deployed.
2. **Preferred Method**: Use GitHub's [Private Vulnerability Reporting](https://github.com/UbivisMedia/ComfyUI-MovieGenerator/security/advisories/new).
3. **Alternative**: Contact the repository maintainers directly via private message or email.

### What to Include in Your Report
To help us triage and resolve the issue quickly, please include:
- A clear description of the vulnerability and its potential impact.
- Steps to reproduce the issue or a minimal proof-of-concept (PoC).
- Affected components (e.g. `script_agency.py`, CLI parser, workflow injection).
- Your operating system and Python environment details.

### Response Timeframe
- We aim to acknowledge your report within **48 hours**.
- We will provide regular status updates until a patch is released.
- You will be credited in the release notes once the vulnerability is addressed (unless you wish to remain anonymous).

---

## Security Architecture & Best Practices

MovieGenerator is designed as a local desktop filmmaking pipeline. Please observe the following security practices:

### 1. Local Network Binding
- By default, `script_agency.py` binds strictly to `127.0.0.1` (localhost).
- We strongly advise **against** exposing port `7860` or your ComfyUI port (`8188`) directly to the public internet without proper reverse proxy authentication (e.g., NGINX with TLS and HTTP Basic Auth / VPN).

### 2. Secrets & Configuration Hygiene
- Machine-specific configuration (`settings.json`) is strictly excluded via `.gitignore`.
- Never commit API keys, personal server tokens, or private network addresses to git.

### 3. Safe AI Models
- Always prefer modern **`.safetensors`** format for diffusion models and LoRAs.
- Avoid legacy `.ckpt` or `.bin` / `.pt` files from untrusted sources, as unpickling arbitrary Python objects can lead to remote code execution.
