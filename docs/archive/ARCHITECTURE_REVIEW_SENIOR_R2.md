# USIF 架构复审报告（第二轮）

> 评审对象：`usif` v4.0（源码分发包 `usif-4.0.tar.gz`，含 `PKG-INFO`/`usif.egg-info`，为 sdist）
> 对照基线：上一轮《USIF 架构评审报告》
> 评审方式：静态阅读 + 编译检查（`usif/`、`tests/`、`examples/` 全部 `py_compile` 通过）+ 逐项核对修复实现
> 重要前提：本次是**源码分发包**，不含 `.github/`、`.flake8`、`.gitignore`（已被 sdist 排除），因此涉及 CI 工作流、flake8 配置的结论以 `docs/CHANGELOG.md` 的声明为准，无法在本包内直接复核。

---

## 0. 总体结论

这是一次**范围大、质量高、且“真改而非掩盖”的整改**。代码结构对照上一轮建议做了系统性重构（拆出 `format/binary`、`storage`、`symmetry`、`io` 子包，巨石模块降级为门面），并以 `test_p0_/test_p1_/test_p2_` 三组回归测试对应“正确性 / 可靠性 / 架构边界”三个优先级。我**逐项核对了实现而非仅看测试**：上一轮全部 Critical / High、以及大部分 Medium/Low 问题已被真实修复，并额外引入了若干超出原评审范围的加固（解压炸弹防护、zip-slip 防护、索引分代+CRC 恢复、bandit/pip-audit/mypy/black/coverage 工程化）。

仍存在的问题集中在**“转换层未真正拆分、只是平移并多包了一层门面”**，以及若干遗留的中/低级问题（部分属性映射的长度不一致、注册表双实现重复、依赖环靠函数内 import 维系）。整体可发布性较上一轮显著提升。

---

## 1. 上一轮问题整改核对表（逐条已验证）

| 编号 | 上轮问题 | 当前状态 | 证据（已读源码） |
|---|---|---|---|
| **C1** | 解码不校验 header 中的 hash | ✅ 已修复 | `encoder.decode` 调用 `validate_geometry_hash(...)`；新增 `IntegrityError`；`test_p0` 篡改 header/几何字节均抛 `IntegrityError`。 |
| **C2** | hash 不含属性，容器据此去重导致静默丢数据 | ✅ 已修复 | `hashing.py` 拆出 `calculate_geometry_hash` / `calculate_record_hash`（含 formula、结构/原子/custom 属性，确定性归一化）；容器主键改用 `get_record_hash`；`test_p0` 验证“同几何异属性=两条记录、完全相同=去重”。 |
| **H1** | `add()` 查重-写-入索引存在 TOCTOU 竞态 | ✅ 已修复 | `add()` 将查重、文件写、索引更新收敛到**单一 `_index_lock` 临界区**（file lock 内嵌）；`test_p1` 64 线程并发 add 同一结构仅留 1 条。 |
| **H2** | `SymmetryReducer` 直接标 `lossless=True` 不校验 | ✅ 已修复 | `symmetry/reduce.py` 先 `SymmetryOperations.crystal_sites_match` 验证，不可逆则返回原全原子结构；与 converter 路径语义一致。 |
| **H3** | `force_symmetric=True` 静默丢弃原子属性 | ✅ 已修复（改为显式策略） | `from_pymatgen` 新增 `drop_atomic_properties` / `fallback_full_atomic`；默认遇到“强制对称+原子属性”**抛 `ValidationError`**，`test_p0` 三分支均覆盖。 |
| **H4** | 索引仅 `close()` 落盘、崩溃即丢、无校验 | ✅ 已修复且加固 | 容器采用**追加式分代索引** + CRC32（`INDEX_HEADER_FORMAT`）；`_find_latest_valid_index_offset` 在最新代损坏时回退到上一有效代；新增 `rebuild_index()` 从数据段重建；`test_p1` 覆盖“损坏检测/旧代恢复/重建”。 |
| **M1** | `PropertyRegistry` 全局可变单例污染 | ✅ 接口已修复（实现仍重复，见下） | 新增 `default_registry()` / `isolated_registry()`；`test_p2` 验证隔离注册不污染全局。 |
| **M3** | 编解码手写 offset、四象限重复 | ✅ 已修复 | 新增 `format/binary/{reader,writer,header,structure_codec}.py`，统一字段读写器；`encoder` 降为薄门面（`test_p2` 以 `inspect.getsource` 断言）。 |
| **M4** | 顶层强依赖 pymatgen/monty | ⚠️ 部分改善 | 转换/对称下沉到 `interop`，`encoder` 仅依赖 `format.binary`；但 `usif/__init__.py` 仍上提 `StructureConverter` 等，`import usif` 仍会触发 pymatgen 链（见 §4）。 |
| **L1** | `USIFStructure` 重复定义 `__getattr__`（`from` 别名失效） | ✅ 已删除 | `structures/structure.py` 已无 `__getattr__`。 |
| **L2** | encoder docstring 宣称 LZMA/BZIP2 但未实现 | ✅ 已修正 | 新 encoder docstring 不再虚假宣称多算法。 |
| **L3** | `interop` Importer/Exporter 死代码、converter 死包装 | ⚠️ 部分残留 | 适配器现已被 facade 调用（不再死代码），但 `interop/*/property_mapping.py` 未被任何模块引用（新死代码），converter_core 的 `_coords_equal/_site_sets_equal/_contains_coord` 仍无调用方。 |
| 版本三处手工同步 | M6 | ✅ 已修复 | `pyproject` 改 `dynamic=["version"]` + `attr = "usif.version.__version__"` 单一来源。 |
| `MANIFEST.in` 引用不存在的 setup.py/paper | — | ✅ 已修复 | 新 `MANIFEST.in` 干净，纳入 `tests/data/*.zip`。 |
| docs 冗余/失衡 | — | ✅ 已修复 | 历史计划/评审稿移入 `docs/archive/`；新增聚焦文档 CHANGELOG/CONTAINER_FORMAT/PROPERTY_SYSTEM/CONTRIBUTING；README 由 21K 精简至 8K。 |
| 工程门槛偏低（无 mypy/black、复杂度=32） | — | ✅ 已改善 | `pyproject` 新增 `[tool.black][tool.mypy][tool.coverage(fail_under=70)][tool.bandit]`；CHANGELOG 称 CI 扩到 3.8–3.12 并加 pip-audit。 |
| 超出原评审的额外加固 | — | ✅ 新增 | 解压上限 `MAX_PAYLOAD/COMPRESSED_SIZE`（解压炸弹防护）；`safe_extract` 防 zip-slip（`../`/绝对路径，`test_p1` 覆盖）；属性段长度校验。 |

---

## 2. 整体项目画像（变化部分）

类型、技术栈、核心工作流与上一轮一致。本轮主要变化是**分层落地**：

- 二进制协议下沉到 `usif/format/binary/`（`header / reader / writer / structure_codec / property_codec / integrity / limits`）。
- 容器实现迁入 `usif/storage/container.py`（顶层 `usif/container.py` 变为 9 行再导出 shim）。
- 对称能力独立为 `usif/symmetry/`（`analysis/expand/equivalence/reduce/metadata`），`usif/interop/symmetry.py` 变为兼容别名（`test_p2` 断言两路径为同一对象）。
- I/O 门面集中到 `usif/io/facade.py`，`USIFStructure` 的 `from_source/save/...` 委托至此。
- 转换实现迁入 `usif/interop/converter_core.py`，并通过 `interop/pymatgen` 与 `interop/ase` 子包暴露。
- 新增可运行示例：`quickstart / container_query / conversion_with_pymatgen / properties_and_hashes`，并被 `test_examples_smoke.py` 纳入冒烟。

入口点不变；新增公共导出 `IntegrityError`、`ContainerIndexError`、`default_registry`、`isolated_registry` 等。

---

## 3. 目录结构评估

分层较上一轮**明显成熟**，已基本实现“协议 / 存储 / 对称 / 互操作 / I-O 门面”的边界划分，符合上轮 §9 的目标结构方向。

仍可改进：

- **`interop/converter_core.py`（902 行）是本轮最大的结构遗留**。它几乎是旧 `converter.py` 的整体平移（甚至略增），仍单类承载 `from_pymatgen/from_ase/to_pymatgen/to_ase` + `_from_crystal/_from_molecule/_to_crystal/_to_molecule` + 对称转发。也就是说，“拆分转换器”这条建议**只完成了搬家和加壳，未完成内部分解**。
- **门面层数偏多**：`usif.converter.StructureConverter.from_pymatgen` → `interop.pymatgen.importer.PymatgenImporter.from_pymatgen` → `interop.converter_core.StructureConverter.from_pymatgen`，三跳到真正实现。兼容性目标达成，但对新读者形成“套娃”。
- `usif/storage/container.py` 反而增至 1348 行（容器逻辑 + 分代索引序列化/反序列化/恢复 + 分组层级序列化 + 预取 + 并行读仍同处一文件），是下一步可继续下沉的对象（如 `storage/index_persistence.py`、`storage/prefetch.py`）。

---

## 4. 核心模块职责分析（聚焦遗留重叠）

整体职责分配清晰度提升。仍存在的重叠/耦合：

1. **对称提取仍“两份”**：`converter_core._from_crystal`（SYMMETRIC 分支用 `SpacegroupAnalyzer.get_symmetrized_structure().equivalent_sites` 抽 Wyckoff）与 `symmetry/reduce.py:reduce_crystal` 实现同一逻辑。虽然现在二者都做无损校验、语义已对齐（H2 修复的红利），但**代码仍重复**，未收敛为单一服务调用。
2. **属性注册表双实现仍在**：`PropertyRegistry`（类方法 + 全局）与 `PropertyRegistryInstance`（实例隔离）逐方法重复（`register/get/get_required/list_properties/...`）。新增的 `default_registry/isolated_registry` 只是入口糖，未消除两套近似实现的 DRY 问题。
3. **依赖环靠函数内 import 维系，且数量增多**：`structure → io.facade → structures.source → converter → interop.pymatgen.importer → interop.converter_core → (顶层) structure`，以及 `symmetry.reduce → converter`。全包约 20+ 处函数体内 `from usif... import`。分层概念上更清晰，但物理模块图仍是环状，隐式依赖治理未根治。

---

## 5. 数据流与控制流（变化）

主链路与上一轮一致，关键增强：

- **解码链路现具备完整性闭环**：`USIFHeader.parse`（magic/版本/大小上限）→ 压缩段大小一致性校验 → `decompress_data(max_output_size=...)`（防解压炸弹）→ 原始段大小一致性校验 → `structure_codec.decode_body` → `validate_geometry_hash`。
- **容器主键语义修正**：写入用 `record_hash`；另建 `_geometry_index` 支持 `get_by_geometry_hash`，几何检索能力得以保留；读旧容器时 `_build_secondary_indexes` 会把 geometry-hash 主键迁移为 record-hash。
- **紧耦合点收敛但未消失**：`StructureContainer` 仍硬绑定 `USIF` 编码器与 SHA-256 记录哈希；`import usif` 仍经 `__init__` 间接拉起 pymatgen 依赖链（纯二进制/属性用途仍不能轻量化）。

---

## 6. 设计问题（按严重程度分级，仅列“当前仍存在”）

### Critical
- 无。上一轮 C1/C2 均已闭环验证。

### High
- 无新的 High。上一轮 H1–H4 均已修复并有回归测试。

### Medium
- **M-a｜`to_pymatgen` 全原子分支的属性长度不一致**：`converter_core._to_crystal` / `_to_molecule` 在 FULL_ATOMIC 下仅对“非 None”的原子追加 `forces/charges/magmoms`。若同一结构中部分原子有力、部分没有，`site_properties["forces"]` 长度将小于位点数，pymatgen 会因 site_properties 长度不匹配而报错。（注意：`from_ase` 路径已改为缺失补零 `[0,0,0]`，但 `to_pymatgen` 的这两处未同步修复。）建议统一为“要么全量补默认值、要么不写该属性”。
- **M-b｜转换层未真正拆分（902 行单类 + 三层门面）**：见 §3。属可维护性风险点。
- **M-c｜注册表双实现 DRY**：见 §4.2。

### Low
- **L-a｜`SymmetryReducer.reduce_crystal/reduce_molecule` 对输入对象有副作用**：在返回新结构前，向 `structure.structure_properties.custom` 原地写入 `SYMMETRY_METADATA_KEY`，且新结构与输入共享同一 `structure_properties` 对象，调用后输入对象被悄然改写。建议在副本上操作。
- **L-b｜死代码**：`interop/pymatgen/property_mapping.py`、`interop/ase/property_mapping.py` 无任何引用；`converter_core` 的 `_coords_equal/_site_sets_equal/_contains_coord` 转发包装无调用方。
- **L-c｜查询数值容差语义**：容器 `query` 数值匹配默认仍用 `SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE`（坐标容差）作为通用数值容差（含能量），语义仍偏借用（上一轮 M2，未见专门处理）。

---

## 7. 可维护性问题（现状）

- **命名/风格**：统一良好；`add`/`add_structure` 别名等历史冗余仍在（向后兼容取舍，可接受）。
- **重复代码**：对称提取两份、注册表两套，是主要残留（见上）。
- **隐式依赖**：函数内 import 数量随门面层增加而上升，是“清晰分层”的代价；建议通过把 `converter_core` 对 `symmetry` 的依赖单向化、并让 `structure` 不反向依赖 `io.facade`（改由 `io` 主动适配）来消除环、删除大部分懒加载。
- **配置集中度**：显著改善——版本单源、`pyproject` 汇集 black/isort/mypy/coverage/bandit/pytest 配置。
- **复杂脚本**：`storage/container.py` 与 `converter_core.py` 仍为高复杂度长文件，建议继续下沉。
- **文档治理**：已达良好状态（archive 归档 + 聚焦文档 + CHANGELOG 记录 P0–P3）。

---

## 8. 安全与可靠性问题（现状）

**安全基线进一步增强**：

- 仍无 `eval/exec/os.system/shell=True/pickle`，无硬编码密钥。
- **新增 zip-slip 防护** `safe_extract`：拒绝 `../` 与绝对路径成员（`test_p1` 覆盖），堵住了上一轮未点名的归档解压风险。
- **新增解压/分配上限**（`limits.py`）与解压输出封顶，缓解解压炸弹与超大分配 DoS。
- **新增 bandit + pip-audit**（按 CHANGELOG），把安全检查纳入工程化流程。

**可靠性增强**：

- 解码端多重一致性校验 + 强制 hash 校验（`strict_integrity`，默认 True）。
- 容器索引**分代 + CRC + 回退恢复 + 重建**，崩溃/截断恢复能力大幅提升，并有针对性回归测试。
- 新异常层次 `IntegrityError`、`ContainerError`、`ContainerIndexError`，错误语义更清晰。

**仍需关注**：

- 写路径的 `_compress/_write` 仍依赖文件/mmap 的 `flush`，未见显式 `fsync`；分代索引保证了**逻辑可恢复性**，但断电级持久化保证仍偏弱（可接受，建议在文档中明确“非事务性”语义）。
- `mp_downloader`（510 行，含硬编码 10 组化学查询）**仍随安装包分发**，虽已用 `safe_extract` 加固，但作为“数据获取脚本”更适合移出 `utils/` 进 `examples/` 或独立工具包（上一轮 §7 建议未采纳）。
- 转换/优化路径仍较多 `except Exception` 宽兜底（converter_core、reduce.py），建议收窄异常类型。

---

## 9. 测试与部署问题（现状）

**改善明显**：

- 新增 `test_p0_integrity_hashing` / `test_p1_reliability` / `test_p2_architecture`，分别锁定正确性、可靠性与架构边界（含用 `inspect.getsource` 守护“门面薄化”不回退）。
- 工程化：black/isort/mypy/coverage(`fail_under=70`)/bandit/pip-audit 全配；版本单源；`MANIFEST.in` 清理；示例纳入冒烟与（按 CHANGELOG）安装产物冒烟。
- 全树 `py_compile` 通过。

**仍存在/无法在本包复核**：

- 本包为 sdist，**不含 `.github/`、`.flake8`**：CHANGELOG 声称“CI 扩至 3.8–3.12”，但无法在本包内验证矩阵与 lint 阈值是否真正落地，建议在仓库层确认。
- `mypy` 配置对 `usif.interop.*`、`usif.services / usif.benchmarks / usif.integrations.*` 设 `ignore_errors=true`，即**最大的 `converter_core` 与 `mp_downloader` 被排除在类型检查之外**，类型保障覆盖面有限（务实但需知悉）。
- 覆盖率门槛 70%、`check_untyped_defs=false`，属起步级门槛，可逐步收紧。
- 仍是 pytest 与（历史）`run_tests.py` 双入口的取舍（次要）。

---

## 10. 后续建议（已大幅收敛，按价值排序）

1. **真正拆分转换层**：把 `converter_core` 按 `pymatgen/importer.py`、`pymatgen/exporter.py`、`ase/*` 落到各自文件承载实质逻辑（而非空壳转发到单一 902 行类），并让对称提取统一调用 `usif.symmetry`，消除重复。同时删除 `property_mapping.py` 等死代码或赋予其实际职责。
2. **修复 M-a 属性映射长度不一致**：`_to_crystal/_to_molecule` 对部分缺失的 force/charge/magmom 采用与 `from_ase` 一致的补默认值或整体省略策略。
3. **消除依赖环**：调整依赖方向使 `structure` 不反向依赖 `io/converter`，从而删除大部分函数内 import；这是当前最大的“隐式依赖”债务。
4. **合并注册表实现**：以实例为唯一实现，`PropertyRegistry` 作为默认实例的薄封装，去除双份方法体。
5. **继续下沉容器**：把分代索引持久化/恢复、预取、并行读拆出 `storage/` 子模块。
6. **工程收尾**：把 `interop/utils` 逐步纳入 mypy；提高 coverage 门槛；将 `mp_downloader` 迁出安装包；在仓库内核对 CI 矩阵与 lint 阈值。
7. **修副作用**：`SymmetryReducer` 在副本上写元数据，避免改写入参（L-a）。

---

### 附：本轮已核验事实清单（节选）

- 全树 `py_compile` 通过。
- `decode()` 强制 `validate_geometry_hash`，篡改 header/几何字节抛 `IntegrityError`（C1）。
- `calculate_record_hash` 含 formula/结构属性/原子属性/custom，容器主键用 record hash（C2）。
- `add()` 单临界区原子化；64 线程并发 add 同结构仅 1 条（H1）。
- `reduce_crystal` 先 `crystal_sites_match` 校验再标 lossless（H2）。
- `force_symmetric`+原子属性默认抛 `ValidationError`，需显式 `fallback_full_atomic`/`drop_atomic_properties`（H3）。
- 容器分代索引 + CRC + 旧代恢复 + `rebuild_index()`（H4）。
- 解压上限 + zip-slip `safe_extract`（新增安全加固）。
- `converter_core.py` 902 行单类，经三层门面调用（遗留 M-b）。
- `_to_crystal/_to_molecule` 全原子分支属性按非 None 追加，存在长度不匹配风险（M-a）。
- `interop/*/property_mapping.py` 无引用（死代码 L-b）。
- 版本单源（`dynamic`+`attr`）、`MANIFEST.in` 已清理；`pyproject` 含 black/mypy/coverage/bandit；`mypy` 排除 `interop.*`/`utils.*`。
