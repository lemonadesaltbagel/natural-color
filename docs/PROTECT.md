# 色彩核心算法加密（NCVault）

把 `naturalcolor/color/`、`naturalcolor/model/` 与 `naturalcolor/io/{demosaic,denoise}.py` 的源码、以及 `params/` + `data/`
里的标定数据（含 `build/iq.pkl`，若存在）替换成 **经过认证加密的密文**：分发出去的目录里再也找不到算法源码，
但程序行为与明文树逐字节一致。

```
构建期                                   运行期
──────                                   ──────
engine.py ──zlib──► ──ChaCha20-Poly1305──► engine.ncs
                                              │  import naturalcolor.color.engine
                                              ▼
                                        meta_path 钩子：读 .ncs → 验签 → 解密
                                              │
                                              ▼
                                        compile() → exec() 到模块命名空间
                                        （明文只在内存里存活一次函数调用）
```

## 一、快速开始

```bash
# 1. 生成加密分发包（默认只加密代码，加 --data 连标定参数一起）
python tool/ncseal.py build --out dist/natural-color --data

# 2. 五段验证：布局 / 不可读 / 完整性 / 防篡改 / 逐字节一致
python tool/verify_sealed.py --root dist/natural-color

# 3. 看一个已加密目录的清单
python tool/ncseal.py status --root dist/natural-color

# 4. 需要回退成明文时
python tool/ncseal.py unseal --root dist/natural-color
```

`build` 从不改动源码树；只有 `inplace` 会就地加密，并且会先在
`_backup/` 写一个带时间戳的 tar.gz。

```bash
python tool/ncseal.py inplace --data        # 就地加密（先自动备份）
python tool/ncseal.py selftest              # 跑 RFC 8439 / RFC 5869 测试向量
```

> 发布到公开仓库、以及 CI 只产出密文的流水线，见 `ci/PUBLISH.md`
> （`tool/public_export.py` 导出公开树，`tool/ci_gate.py` 做发布闸门）。

## 二、三种部署模式

| 模式 | 命令 | 适用场景 |
|---|---|---|
| **embedded**（默认） | `build --data` | 单机 / 桌面分发。密钥以拆分混淆形式编进 `vault/_k.py`，密文和 loader 一起走。 |
| **external** | `build --data --key-mode external --key-out ~/.keys/nc.key` | 交给客户或部署到服务器。树上没有密钥，**只拿到目录无法解密**。 |
| **host-bound** | `build --data --bind` | 只允许在这一台机器上跑；换机器（或换硬件）直接解不开。 |

`external` 模式的运行方式：

```bash
export NATURALCOLOR_VAULT_KEY_FILE=~/.keys/nc.key     # 或 NATURALCOLOR_VAULT_KEY=<64 位 hex>
python -m naturalcolor render --input photo.raw --output out.jpg \
       --pipeline camera --params params/0044.json
```

三种模式可以叠加：`--key-mode external --bind` = 外部持钥 + 机器绑定。

## 三、加密设计

| 项目 | 选择 |
|---|---|
| 认证加密 | ChaCha20-Poly1305（RFC 8439），纯 Python + numpy 实现，无第三方依赖；装了 `cryptography` 会自动用它的原生实现 |
| 密钥派生 | HKDF-SHA256（RFC 5869），每个文件独立子密钥 |
| 子密钥输入 | `master [+ 主机指纹]`，`salt` 每文件随机 16 字节，`info = "ncvault/1|mod|naturalcolor.color.engine"` |
| 关联数据（AAD） | 整个文件头 + 逻辑名 + 类型。把 `engine.ncs` 改名成 `curves.ncs`、或把 params 冒充模块，都会**验签失败** |
| 压缩 | 先 zlib（-9）再加密：`gradation.bin` 262 KB → 56 KB，`params/*.json` 24 KB → 7 KB |
| 随机数 | `os.urandom`，每次构建 salt/nonce 全部重新生成 |
| 完整性 | `manifest.json` 记录每个载荷的 SHA-256；`verify()` 可离线校验 |

两处细节值得注意：

* **名字绑定**。`AAD` 里有 `kind + name`，所以密文块之间不能互换、不能拼接、
  不能把别人的 `params/0044.json.ncs` 塞进来读取。
* **拒绝静默降级**。密钥缺失 → `MissingKey`；密文被改 → `IntegrityError`。
  两种情况都直接抛异常，不会退回到"读不到就当默认值"。

## 四、威胁模型

| 攻击者能力 | embedded | external |
|---|---|---|
| 拿到分发目录，直接看源码 | 挡住（只有密文） | 挡住 |
| `strings` / `grep` 找算法常数 | 挡住（随机密文，无可读串） | 挡住 |
| 改一个字节 / 换文件 / 降级到旧版本 | 验签失败 | 验签失败 |
| 拿到目录 + 逆向 loader 提取密钥 | **只能提高成本**，不是绝对安全 | 无密钥可提，安全 |
| 在本机 dump 进程内存 | 能看到明文与字节码 | 能看到明文与字节码 |
| 反编译 CPython 字节码 | 可反汇编 `__code__` | 同左 |

必须说清楚的一点：**embedded 模式是混淆级防护，不是密码学级防护。**
密钥必须随程序一起走，任何人只要拥有完整分发物，理论上都能把 loader 逆出来。
它的价值是"防止源码泄漏、防止随手 copy、防止 Git 仓库被人 clone 走算法"，
而不是"防止有动机的逆向工程师"。

真正需要对抗逆向时，按这个顺序叠加：

1. `--key-mode external` —— 让密文本身不含密钥；密钥走 KMS / 环境变量 / 授权服务。
2. `--bind` —— 密文只在这台机器上有效。
3. 用 **Nuitka** 或 **PyArmor** 把 `naturalcolor/vault/` 这段 loader 也编译/虚拟化，
   此时攻击者连"从哪读密钥"都要先逆二进制。
4. 如果要做到"算法本身不可提取"，唯一可靠的路是把色彩核心用 C/C++/Rust 重写成
   原生扩展（配合 `-O2` 和符号剥离），Python 侧只留调用接口。

## 五、日常操作

```bash
# 加密额外的模块（替换默认清单，可重复）
python tool/ncseal.py build --out dist/x --include naturalcolor.io.demosaic

# 想在包里保留明文源码做调试（密文仍优先）
python tool/ncseal.py build --out dist/x --keep-source

# 指定一把固定密钥，便于多台机器产出一致的分发包
python tool/ncseal.py build --out dist/x --key $(python -c "import secrets;print(secrets.token_hex(32))")
```

* **不要在分发包里带上 `tool/`**。`build` 默认已经把它剔掉（`--with-tool` 才会带）。
  带上去等于把 `unseal` 一起发出去。
* **换密钥 = 重新构建**。改 `--key` 或 `--key-mode` 后必须重跑 `build`，
  旧密文与新密钥不通用（`manifest.json` 里的 `key_id` 会直接报错）。
* **升级 Python 不需要重新加密**。密文里存的是源码文本，不是 `.pyc`；
  Python 3.9+ 都能解。（若要升到 3.14 之类，建议重跑一次 `verify_sealed.py`。）
### 在加密树里校准

`CameraParams.save()` / `PostParams.save()` 已接到 vault：在加密树里写
`params/x.json`，实际落地的是 `params/x.json.ncs`（重新加密 + 更新 `manifest.json`
的 SHA-256），读回来自然优先密文。所以不会出现"改了明文、实际跑的却是旧密文"这种
静默错位；`verify()` 在写入后仍然为绿。源码树里依旧是普通 JSON。

```bash
# 加密树里的写盘效果
python -c "from naturalcolor.model.post import PostParams; PostParams(trim=None).save('params/post_0099.json')"
ls params/post_0099.json*        # -> post_0099.json.ncs（没有明文）
```

`python -m naturalcolor verify` 现在也能在加密树里看见 `post_lut_*.json`
（之前 `Path(...).exists()` 恒为 False，会把 studio-lut 那一行静默跳过）。

* **`__pycache__` 不要进包**。`build` 已忽略；如果手工拷贝，记得删掉，
  否则可能留下某个未加密模块的旧字节码。

## 六、故障排查

| 现象 | 原因 / 处理 |
|---|---|
| `MissingKey: no vault key found` | external 模式没设 `NATURALCOLOR_VAULT_KEY(_FILE)`；或 `_k.py` 被删 |
| `IntegrityError: ... wrong key or modified blob` | 密钥不对、密文被改、或跨机器跑了 host-bound 构建 |
| `ImportError: ... listed in the sealed manifest but ... is missing` | `.ncs` 被删/被改名；重跑 `build` |
| `verify` 报 digest mismatch | 构建后有人动过文件；以 `manifest.json` 为准重新构建 |
| 改了源码但行为没变 | 你在跑一个已加密的目录，改的是别的树；或在 `dist/` 里改 `.py` 但 `.ncs` 优先 |

## 七、文件清单

```
naturalcolor/vault/
  _aead.py      ChaCha20-Poly1305（RFC 8439），numpy 向量化 + 纯 Python 参考实现
  _kdf.py       HKDF-SHA256、主机指纹、子密钥派生
  _format.py    密文容器（头/盐/nonce/AAD/验签）
  _keys.py      主密钥解析顺序：env → 密钥文件 → _k.py
  _manifest.py  manifest 读取与仓库/包根定位
  _finder.py    sys.meta_path 钩子 + 内存内 exec 的 loader
  data.py       标定数据的透明读写（有 .ncs 就用 .ncs，否则明文）
  manifest.json 构建产物：模块/数据清单 + SHA-256 + key_id
  _k.py         构建产物：embedded 模式的密钥材料（已 gitignore）
tool/
  ncseal.py     build / inplace / unseal / status / selftest
  verify_sealed.py  五段式验收（布局、不可读、完整性、防篡改、逐字节一致）
  test_vault.py     RFC 测试向量 + 容器行为
```

`naturalcolor/__init__.py` 里只有一行 `vault.install_if_sealed()`：没有
`manifest.json` 的普通源码树完全不受影响，加密目录则自动接管导入。
