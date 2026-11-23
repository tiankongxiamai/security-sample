# Sample reports

These reports were produced by running the scanners locally on this project, so you can read real results before pushing anything to GitHub.

| File | Scanner | What to look for |
| --- | --- | --- |
| `semgrep.json` | Semgrep (SAST, local rules) | `results`: 6 findings, each with rule, line number and CWE |
| `pip-audit.json` | pip-audit (SCA) | `dependencies[].vulns`: CVE / PYSEC IDs and the `fix_versions` that resolve them |
| `checkov.json` | Checkov (IaC) | `results.failed_checks`: 20 failed checks on the Terraform file |
| `sbom.cyclonedx.json` | CycloneDX (SBOM) | `components`: every package with its version and `purl` identifier |

Container scanning (Trivy) and DAST (OWASP ZAP) need Docker, so their reports are produced only when the pipeline runs on GitHub Actions. Download them from the run's Artifacts.

Vulnerability databases update daily, so the numbers you see in CI may differ slightly from these.
