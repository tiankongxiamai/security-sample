# Secure Pipeline Demo: a CI/CD pipeline with a security gate at every stage

This project uses a small, **deliberately vulnerable** Flask application to show how security checks fit into each stage of a CI/CD pipeline: SAST, SCA, container scanning, SBOM generation, DAST and infrastructure-as-code (IaC) scanning.

The goal is hands-on understanding: build the pipeline, run every tool, and look at what each one actually finds, and what it misses.

> **Warning:** the application in `app/` and the configuration in `terraform/` are insecure **on purpose**. They are for learning only and must never be deployed.

---

## Architecture: how the files work together

![How the files work together](docs/architecture.png)

- **The product** (red): `app/app.py` is the application itself. `requirements.txt` lists the libraries it uses, and the `Dockerfile` packages both, plus an operating system, into a container image that can run anywhere. `terraform/main.tf` describes the cloud infrastructure the app would run on.
- **The inspectors** (green): six security tools. Each one looks at a different part of the product, and each judges it against its own knowledge: Semgrep against the rules in `.semgrep/rules.yml`, pip-audit and Trivy against vulnerability databases, ZAP against its built-in attack rules, Checkov against its built-in cloud policies. Syft only takes inventory and produces the SBOM.
- **The orchestration** (purple): the GitHub Actions workflow runs every inspector automatically on each push, decides whether findings should fail the pipeline (audit or enforce mode), and keeps every report as evidence.

| File | Language | Role |
| --- | --- | --- |
| `app/app.py` | Python | The product's code |
| `app/requirements.txt` | Plain list of package names and versions | The product's ingredients |
| `app/Dockerfile` | Dockerfile instructions | How to package the product with its runtime environment |
| `terraform/main.tf` | HCL (Terraform language) | The cloud infrastructure, described as code |
| `.semgrep/rules.yml` | YAML | What the SAST tool should treat as a flaw |
| `.github/workflows/security-pipeline.yml` | YAML, with shell commands inside `run:` | When and how all checks run, and what happens with the results |

---

## 1. Project structure

```
secure-pipeline-demo/
├── app/
│   ├── app.py             # Flask app with 5 deliberate flaws (each marked "VULN")
│   ├── requirements.txt   # Old dependency versions with known CVEs
│   └── Dockerfile         # End-of-life base image, runs as root
├── terraform/
│   └── main.tf            # Insecure GCP setup: public bucket, open SSH, public database
├── .semgrep/
│   └── rules.yml          # Custom SAST rules, showing what a rule looks like
├── .github/workflows/
│   └── security-pipeline.yml   # The pipeline that ties all checks together
├── docs/
│   ├── architecture.png        # The diagram above
│   └── make_architecture.py    # Script that draws the diagram
└── reports/               # Sample scan results produced locally
```

---

## 2. The security gates at a glance

| Stage | Security control | Tool | What it scans | Result in this project |
| --- | --- | --- | --- | --- |
| Code | **SAST** (static code analysis) | Semgrep | `app/app.py` | All 6 planted issues found: 2 hard-coded secrets, SQL injection, XSS, command injection, debug mode |
| Build | **SCA** (dependency vulnerabilities) | pip-audit | `requirements.txt` | 7 of 12 packages vulnerable, 32 unique known vulnerabilities, including transitive dependencies (`urllib3`, `idna`) that were never declared directly |
| Build | **SBOM** (software bill of materials) | Syft | Container image | A CycloneDX inventory of every component in the image |
| Build | **Container scanning** | Trivy | Container image | High and critical OS-level vulnerabilities from the end-of-life base image |
| Infra | **IaC scanning** | Checkov | `terraform/main.tf` | 20 failed checks: public bucket, SSH open to the internet, database with a public IP, no SSL, no backups, missing logs |
| Test | **DAST** (dynamic attack testing) | OWASP ZAP | The running app | 5 high, 3 medium, 6 low alerts. Command injection confirmed by reading `/etc/passwd`; XSS and SQL injection also found |

The sample reports in `reports/` cover SAST, SCA, IaC and a dependency SBOM, generated locally. Container scanning and DAST need Docker, so their reports are produced by GitHub Actions and can be downloaded from each run's artifacts.

---

## 3. Proof that the flaws are real

The app was started and attacked directly:

| Flaw | Attack input | Result |
| --- | --- | --- |
| Normal query | `/user?name=alice` | Returns only alice |
| **SQL injection** | `/user?name=' OR '1'='1` | Returns **every user**, including the admin bob |
| **XSS** | `/hello?name=<script>alert(1)</script>` | The script appears unescaped in the page and would run in a browser |
| **Command injection** | `/ping?host=127.0.0.1;whoami` | The server runs `whoami` and returns `root` |

This is why both SAST (find the dangerous code patterns early) and DAST (prove they can be exploited at runtime) are needed.

---

## 4. Running it on GitHub (about 10 minutes)

No scanners need to be installed locally. GitHub Actions runs every check for free.

### Option A: with git (recommended)

1. Create a new **public** repository on GitHub, for example `secure-pipeline-demo`, without a README. A public repository can show SAST results in the Security tab for free.
2. In the project folder, run:

```bash
git init
git add .
git commit -m "Secure pipeline demo"
git branch -M main
git remote add origin https://github.com/<your-username>/secure-pipeline-demo.git
git push -u origin main
```

### Option B: upload through the web interface

On macOS, `.github` and `.semgrep` are hidden folders and are easy to miss when dragging files. Press `Cmd + Shift + .` in Finder to show them. After uploading, check that `.github/workflows/security-pipeline.yml` exists in the repository, otherwise the pipeline will not start.

### Where to look after pushing

1. **Actions tab:** the "Secure pipeline demo" workflow starts automatically. Four jobs run in parallel and finish in a few minutes.
2. **Run summary:** tables for SCA and container scanning at the bottom of the run page.
3. **Artifacts** (bottom of the same page): the full report from every stage. Open `zap-report.html` from `build-and-test-reports` in a browser to see the DAST report.
4. **Security tab → Code scanning:** Semgrep findings shown directly on the affected lines of code.

---

## 5. Two exercises

### Exercise 1: audit mode vs enforce mode

Line 13 of `.github/workflows/security-pipeline.yml`:

```yaml
ENFORCE_GATES: "false"
```

- `"false"` is **audit mode** (report only): every scan runs and produces a report, but the pipeline does not fail. This suits the early rollout of a new control, when the goal is to collect data without blocking delivery.
- `"true"` is **enforce mode**: any finding turns the pipeline red. Combined with branch protection rules, code with findings cannot be merged.

The switch is built from two standard GitHub Actions features: a workflow variable (`env`) and `continue-on-error` on each scan step. Rolling out a control this way, collecting data first and blocking later, mirrors how deployment policies such as Binary Authorization are typically introduced.

### Exercise 2: fix the flaws and watch the gates turn green

Each fix, once pushed, makes the matching check pass. This completes the find → fix → verify loop.

| Issue | Fix |
| --- | --- |
| Hard-coded secrets | `app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]` |
| SQL injection | `conn.execute("SELECT ... WHERE name = ?", (name,))` (parameterised query) |
| XSS | `from markupsafe import escape`, then `"<p>Hello " + escape(name) + "</p>"` |
| Command injection | `subprocess.run(["ping", "-c", "1", host], capture_output=True, text=True)` (a list, no shell), plus validating the format of `host` |
| Debug mode | `app.run(host="127.0.0.1", port=5000, debug=False)` |
| Vulnerable dependencies | Upgrade each package in `requirements.txt` to the fix version listed in the pip-audit report |
| Container | Switch to `python:3.12-slim` and add a `USER` instruction so the app does not run as root |
| Terraform | Remove the `allUsers` binding; restrict SSH to company IP ranges; disable the database's public IP and require SSL |

---

## 6. Key takeaways

- **SAST and DAST complement each other.** Only SAST found the hard-coded secrets and debug mode. Only DAST found the missing security headers and the leaked server version. Both found the injections, and DAST proved the command injection by reading a system file.
- **Most supply-chain risk is indirect.** Several vulnerable packages were pulled in by other libraries and never chosen explicitly.
- **Many cloud misconfigurations are omissions.** A large share of Checkov's failures came from settings that were never written, because insecure defaults apply.
- **Scanners need human triage.** ZAP reported a likely false positive (file inclusion in an app that reads no files). Too many false positives lead teams to ignore alerts.
- **A green pipeline is not a secure product.** In audit mode every job showed green while the scans had found dozens of issues. What matters is what happens when a tool finds something.

### Questions a second-line reviewer should ask about any pipeline

1. **Coverage:** what share of repositories actually run these scans?
2. **Enforcement:** do findings block a release, or only produce a report nobody reads?
3. **Transitive dependencies:** does SCA cover the full dependency tree?
4. **Rule quality:** which SAST rule sets are used, and are they tuned to the company's tech stack?
5. **DAST depth:** passive baseline scan only, or an active full scan? Are authenticated pages covered?
6. **Exceptions:** who can approve shipping with a known vulnerability, and do exceptions expire?
7. **Remediation time:** how long, on average, from finding a critical vulnerability to fixing it?

---

## 7. The tools in one line each

| Tool | Control | What it does |
| --- | --- | --- |
| Semgrep | SAST | Matches dangerous code patterns against rules; custom rules can be written |
| pip-audit | SCA | Compares Python dependencies against public vulnerability databases |
| Trivy | Container scanning (also SCA and IaC) | Scans the OS packages and language dependencies inside an image |
| Syft | SBOM | Lists every component in an image in CycloneDX or SPDX format |
| OWASP ZAP | DAST | Attacks the running website the way an attacker would |
| Checkov | IaC scanning | Checks Terraform and other configuration files for risky settings |

In an enterprise GCP environment, the equivalent managed services include Artifact Analysis (container scanning and SBOMs), Cloud Build (pipelines), Binary Authorization (deployment admission) and Web Security Scanner (DAST).
