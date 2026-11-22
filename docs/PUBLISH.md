# 发布流程（framework 公开 + 核心加密分发）

公开仓库只有框架；色彩核心留在私有仓库，发布时由 CI 用只读 deploy key 拉取、加密、过闸门，
最后只上传密文。核心的明文**从不**出现在公开仓库、也从不进入 release 产物。

```
私有仓库 natural-color-core         公开仓库 natural-color           用户
──────────────────────────         ──────────────────────          ────
naturalcolor/color/*.py   ──┐
naturalcolor/model/*.py     │  CI: 检出 → ncseal build → 闸门 → 上传
params/*.json               │        │
data/gain_curves.json     ──┘        ▼
                              natural-color-v2.0.tar.gz
                              （只有 .ncs 密文 + 框架）
                                     │
                                     └──► 解包到框架树上，提供密钥即可运行
```

## 一次性配置

公开仓库 Settings → Secrets and variables → Actions：

| 类型 | 名称 | 内容 |
|---|---|---|
| secret | `CORE_DEPLOY_KEY` | SSH 私钥；对应公钥作为 **只读 deploy key** 加在私有核心仓库上（只开这一个仓库，不过期，与账号凭据无关） |
| secret | `CORE_KEY` | 32 字节 hex（`python -c "import secrets;print(secrets.token_hex(32))"`） |
| variable | `CORE_REPO` | `owner/repo`，私有核心仓库 |
| variable | `CORE_KEY_MODE` | `external`（默认，用户需持钥）或 `embedded`（开箱即用） |

## 两种密钥模式，选一个

| | `external` | `embedded` |
|---|---|---|
| 用户拿到包后 | 必须配 `NATURALCOLOR_VAULT_KEY` 才能跑 | 解包即可跑 |
| 密钥在哪 | 只在 CI secret + 你的密钥库 | 编译进 `vault/_k.py` |
| 防护强度 | 密文本身不含密钥 | 只能防"读到源码"，防不住有动机的逆向 |
| 适用 | 授权分发、商业客户 | 公开可运行、但不想公开算法 |

同一个 tag 只能对应一种模式；换模式等于换密钥，必须重新构建。

## 发布

```bash
git tag v2.0
git push origin v2.0          # 触发 .github/workflows/release.yml
```

流水线做的六件事，任何一步失败都不发布：

1. `tool/test_vault.py` —— 17 个加密/容器测试
2. `ci_gate --profile public --strict` —— 公开树里没有任何核心痕迹
3. 用 `CORE_DEPLOY_KEY` 经 SSH 检出私有核心（GitHub 主机指纹从 api.github.com/meta 固定），合并进工作树后立即删除 `.core-src/`
4. `ci_gate --profile core` —— 核心确实齐了（防止空克隆发一个没有核心的包）
5. `ncseal build --data --key-mode …` → `ci_gate --profile release --strict` →
   `verify_sealed`（与明文树逐字节比对）
6. 打包 → 再对**压缩包本身**跑一次 release 闸门 → 上传 release asset

第 6 步重复检查压缩包是有意的：防止打包这一步把明文又带回来。

## 闸门到底查什么

```bash
python tool/ci_gate.py --profile release --strict dist/release/natural-color
```

* 清单里 15 个模块（`ncseal.PROTECTED`）全部封了，且**没有**同名 `.py`
* `naturalcolor/color/`、`naturalcolor/model/` 下**没有任何** `.py`（不在清单里的新文件也会被拦下）
* 9 个数据文件全部封了，且**没有**明文原件
* 没有 `tool/`（它带 `unseal`）
* `external` 模式下没有 `_k.py`
* 全树可读文本里没有核心常数与厂商符号（清单在 `tool/ci_gate.py`）
* `--strict` 连"来源说明"性质的措辞也一并拦截

## 用户侧

```bash
tar -xzf natural-color-v2.0.tar.gz -C natural-color/
export NATURALCOLOR_VAULT_KEY_FILE=~/.config/natural-color/vault.key
python -m naturalcolor.core_api      # 看核心/密钥状态
```

## 本地演练（不依赖 GitHub）

```bash
# 1. 导出公开树，并过一遍 public 闸门
python tool/public_export.py --out /tmp/nc-public

# 2. 模拟 CI：把私有核心注回去，封一层，再对产物过闸门
rsync -a naturalcolor/ /tmp/nc-public/naturalcolor/
rsync -a params/ data/ /tmp/nc-public/
cd /tmp/nc-public
python tool/ncseal.py build --out dist/release/natural-color --data --key-mode external --key-out /tmp/nc.key
python tool/ci_gate.py --profile release --strict dist/release/natural-color
tar -czf /tmp/nc.tar.gz -C dist/release natural-color
python tool/ci_gate.py --profile release --strict /tmp/nc.tar.gz
```

## 密钥轮换 / 作废

* 换 `CORE_KEY` → 重新打 tag 构建；旧包配新钥解不开（`key_id` 会直接报错）
* 只想让旧包失效 → 不用重新构建，停止发放密钥即可
* 泄露怀疑 → 换钥 + 重新发版；`--bind` 可把新包绑死在指定机器上

### 配置 deploy key

```bash
ssh-keygen -t ed25519 -N "" -C "natural-color release CI (read-only)" -f /tmp/core_deploy
gh repo deploy-key add /tmp/core_deploy.pub -R <owner>/natural-color-core --title "release CI (read-only)"
gh secret set CORE_DEPLOY_KEY -R <owner>/natural-color < /tmp/core_deploy
rm -f /tmp/core_deploy /tmp/core_deploy.pub      # 私钥只留在 secret 里
```

## 桌面应用（.dmg / .exe）

同一个 tag 还会构建桌面应用：`apps` 任务在 macOS（Apple Silicon）和 Windows 上各自
注入核心，用 **embedded 模式、每次随机生成的密钥** 加密，然后 `tool/build_app.py`
用 PyInstaller 打包。加密树以普通文件随包分发，由 vault 的导入钩子在内存里解密；
PyInstaller 只读明文源码来找依赖，打包前再把 `naturalcolor` 的字节码全部剔除。

`build_app.py` 在以下任一情况下拒绝产出：

* 加密树不是 embedded 模式，或 `color/`、`model/` 下还有明文
* 冻结的 PYZ 里出现任何 `naturalcolor` 模块
* 打包好的应用跑 `--selftest` 失败（全部观感 × 编码，经过加密核心）

本地构建（macOS 示例）：

```bash
pip install pyinstaller pywebview
python tool/ncseal.py build --out dist/app/natural-color --data --key-mode embedded
python tool/build_app.py --sealed dist/app/natural-color --version 2.1.0
# -> dist/app/Natural-Color-2.1.0-macOS-arm64.dmg
```

应用未签名：macOS 首次打开需右键 › 打开（Gatekeeper），Windows 可能出现 SmartScreen
提示。有了 Apple Developer ID / Windows 代码签名证书后，在 `apps` 任务里加签名与公证即可。

embedded 模式的含义见 `docs/PROTECT.md` 的威胁模型：应用里带着密钥，挡得住"读源码"，
挡不住有动机的逆向。它与 external 发布包使用不同的密钥。
