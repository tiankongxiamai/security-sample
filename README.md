# Secure Pipeline Demo：一条带安检口的 CI/CD 流水线

这个项目用一个**故意写满漏洞**的小型 Flask 应用，演示如何在 CI/CD 流水线的每个阶段加入安全检查：SAST、SCA、容器扫描、SBOM、DAST、IaC 扫描。

目的只有一个：让你能诚实地说出 **"I've built a pipeline with these security gates myself and looked at what each tool finds."**

> 警告：`app/` 里的应用和 `terraform/` 里的配置都是**故意不安全**的，只能用于学习，绝不能部署。

---

## 1. 项目结构

```
secure-pipeline-demo/
├── app/
│   ├── app.py             # 故意有 5 个漏洞的 Flask 应用（每个都标了 VULN）
│   ├── requirements.txt   # 故意用了有已知 CVE 的旧版本依赖
│   └── Dockerfile         # 故意用了过期的基础镜像，并以 root 运行
├── terraform/
│   └── main.tf            # 故意不安全的 GCP 配置（公开存储桶、开放 SSH、公网数据库）
├── .semgrep/
│   └── rules.yml          # 自己写的 SAST 规则（演示规则长什么样）
├── .github/workflows/
│   └── security-pipeline.yml   # 核心：把所有安全检查串起来的流水线
└── reports/               # 我已经在本地跑出来的真实扫描结果
```

---

## 2. 一张表看懂：每个阶段的安检口

| 阶段 | 安全控制 | 用的工具 | 扫描对象 | 在本项目里的真实结果 |
| --- | --- | --- | --- | --- |
| Code | **SAST**（静态代码扫描） | Semgrep | `app/app.py` | 找到全部 6 处问题：2 个硬编码密钥、SQL 注入、XSS、命令注入、debug 模式 |
| Build | **SCA**（依赖漏洞扫描） | pip-audit | `requirements.txt` | 12 个包里有 7 个存在已知漏洞，去重后共 32 个，包括我们没直接写的间接依赖 `urllib3`、`idna` |
| Build | **SBOM**（软件物料清单） | Syft（CI）/ CycloneDX（本地） | 镜像 / 依赖 | 生成 CycloneDX 1.6 格式的配料表 |
| Build | **容器扫描** | Trivy | Docker 镜像 | 只在 GitHub Actions 里运行（见第 4 节） |
| Infra | **IaC 扫描** | Checkov | `terraform/main.tf` | 20 项失败：公开存储桶、SSH 对全网开放、数据库有公网 IP 且对所有人开放等 |
| Test | **DAST**（动态攻击测试） | OWASP ZAP | 运行中的应用 | 只在 GitHub Actions 里运行（见第 4 节） |

为什么有两项只在 GitHub 上跑：容器扫描和 DAST 需要 Docker，我做这个项目的环境里没有 Docker。GitHub Actions 的服务器上有 Docker，所以推上去之后会完整运行。

---

## 3. 先证明漏洞是真的

我把应用跑起来实际攻击了一遍，结果如下：

| 漏洞 | 攻击输入 | 结果 |
| --- | --- | --- |
| 正常查询 | `/user?name=alice` | 只返回 alice |
| **SQL 注入** | `/user?name=' OR '1'='1` | 返回**所有用户**，包括管理员 bob |
| **XSS** | `/hello?name=<script>alert(1)</script>` | 脚本原样出现在网页里，会在浏览器中执行 |
| **命令注入** | `/ping?host=127.0.0.1;whoami` | 服务器执行了 `whoami`，返回 `root` |

这就是为什么需要 SAST（在代码阶段发现这些写法）和 DAST（在运行时验证它们真能被利用）。

---

## 4. 10 分钟在 GitHub 上跑起来（最快、最出效果的方法）

不需要在自己电脑上装任何扫描工具，GitHub Actions 会免费帮你跑完全部检查。

### 方法 A：用 git 命令（推荐）

1. 在 GitHub 上新建一个 **Public** 仓库，例如 `secure-pipeline-demo`。不要勾选添加 README。
   （选 Public 是为了能免费使用 Security 标签页展示 SAST 结果。）
2. 解压这个项目，在项目文件夹里运行：

```bash
git init
git add .
git commit -m "Secure pipeline demo"
git branch -M main
git remote add origin https://github.com/<你的用户名>/secure-pipeline-demo.git
git push -u origin main
```

### 方法 B：只用网页上传

在 macOS 访达里，`.github` 和 `.semgrep` 是隐藏文件夹，拖拽上传时容易漏掉。按 `Cmd + Shift + .` 可以显示隐藏文件。上传后，确认仓库里能看到 `.github/workflows/security-pipeline.yml`，否则流水线不会启动。

### 推上去以后看哪里

1. **Actions 标签页**：会看到 "Secure pipeline demo" 自动运行，4 个任务并行执行，大约 5 到 10 分钟完成。
2. 点进这次运行，页面底部的 **Summary** 有 SCA 和容器扫描的汇总表。
3. **Artifacts**（同一页面底部）：下载各阶段的完整报告。最值得看的是 `build-and-test-reports` 里的 `zap-report.html`，用浏览器打开就是 DAST 报告。
4. **Security 标签页 → Code scanning**：Semgrep 的结果会像代码审查意见一样，标注在具体的代码行上。

---

## 5. 两个关键练习（面试时最有说服力的部分）

### 练习一：审计模式 vs 强制模式

打开 `.github/workflows/security-pipeline.yml`，第 13 行：

```yaml
ENFORCE_GATES: "false"
```

- `"false"` 是**审计模式**：所有扫描都运行、都出报告，但流水线不会失败。适合刚开始推行时先收集数据、不影响交付。
- 改成 `"true"` 是**强制模式**：任何一项扫描发现问题，流水线就会变红，代码不能继续往下走。

改完再推一次，对比两次运行的结果。这正是之前讲 Binary Authorization 时说的推行策略：**先审计、看数据，再强制**。

### 练习二：修复漏洞，看安检口由红变绿

每修一个问题、推一次代码，就能看到对应的检查通过。这就是完整的"发现 → 修复 → 验证"闭环。

| 问题 | 修复方法 |
| --- | --- |
| 硬编码密钥 | `app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]` |
| SQL 注入 | `conn.execute("SELECT ... WHERE name = ?", (name,))`（参数化查询） |
| XSS | `from markupsafe import escape`，然后 `"<p>Hello " + escape(name) + "</p>"` |
| 命令注入 | `subprocess.run(["ping", "-c", "1", host], capture_output=True, text=True)`（用列表，不用 shell），并校验 `host` 的格式 |
| debug 模式 | `app.run(host="127.0.0.1", port=5000, debug=False)` |
| 依赖漏洞 | 把 `requirements.txt` 里的版本升级到 pip-audit 报告中的修复版本 |
| 容器 | 换成 `python:3.12-slim`，并加上 `USER` 指令，不以 root 运行 |
| Terraform | 删除 `allUsers` 授权；SSH 只允许公司 IP 段；数据库关闭公网 IP 并强制 SSL |

---

## 6. 面试怎么讲

### 60 秒版本

> "To get hands-on, I built a small CI/CD pipeline in GitHub Actions around a deliberately vulnerable Flask app. It has a gate at each stage: Semgrep for SAST, pip-audit for SCA, Trivy for container scanning, Syft for the SBOM, OWASP ZAP for DAST, and Checkov for the Terraform. SAST caught every flaw I planted, including SQL injection and command injection. SCA found 32 known vulnerabilities across seven packages, including transitive dependencies I never declared. Checkov flagged a public bucket and SSH open to the internet. I also built an audit mode and an enforce mode, because in practice you roll out gates by collecting data first and blocking later."

### 这个项目让你作为 2nd line 能提出的质疑

做过一遍以后，你会自然地问出这些问题，而不是只问"你们有没有 SAST"：

1. **覆盖率**：多少比例的仓库真的启用了这些扫描？
2. **强制性**：扫描结果会阻止发布，还是只出一份没人看的报告？（对应练习一）
3. **间接依赖**：SCA 有没有覆盖间接依赖？本项目里 `urllib3` 就是没直接声明、却有漏洞的依赖。
4. **规则质量**：SAST 用的是什么规则集？有没有针对公司技术栈调整过？（对应 `.semgrep/rules.yml`）
5. **DAST 深度**：是只做被动的 baseline 扫描，还是做了主动攻击的 full scan？
6. **例外管理**：谁能批准"带着已知漏洞上线"？有没有记录和到期时间？
7. **修复时效**：critical 漏洞从发现到修复平均要多久？

---

## 7. 每个工具一句话

| 工具 | 类型 | 一句话 |
| --- | --- | --- |
| Semgrep | SAST | 按规则匹配危险的代码写法，规则可以自己写 |
| pip-audit | SCA | 把 Python 依赖和公开漏洞数据库比对 |
| Trivy | 容器扫描（也能做 SCA、IaC） | 扫描镜像里的操作系统包和语言依赖 |
| Syft | SBOM | 列出镜像里的所有组件，输出 CycloneDX 或 SPDX 格式 |
| OWASP ZAP | DAST | 像黑客一样攻击运行中的网站 |
| Checkov | IaC 扫描 | 检查 Terraform 等配置文件里的危险设置 |

在企业或 GCP 环境里，对应的服务有 Artifact Analysis（容器扫描、SBOM）、Cloud Build（流水线）、Binary Authorization（部署准入）、Web Security Scanner（DAST）。
