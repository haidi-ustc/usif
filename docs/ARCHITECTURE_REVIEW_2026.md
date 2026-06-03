# USIF 架构评审报告

## 整体架构概览

USIF 是一个 Python 科学数据格式库，核心目标是提供统一的晶体和分子结构表示、二进制编码、压缩、转换、容器化存储和 Materials Project 数据辅助处理。

当前主要结构如下：

- `usif/structures/`：领域模型，核心是 `USIFStructure`、`WyckoffSite`、`PointGroupSite`、`AtomSite`
- `usif/encoder.py`：单结构 USIF 二进制编码和解码
- `usif/container.py`：多结构容器、索引、分组、缓存和 mmap
- `usif/converter.py`：pymatgen/ASE 与 USIF 转换
- `usif/properties/`：属性定义、注册表和序列化
- `usif/utils/`：优化、基准测试和 Materials Project 下载
- `tests/`：pytest/unittest 测试
- `examples/`：示例脚本
- `docs/`：模块文档和架构说明

整体是“领域模型 + 编码器 + 转换器 + 容器 + 工具层”的库式架构，但多个模块职责过宽，控制流和数据流耦合较重。

## 优点

- 领域模型清晰，通过 `StructureType` 和 `StorageMode` 区分晶体/分子、对称/全原子存储。
- 测试覆盖较多，包含结构、编码、容器、转换、属性和 MP 数据。
- API 入口集中，`usif/__init__.py` 便于用户从顶层导入。
- 属性系统具备扩展基础，包含 `PropertyDefinition`、`PropertyRegistry`、`PropertySerializer`。
- 格式层已有 magic bytes、版本、hash、压缩类型等长期演进要素。
- 容器层考虑了缓存、索引、分组、线程锁和 mmap。

## 严重问题

1. 核心模块过大，职责混杂。`container.py`、`structure.py`、`converter.py`、`encoder.py` 都偏大，后续维护风险高。
2. 格式协议与实现耦合过深。`encoder.py` 同时处理结构、属性、hash、压缩、custom JSON 和错误映射。
3. 对称存储语义有架构风险。代表位点加 multiplicity 不总能无损恢复输入坐标系。
4. 依赖声明不完整。`mp-api`、`ase`、OpenBabel 等实际使用依赖没有清晰的 optional dependency 分组。
5. 构建配置存在历史债务。静态版本与 `setuptools_scm` 依赖并存，发布路径需要清理。

## 中优先级问题

- `USIFStructure` 同时承担领域对象、MSON 序列化、文件 I/O 和转换门面职责。
- `PropertyRegistry` 是全局可变单例，测试和运行时 custom property 可能互相污染。
- `StructureConverter` 混合了导入、导出、对称分析、属性提取和异常回退。
- `USIFOptimizer` 与 `StructureConverter` 重复实现对称提取逻辑。
- `run_tests.py` 与 pytest 配置形成双轨测试入口。
- `run_lint.py` 依赖 `.flake8`，但复杂度阈值较高，质量门槛有限。
- 示例脚本没有统一纳入 CI 式 smoke test。
- 容器属性索引使用 round bucket，范围查询精度和边界语义不够明确。

## 低优先级问题

- 文档很多但存在历史计划、模块文档、评审文档并存的问题，可能过期。
- 顶层 `__init__.py` 导出过多，长期会增加导入副作用风险。
- 示例和测试中存在复杂函数和长行，可读性一般。
- recoverable fallback 的日志级别不够统一。
- README、docs、`AGENTS.md` 对开发命令有重叠，后续容易不一致。

## 具体重构建议

1. 拆分 `encoder.py`：
   - `format/header.py`
   - `format/structure_codec.py`
   - `format/property_codec.py`
   - `format/compression.py`
   - `format/hash.py`

2. 拆分 `container.py`：
   - `container/file_store.py`
   - `container/index.py`
   - `container/groups.py`
   - `container/query.py`
   - `container/container.py`

3. 拆分转换层：
   - `PymatgenImporter`
   - `PymatgenExporter`
   - `ASEImporter`
   - `ASEExporter`
   - `SymmetryReducer`
   - `SymmetryExpander`

4. 明确对称表示的不可逆性，增加 `lossless`、`reconstruction_mode`、`symmetry_origin`、`source_coordinate_frame` 等元数据。

5. 将 `PropertyRegistry` 改为可注入 registry，顶层只提供 default registry。

6. 整理 `pyproject.toml` optional dependencies：
   - `ase`
   - `mp`
   - `benchmark`
   - `dev`
   - `all`

7. 统一测试入口，以 `python -m pytest` 为主。

## 建议目标架构

```text
API Layer
  usif.__init__
  USIFStructure facade
  StructureContainer facade

Domain Layer
  structures/
  properties/
  units/
  exceptions/

Codec Layer
  format/header
  format/structure_codec
  format/property_codec
  format/compression
  format/hash

Interop Layer
  interop/pymatgen
  interop/ase
  interop/symmetry

Storage Layer
  container/file_store
  container/index
  container/groups
  container/query

Tools Layer
  utils/optimizer
  utils/benchmark
  utils/mp_downloader
```

关键原则：领域模型不直接承担文件 I/O；编解码不直接承担业务转换；容器存储不混入查询策略；外部依赖全部放在 interop/tools 层。

## 应优先修改的模块

1. `usif/container.py`
2. `usif/encoder.py`
3. `usif/converter.py`
4. `usif/properties/registry.py`
5. `pyproject.toml`
6. `run_tests.py`、`run_lint.py`、`.flake8`

## 三步迁移计划

### 第一步：稳定边界

- 冻结当前公共 API，补充黑盒回归测试。
- 覆盖老文件兼容、索引持久化、custom property、对称结构重建。
- 整理 `pyproject.toml` 可选依赖，确保 `pip install -e ".[all]"` 可运行测试和示例。

### 第二步：内部拆分但保持 API 不变

- 拆 `encoder.py` 到 codec 子模块。
- 拆 `container.py` 到 storage/index/group/query 子模块。
- `USIF`、`StructureContainer` 继续作为 facade。
- 将 pymatgen/ASE 相关逻辑移到 `interop/`。

### 第三步：强化语义和扩展能力

- 引入显式格式 schema/version migration。
- 将 `PropertyRegistry` 改为可注入 registry。
- 为对称存储增加 lossless/lossy 标记和坐标系元数据。
- 建立 CI 工作流：pytest、lint、examples smoke test、editable install、package build。
