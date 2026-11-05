# 地图源制作方式

本文说明如何为《胡闹厨房 2》的 DIYLevel 自定义关卡集（玩家口中的「地图」）发布一份地图源，让管理器的**地图安装页**能列出并安装它们。

仓库源与地图源是**两条独立的索引链**，不要混用：

| | MOD 仓库源 | 地图源 |
|---|---|---|
| 索引文件 | `repositories.toml` | `maps.toml` |
| 收录对象 | BepInEx 插件 | DIYLevel 关卡集（ZIP） |
| 绑定本地 | `plugin_guid`（DLL 内嵌） | `author` + `level_set_name`（info 内嵌） |
| 安装单元 | MOD 包（可含多个 DLL） | 恰好一个关卡集 |
| 界面 | MOD 安装页 | 地图安装页 |

## 1. 三种发布形态（`document` / `repository` / `release-tags`）

地图只分发 ZIP，一个 ZIP 里**恰好一个**关卡集。仓库怎么组织有两种写法：

| 形态 | 一个仓库 | 地图条目写在哪 | 读源时要联网吗 |
|---|---|---|---|
| `mode = "repository"` | 一张地图 | `maps.toml` 里 `[map_sources.map]` 内联 | 不用，版本列表单独刷新 |
| `mode = "release-tags"` | 任意多张地图，**一个 Release = 一张地图** | 各 Release note 里的 `<!-- oc2-map -->` 块 | 要，加载源时读完整仓 Release |
| `mode = "document"`（缺省） | 任意多张地图，集中在一份子源文档里 | 子源文档的 `[[maps]]`（相对路径 / 内置资源名 / Release 资产地址） | 要，读那份子源文档 |

老形态 `mode = "document"`（`url` 指向一份 `[[maps]]` 子源文档）仍然支持，适合把几十张图集中维护在一份 TOML 里；它在加载源时读那份文档，条目仍然是「一个仓库一张图」。

为什么不做「一个 ZIP 装多张图」：ZIP 里包含多个关卡集时安装会被拒绝，因为无法判断该绑到哪一条地图声明上。多张图请拆成多个仓库（`repository`）或多个 Release（`release-tags`）。

`release-tags` 是给「一个作者十几张图」准备的：作者发一个新 tag 就是发布一张新地图，改一次 note 就是改这张图的说明与依赖，**不需要再维护、再同步一份集中式索引**。管理器读该仓库全部 Release（默认每页 50 条、最多 20 页），逐个解析 note 里的块，整份组合成一个地图源交给界面。

卡片说明只取块内的 `note_i18n`：按界面语言选，缺失退回单语言 `note`，两者都没有才显示「此地图暂无说明」。块外面的正文是**这个版本的更新日志**，进版本详情的「提交日志」，不会被当成简介；`repository` 与 `document` 形态的地图条目走同一套 `name_i18n` / `note_i18n` 回退。

## 2. 关卡集的目录结构

管理器认可的 ZIP 内布局（`<任意目录>/` 那一层可以是 ZIP 名称）：

```text
rw_v0.73.zip
└── RW_LevelSet/          ← 关卡集目录（目录名会被保留）
    ├── info              ← 元数据（Unity AssetBundle）
    ├── s_rw_1            ← 关卡场景
    ├── s_rw_2
    └── ...
```

安装后落盘位置：

```text
BepInEx/plugins/OC2DIYLevel/levels/RW_LevelSet/                  ← 启用
BepInEx/cache/modmanager_disabled_maps/RW_LevelSet/              ← 停用
```

停用根**不在 `BepInEx/plugins/` 树里**：BepInEx 5 递归扫描 `plugins/` 下每个 `.dll`，关卡集目录里又可能带着作者随包的修复插件（见下一节），停在 `plugins/` 里等于「地图停用了、插件下次启动照样加载」。旧版本停用根 `BepInEx/plugins/OC2DIYLevel/disabled` 由 `level_sets::migrate_legacy_disabled_root` 在扫描时一次性搬过去（整体 rename；目标已有同名目录就逐项搬并保留旧位置，不覆盖用户数据）。

### 关卡集包里带插件（作者修复包）

作者常把「地图 + 自己的修复插件」打进同一个 ZIP，实测结构是：

```text
jonny职业鼠鼠的图.zip
├── levels包/
│   └── jonnylevelset3.4.1/{info_jonny, s_jonny_1..7}
└── plugins包/
    └── Jonny_dll/{JonnyLevelLoaderPlugin.dll, JonnyLevelScripts.dll}
```

识别规则（`level_sets.rs` 的 `package_unit_root` / `plugin_unit_root` / `assign_plugins`）：

- **包单位**：从集目录往上找第一层 `levels*`（容忍 `levels包`、`Levels`），取它的父目录当「一个作者包」；ZIP 根下直接就是集目录时退回集目录的父目录。同一个包单位里的集与 DLL 是同一件事的两半。
- **插件归集**：向上找最近的 `plugins*` 目录取父目录；**不在 `plugins*` 子树里的 DLL 不认**（避免把集目录里某个同名的资源当插件）。单集直接归它；多集时按「DLL 名 / DLL 父目录名」与「集目录名 / `levelSetName` / `levelSetNameZH`」的最长公共前缀打分（归一化去掉非字母数字、CJK 保留），唯一最高且 ≥ 4 才命中，否则归排序第一张 —— **不复制成多份**，重复 DLL 会被 BepInEx 加载两遍。判不出归属时至少让地图能装，插件归到一张图上。
- **落盘位置**：DLL 直接写进集目录根（`levels/<集>/YourFix.dll`），不进 `BepInEx/plugins` 顶层 —— 这样「停用地图」搬走整个目录时插件一起走，不会留下一个还在加载的孤儿插件。
- 导入结果的 `ZipLevelSet.plugins` 带出这批 DLL，确认弹窗逐张地图显示「随包插件：…」，用户装之前就知道会多出哪些 DLL。

`info` 是一个 UnityFS AssetBundle，里面装着 `LevelSetInfoSO`。管理器只读取它，不修改。部署时可参考以下几点：

- 文件名优先找 `info`；找不到时找唯一的 `info_*`（例如 `info_v2`）。有多个 `info_*` 且无法判定时视为无效关卡集。
- 目录内的 `.DS_Store`、`Thumbs.db`、`__MACOSX`、`.git` 等噪音条目会被忽略，不影响导入。
- 关卡集与其它 MOD 互不干扰；DIYLevel 只枚举 `levels/` 下的一级目录。

### ZIP 与声明不一致会被拒绝

安装在线地图时，管理器会解析 ZIP 里的 `info`，把它的 `levelSetName` 和 `author` 与地图源里声明的身份**逐一比对**（忽略大小写与首尾空白）。

不一致就直接失败，什么都不写入磁盘。这是刻意的：一旦装错绑定，后续所有更新检测都会失效，而用户看到的只是一个看起来很正常的卡片。错误提示会同时给出「声明值」和「实际值」。

## 3. 编写 `maps.toml`

### 3.1 索引只放源声明

`maps.toml` 是**索引**，里面只有 `[[map_sources]]`。三种 `mode` 各有一个必填字段。随包的内置索引当前只声明一个 `release-tags` 仓库（`community-maps`），下面三种形态的完整示例用来写自定义源或远程索引：

```toml
# 单仓库地图：整仓 = 一张图，条目内联（离线可用）
[[map_sources]]
id = "maps-rw"
mode = "repository"
builtin = true
provider = "gitee"
username = "ch3ngyz"
repository = "DIYLevel-Maps-RW"
[map_sources.nickname_i18n]
zh-CN = "RW - DIYLevel 地图"
en = "RW - DIYLevel maps"
[map_sources.map]
# 这张图的全部元数据，字段见 §3.2
...

# 单仓多 Release：一个 tag 一张图，元数据在各 Release note 里
[[map_sources]]
id = "community-maps"
mode = "release-tags"
builtin = true
provider = "github"
username = "CH3NGYZ"
repository = "oc2"
page_size = 100
max_pages = 10
[map_sources.nickname_i18n]
zh-CN = "社区地图仓库"

# 老形态：url 指向一份 [[maps]] 子源文档
[[map_sources]]
id = "third-party-doc"
url = "maps-third-party.toml"
```

`[[map_sources]]` 字段：

| 字段 | 适用于 | 缺失时 |
|---|---|---|
| `id` | 全部 | 必填，卡片 ID 与「沿用上次条目」都靠它 |
| `mode` | 全部 | 默认 `document` |
| `url` | `document` | 整份源解析失败：`文档型地图源缺少 url：X` |
| `provider` / `username` / `repository` | `repository` / `release-tags` | `release-tags` 缺坐标整份源失败；`repository` 可以只写在 `[map_sources.map]` 里 |
| `[map_sources.map]` | `repository` | 整份源解析失败：`单仓库地图源缺少 [map_sources.map] 条目：X` |
| `page_size` | `release-tags` | 默认 50，范围 1–100（内置 `community-maps` 写的是 100） |
| `max_pages` | `release-tags` | 默认 20，范围 1–100（50 × 20 = 最多 1000 条 Release；内置 `community-maps` 写的是 10） |
| `nickname` / `nickname_i18n` | 全部 | 界面层级第二层的源名，可从 `zh-CN` 折出单语言镜像 |
| `region` | 全部 | 留空表示所有地区可见 |
| `builtin` | 全部 | 继承父源；远程文档写了也不能自行提权 |

随包索引（`src-tauri/resources/maps.toml`）目前只声明 `community-maps` 一个 `release-tags` 源，**没有内联地图**：条目要联网读各 Release note，离线首启或断网时地图页为空，刷新失败会沿用上次成功生成的条目（`MapSourceContext.previous`）。要让地图随包可用，得再加一个 `repository` 或 `document` 条目。

声明级坐标（`provider` / `username` / `repository`）优先：`repository` 模式里条目自己的坐标只在声明级为空时补上，`provider` 永远以声明级为准。

### 3.2 单仓库地图（`mode = "repository"`）

`[map_sources.map]` 与老的 `[[maps]]` 条目字段完全一致：

```toml
[map_sources.map]
enabled = true

# 展示用（只写多语言表即可，单语言镜像会自动从 zh-CN 折进来）
name_i18n.zh-CN = "RW 关卡合集"
name_i18n.en = "RW Level Pack"
# 分组 = 作者显示名：地图安装页按它折叠（见下方说明）
group_i18n.zh-CN = "RickWang"
group_i18n.en = "RickWang"

# 下载方式
channel = "all"           # all / stable / beta
max_release_count = 10
download_threads = 32

# 选哪个资产：地图只分发 ZIP
asset_rules = [
  { type = "glob", value = "rw_v*.zip" },
]

# 绑定本地关卡集的身份（必填）：必须与 info 里的 levelSetName / author 一致
level_set_name = "RW_LevelSet"
author = "RW"

# 简介（多语言）：没有这条时卡片显示「此地图暂无说明」
note_i18n.zh-CN = "包含 10 张由 RW 制作的自定义关卡。"
note_i18n.en = "Ten custom levels by RW."
```

必填字段与失败后果：

| 字段 | 缺失时 |
|---|---|
| `level_set_name` | 整份源解析失败：`地图「X」缺少 level_set_name` |
| `author` | 允许为空（官方导出常为空），但要与 info 一致 |
| `username` / `repository` | 整份源解析失败 |
| `asset_rules` | 整份源解析失败 |
| `name_i18n` / `note_i18n` | 不算错，标题退回 `用户名/仓库名`，说明显示「此地图暂无说明」 |

`group_i18n` 是**地图安装页的第二层**：第一层是地图源（`[[map_sources]]` 的 nickname，由后端 `MapRepositoryConfig.source_name` 落到配置里），第二层是 `group_i18n.zh-CN` 相同的条目（组标题就是分组名），第三层才是地图卡片 —— 与 MOD 安装页的「源 → 分类 → 卡片」完全同构，分桶与折叠规则共用 `useSourceGroupTree.ts`。地图管理页没有源层，仍按作者折叠本地关卡集。

与 MOD 侧的分组语义不同：MOD 的 `group` 是职责/相似性分类，地图的 `group` 是作者。它和 `author` 是两个不同的东西：

- `author` 是**绑定键**，必须与 ZIP 里 `info` 的 `author` 逐字一致（忽略大小写），否则认不出本地关卡集；
- `group_i18n` 是**展示名**，可以写作者更完整的名字。绑定键是 `RW`、分组写 `RickWang` 是正常的，不要为了“看起来一致”去改 `author`。

同一个作者的多张地图必须写同一个 `group_i18n`，否则会在界面上被拆成两个分组（`tools/oc2-info` 默认就按作者名生成，作者不用每张图手填）。地图管理页对**没有绑定到任何地图源**的本地关卡集回退到 `info` 里的 `author` 当分组名；两者都没有才归入「未分组」。

`provider` 决定 raw 与 API 的地址拼接规则，写错会直接 404。`region` 只接受 `chinese_mainland` / `international`（及其别名）；无法识别的值按「所有地区」处理并记一条 warn，**不会**让整份源失败。

### 3.3 单仓多 Release（`mode = "release-tags"`）

这个模式里**地图元数据不在 TOML 里**，而是写在每个 Release 的说明（Release note）里，用一段隐藏注释包起来：

```markdown
共 2 张关卡，由 GAODA 制作。需要在设置里启用 DIYLevel 框架。

<!-- oc2-map
level_set_name    = "GAODA"
level_set_name_zh = "胡闹达学"
author            = "GAODA"
name_i18n.zh-CN   = "胡闹达学"
name_i18n.en      = "GAODA"
group_i18n.zh-CN  = "GAODA"
group_i18n.en     = "GAODA"
note_i18n.zh-CN   = "共 2 张关卡。需要 DIYLevel 框架。"
note_i18n.en      = "2 levels. Requires the DIYLevel framework."
asset                 = "daxue_v${version}.zip"
latest_mapset_version = "0.3.2"
latest_info_version   = "0.3.2"
requires              = { "dev.gua.overcooked.diylevel" = ">=0.10.0" }
-->
```

注释在 GitHub / Gitee 上都不渲染，普通玩家看到的仍然是一段正常的更新说明；块外面的文字是**这个版本的更新日志**，块里面的字段是**这张地图的元数据**。

一个 Release 就是一张地图，它的资产是这张图的各个版本：

```text
daxue_v0.3.1.zip
daxue_v0.3.2.zip
```

**没有块的 Release 会被跳过**（例如只是发了个热修说明），所以同一个仓库里可以混放地图 Release 与普通 Release。

块的字段：

| 字段 | 说明 | 缺失时 |
|---|---|---|
| `level_set_name` | 本地关卡集的 `levelSetName` | 块无效，该 Release 跳过并记 warn |
| `level_set_name_zh` | 中文名 | 允许为空 |
| `author` | 本地关卡集的 `author`，官方导出常为空串 | 允许为空，但绑定按空串比对 |
| `name_i18n.<locale>` | 卡片标题（五语） | 退回 `level_set_name_zh`，再退回 `level_set_name` |
| `group_i18n.<locale>` | 分类名（五语），只影响分桶、不参与身份 | 与 `name_i18n` 相同（一 tag 一张图，各自成一类）；`tools/oc2-info` 生成时默认把中英都写成 `author` |
| `note_i18n.<locale>` | 卡片上的**简短**说明（五语） | 退回单语言 `note`；都没有则卡片显示「此地图暂无说明」 |
| `note` | `note_i18n` 的单语言兜底 | 允许为空 |
| `asset` | 安装包名模板，`${version}` 是占位符 | 见下方「版本怎么抽」 |
| `latest_mapset_version` | 作者声明的「这就是最新版」**地图包版本**（旧名 `latest_version` 仍认） | 按数字段取最大 |
| `latest_info_version` | 该版 `info` 文件**内**的版本号，`tools/oc2-info` 自动写 | 按 `latest_mapset_version` 判定 |
| `requires` / `compatible` / `conflicts` | 三张关系表，见 §3.4 | 无依赖 |

`provider`、`username`、`repository`、`tag` 由解析方从「源声明 + Release 本身」补上 —— 那些是仓库坐标，写在每份 note 里只会重复。条目的 `tag` 就是该 Release 的 tag 名。

**为什么有两个版本字段**：`latest_mapset_version` 是地图包（Release）的版本，决定「最新的那条 Release 是哪个」（`0.7 > 0.69` 这种数字比较会得出反的结论，作者写了就以它为准）；`latest_info_version` 是这一版 `info` 文件里作者自报的版本。两者平时相同，但作者升了包版本却忘了改 `info` 里的版本号时会不同 —— 本地读到的版本（来自 `info`）永远追不上包版本，界面就会一直显示「可更新」。管理器于是用 `latest_info_version` 与本地 `info` 版本做**等值**判定：相等即「装的就是最新版」，与包版本怎么比较无关。`tools/oc2-info` 生成块时把 `info` 里的版本写进 `latest_info_version`，作者不用手填。

**版本怎么抽**：`asset` 模板里的 `${version}` 会被替换成版本号形状（数字段、点分隔），模板其余部分按字面转义，整串锚定。例如：

```toml
asset = "daxue_v${version}.zip"
# → ^daxue_v(?P<version>[0-9]+(?:\.[0-9]+)*)\.zip$
```

省略 `asset` 时，解析方取该 Release 里第一个 `.zip` 资产名反推：找到数字版本号，把两侧的字面文本当锚点拼成正则。因此 `blni_v2.1.zip` 与 `blni_v2.2.zip` 都能被同一个 Release 的条目接住。资产名里推不出版本号时该 Release 会被跳过（warn 里有原因）。

同一张图的多个版本可以放在同一个 Release 的多个资产里，也可以一个版本一个 Release —— `release-tags` 模式下**一个 Release 只代表一张地图**，版本号只影响「版本列表里有哪些可回滚的项」。

**读取成本**：管理器默认每页 50 条、最多 20 页，`<页大小` 或空页即停止，所以一个有 12 个 Release 的仓库只需要 1 次 API 请求。同一个仓库在一次刷新动作里只请求一次（`release_cache` 的 `pass_id` 去重 + 60 秒 TTL），匿名 GitHub 的 60 次/小时因此够用。API 失败时**沿用上一次成功生成的条目**并记 warn —— 第三方源不该因为一次限流或断网从地图页整块消失（用户会以为作者下架了地图）。

`tools/oc2-info` 就是用来生成这段块的：读 ZIP 里的 `info`，按 `--asset` / `--note*` / `--requires` 等参数拼出注释；`latest_info_version` 它自己填，`latest_mapset_version` 由 `--latest`（或 `OC2_MAP_LATEST_VERSION`）给。手动跑用命令行，CI 用 `OC2_MAP_*` 环境变量。

### 3.4 依赖声明

地图由 DIYLevel 读取，前置由 Web Runtime 提供。当前基线：

- `dev.gua.overcooked.diylevel` ≥ **0.10.0**
- `oc2.oc2diylevelruntimewloader` ≥ **3.10.2**

两种模式写法不同，语义相同：

```toml
# [[maps]] / [map_sources.map] 里：写在文件末尾
[[maps.relations]]
kind = "requires"
guid = "dev.gua.overcooked.diylevel"
version = ">=0.10.0"

[[maps.relations]]
kind = "requires"
guid = "oc2.oc2diylevelruntimewloader"
version = ">=3.10.2"
```

```toml
# Release note 的块里：三张内联表
requires   = { "dev.gua.overcooked.diylevel" = ">=0.10.0" }
compatible = { "dev.gua.overcooked.diylevel" = ">=0.10.0,<=0.11.9" }
conflicts  = { "com.example.oldloader" = ">=4.0.0" }
```

两种写法里的版本边界都是同一个 `version` 字段，语法与 pip 的 requirement specifier 一致：逗号分隔的多个条件取**同时满足**（AND），`""` 或 `"*"` 表示不限，其余写 `>=x`、`>x`、`<=x`、`<x`、`==x`（`=x` 同义）、`!=x`，例如 `">=0.10.0,<0.12.0"`。三条规定：

- **比较符必须写出来**。裸版本号（`version = "0.10.0"`）会被拒绝并记 warn：老写法里 `min_version = "0.10.0"` 是「至少 0.10.0」，若把裸值按「恰好等于」解释，要求会被静默收窄。
- **`~=` 不支持**。本项目的版本号有 4 段写法（`1.9.8.1` ≡ `1.9.8-beta.1`），`~=1.9.8` 到底锁到哪一段有歧义，请写 `">=1.9.8,<1.10"`。
- 下限高于上限（`">=2.0,<1.0"`）会被校验拒绝。

需要额外开关时写显式表：

```toml
conflicts = { "oc2.oc2diylevelruntimewloader" = { version = ">=4.0.0", prerelease = true } }
```

`optional = true` 表示这条关系只是提示、不参与「缺依赖」判定（只对 `requires` 有意义）。

#### 按地图版本换一套依赖

有些地图在新版本里换了前置（例如把 DIYLevel 的要求从 0.10 提到 0.12）。这时写覆盖表，按「这个 Release 的版本」整套替换关系，而不是逐条改写：

```toml
# 源文档里
[[maps.release_relations]]
version = ">=2.0.0,<3.0.0"
relations = [
  { kind = "requires", guid = "dev.gua.overcooked.diylevel", version = ">=0.12.0" },
]
```

```toml
# Release note 的块里（内层与上面三张表写法一致）
[[release_relations]]
version = ">=2.0.0,<3.0.0"
requires = { "dev.gua.overcooked.diylevel" = ">=0.12.0" }
```

规则：

- 命中的是「版本落在 `version` 区间内」的覆盖表；命中多张时取**区间下限最高**的那张（下限相同取先出现的），它的关系**整体替换**地图的三张表（不合并）。版本列表里只有 Releases 的 tag，`version` 比的是这个 tag 去掉 `v` 之后的值。
- 一张覆盖表都不命中就沿用地图自己的 `relations`。
- 写 `version = "*"`、不写 `version`、或内层一条关系都没有的覆盖表会被丢掉并记 warn —— 它会匹配所有版本，效果等于直接改上面三张表，作者却以为限定了范围。
- 生成用 `tools/oc2-info`：`--relations-for ">=2.0.0,<3.0.0"` 之后的 `--requires/--compatible/--conflicts` 归进这一组，直到下一个 `--relations-for`（写在第一个之前的仍进顶层三张表），区间不能是 `*` 或空、每组至少要有一条关系；CI 里同一件事用 `OC2_MAP_RELEASE_RELATIONS`（JSON 数组，每项 `version` + 三张表，与命令行合并后 `version` 不许重复）。`--print` 回读校验同形态，只认三张表（手写的 `relations = [{ kind, guid, version }]` 数组管理器认、工具不认）。不给覆盖组时输出与旧版逐字节一致。

`[[maps.relations]]` **必须写在条目末尾**：TOML 里 `[[maps.relations]]` 之后的所有键都属于那个 relation 表。写在地图字段中间会把后面的 `level_set_name` 等字段吞进 relation，表现是「字段明明写了却报缺失」。

管理器会对照本机已装插件版本判定是否满足，在卡片上显示依赖提醒：必须依赖没满足时一律是「缺依赖」（与 MOD 卡片是同一枚 key `modsOnline.missingDep`，不是自造的「依赖缺失」；线上有满足区间的候选仓库时标签可点去安装），兼容关系差一个版本时才是「可安装」（`tools.installable`，可点去安装）；详情抽屉的「说明」页里有一张**依赖表**（排在备注上方，与分割线隔开；表头 `MOD / 关系 / 要求 / 状态` 本身就是标题，没有额外的「依赖框架」小标题），逐条列出「哪个依赖 / 版本要求多少 / 本机是否满足」。这张表与 MOD 安装页、MOD 管理页的依赖表是同一个组件（`DependencyTable.vue`）与同一份行构造逻辑（`src/dependencyRows.ts`）：名称按「在线 MOD 仓库卡片名 → 本地已装 MOD 的安装包标题 → GUID」解析，所以这里显示的是作者在源文档里给框架起的名字，而不是 `required_frameworks` 里的 GUID；关系列只在出现非 `requires` 的关系时才出现。

状态列的标签与卡片上的状态标签同一档（`.state-tag` + `theme.ts` 色阶）。**满足时只写「已满足」，不带版本号** —— 版本写在「要求」列，状态列只回答「现在行不行」。地图与 MOD 走**同一套**结论：必须依赖缺了就写「缺依赖」，线上有候选仓库时**可点**（跳到 MOD 安装页里那张能提供它的仓库卡片）、没有来源时不可点；兼容关系差一个版本写「可安装」并且**可点**。

判定只有一处：`dependencyRows.ts`（依赖表行 + 跳转）与 `modRelations.ts::relationTagView`（卡片标签 + 落点，`dependencyTagFor` 只做「装了才显示」的门控），四个页面（MOD 安装 / MOD 管理 / 地图安装 / 地图管理）统一调用。关卡集的关系声明来源也与依赖表同一条链（`levelSetStatus.ts::levelSetRelationStatuses`）：绑定在线地图就用它的声明，地图源下线或本地导入的图才退回 `info` 快照里的 `relations`。

依赖声明还有一份**快照**：地图安装成功时，管理器把该地图仓库的 `relations` 写进数据根的 `manifests/map-relations.json`（管理器侧清单，不写进游戏目录）；之后每次刷新地图源、检测更新都由 `sync_dependency_snapshots` 按线上声明整体重写（配置里已删除的地图条目会从快照里消失）。地图源被删或下线后，本地关卡集的依赖表从这份快照渲染，不会凭空消失 —— 在线与本地不一致时以在线为准。

满足性判定只发生在**管理器前端**：后端只把 `relations` 原样解析成声明（`MapInfo.relations`），不再为它重扫 `BepInEx/plugins`。地图管理页用 Dashboard 已经扫描到的本机 MOD 列表比对，所以没探测到游戏目录时卡片标签显示「无法判定」，而不是错误地报「缺失」（依赖表本身没有「无法判定」这一档，那种情况下写的是「未安装」）。

判定不满足时**不阻止安装**（用户可能想先装地图再升级框架），但提示会明确说「装上后地图仍无法加载」。

### 3.5 身份与 ID

map 条目的 ID 由「源 ID + author + level_set_name（+ 中文名）」派生，**不含 tag**，因此：

- 刷新源树不会改变 ID，Release 缓存、用户的手动禁用都能接回；
- 改动 `author` 或 `level_set_name` 等于发布一张新地图，旧条目的缓存不会跟过来；
- 同一份源里两条声明身份相同会被拒绝（会抢同一个本地目录）：TOML 里是 `duplicateEntry` 错误，Release note 里是跳过后者并记 warn。

身份比较忽略大小写：`RW` + `RW_LevelSet` 与 `rw` + `rw_levelset` 视为同一张地图。

### 3.6 老形态：`document` 子源

`url` 指向一份 `[[maps]]` 文档，与仓库源一样支持三种地址形式：

1. **完整 HTTPS 地址** —— 任意合法地址，不能带认证信息；
2. **相对路径** —— 相对**当前文档所在位置**解析。远程文档以重定向后的真实地址为基准；内置资源以自身所在目录为基准；
3. **内置资源名** —— 仅在内置快照里有效。

文档里先写 `[[maps]]` 条目（字段同 §3.2），末尾写 `[[maps.relations]]`；同一份文档里的地图都来自同一个仓库时，可以把坐标写在顶部 `[bundle]`：

```toml
[bundle]
provider = "github"
username = "QingyuQingxue"
repository = "OC2-Map-Bundle"

[[maps]]
name_i18n.zh-CN = "音乐厨房"
tag = "yinyuechufang"
level_set_name = "YinYueChuFang_LevelSet"
author = "QingyuQingxue"
asset_rules = [
  { type = "regex", value = '^yinyuechufang_v(?P<version>[0-9.]+)\.zip$' },
]
```

- 继承是**整组**的：`username` 与 `repository` 任一个为空就整组用 `[bundle]` 的值；
- `[bundle]` 只在当前文档内生效，不传给子源；
- 子源可以继续声明子源，但最多 3 层。超出部分会被丢弃并记 warn 日志；检测到循环引用也会跳过。

`document` 模式仍支持**条目级 `tag`**（老写法）：`tag = "yinyuechufang"` 表示只读这个 tag 的 Release，那个 Release 里的每个资产是该图的一个版本，规则与 `release-tags` 的资产拆分相同（正则必须整串锚定且带版本捕获组，优先 `(?P<version>…)`）。`max_release_count` 在 tag 模式下语义是「最多显示几个版本」，列表 API 的 `per_page` 固定拉满。

### 3.7 第三方源：文档托管在 Release 资产里

`document` 模式的 `url` 可以直接写 Release 资产地址：

```toml
[[map_sources]]
id = "some-bundle"
url = "https://github.com/QingyuQingxue/OC2-Map-Bundle/releases/download/maps/map-sources.toml"
builtin = true
```

这种形态与普通子源有三处不同，都由后端自动处理：

1. **先取校验信息再下载**：向同一个仓库的 API 要这个资产的 size/sha256，然后走与其他下载相同的「直连 / 加速竞速」拉取并校验（GitHub 给 `sha256:` 摘要，Gitee 只给长度）。API 拿不到校验信息时退回单次直连 —— 校验是增强，不该变成新的失败点。
2. **文档里不能写相对子源**：Release 资产地址会 302 到签名地址，相对路径必然解析到错误位置，后端直接报 `source.relativeChildInReleaseAsset`。绝对地址照常可用。
3. **同一个仓库一次动作只打一次 Release API**：源文档的校验与各条目的版本列表共用同一份列表（`release_cache`）。

内置索引里登记远程子源要写 `builtin = true`：这个字段的含义是「随包登记过、开内置模式也要加载」，**不代表官方维护**。不登记的话「仅使用内置地图源」打开时会整条跳过它（默认关闭的今天，远端索引里的声明才决定加载哪些源）。

### 3.8 社区地图源（自动发现）

`maps.toml` 里的源是**声明出来的**；另有一类源是**发现出来的**：社区发现（`docs/community-repositories.md`）扫到带 `map` topic 的仓库后写入 `config.toml` 的 `community_map_repositories`（只存 `provider` / `username` / `repository` 三个坐标，不存条目），地图源树加载时把它们追加在官方索引之后。

- 每个仓库展开成一个 `mode = "release-tags"` 声明（`map_sources::community_map_declaration`）：`nickname` 是 `owner/repo`，分页参数走默认（每页 50、最多 20 页）。
- 源 ID 只有两个：`github-map-community` / `gitee-map-community`（`GITHUB_COMMUNITY_MAP_SOURCE_ID` / `GITEE_COMMUNITY_MAP_SOURCE_ID`），同平台所有社区仓库共用一个源，界面顶层显示「社区地图（GitHub）」/「社区地图（Gitee）」等五语名称，中层再按作者聚合 —— 一个仓库一个源会让顶层铺满陌生仓库名。
- 与官方索引**撞身份**（`map_identity`，作者 + 关卡集名）时保留官方条目：官方树先加载，`append_community_map_maps` 的 `seen` 集合按身份去重。
- 单个仓库读 Release 失败只 warn 跳过，不影响其它社区仓库与官方树；上一轮的条目靠 `MapSourceContext.previous` 沿用（`previous_for` 按 `source_id` 过滤，是当前配置的超集，`seen` 同样去重）。
- 社区仓库上限 50 个（`MAX_COMMUNITY_MAP_REPOSITORIES`），超出只 warn —— 每个仓库一次 Release 列表请求，匿名 GitHub 的配额撑不住更多。
- 首次启动的**顺序**：地图源树必须等社区发现写完配置再加载，否则首启看不到社区地图。前端在 `useRepositoryRefresh` 里用 `whenCommunityDiscovered()` 兑现这个时序（`App.vue` 的 `settleRefresh` 先 `requestStartupRefresh()`，等发现结束才 `requestMapSourcesStartupRefresh()`），不等整批 Release 刷新。

## 4. Release 与资产

管理器对地图 Release 的处理与 MOD 仓库共用同一条流水线（超时、重试、403 处理、加速选择、5 分钟缓存），只有两点不同：

- 资产只选 ZIP。`asset_rules` 支持 `exact` / `glob` / `regex`；
- 不读安装目录配置：ZIP 里的关卡集目录名就是落盘目录名。

详情抽屉的版本/资产区与 MOD 安装页是**同一个面板**（`ReleaseDetailPanel.vue`）：

- **说明**页显示这张地图的 `note_i18n`，长文按 Markdown 渲染；没有说明时显示「此地图暂无说明」。地图详情**不拉仓库 README** —— README 是仓库级的，一个仓库放多张图时会把说明串在一起；
- **下载安装**页的版本下拉允许回滚到更旧的版本（默认最新），选中项的「提交日志」就是那个 Release 的 note **剥掉 `<!-- oc2-map -->` 块之后**的正文；
- **资产下拉**列出命中 `asset_rules` 的文件（规则没写或没命中时退回该 Release 的全部可下载文件），选中项的名称会随安装命令传给后端，按名字精确匹配 —— 界面上显示哪个就下载哪个，不会静默换成别的。

下载与安装完全复用 MOD 侧实现，地图侧没有任何私有分支：

- 点「安装」后先走 `useLevelSetImport` 的 `finishStaged`：处理同身份冲突，再弹与 MOD 共用的确认界面（含依赖检查），确认后才开始下载；
- 下载进度走全局进度条（`DownloadStrip`）：领先文件字节数、竞速源数量、当前路由、速度与取消按钮都与 MOD 一致。进度按**已下载字节最多的那个文件**展示，不是把并行源加总；
- 传输层同样是多源竞速：GitHub 走自动直连 / 自动加速的最多三个完整文件竞速（5 秒窗口内平均速度低于 256 KiB/s 的源让位并补候选），Gitee 只有直连。

发布约定：

- `repository` 模式：一个仓库只放一张图，tag 建议用 `v0.73` 这类写法；
- `release-tags` 模式：**一张图一个 tag**，tag 名随便取（`daxue`、`chan` 都行），版本追加成同一 Release 下的新资产，或者发一个新 Release 再放这一版的资产；
- 资产名建议带版本（`rw_v0.73.zip`、`daxue_v0.3.2.zip`），模板或规则就能只取正式包，避免把源码 ZIP 也选进来；
- GitHub 资产若带 `sha256:` 摘要，管理器会在安装前校验；Gitee 不提供摘要，只校验长度与 ZIP 结构。

## 5. 上线检查清单

`repository` 模式：

1. ZIP 里恰好一个关卡集目录，里面有 `info`，且能被解析出名字、作者、版本、关卡数；
2. `level_set_name` / `author` 与 `info` 完全一致（大小写不敏感）；
3. `group_i18n` 写作者显示名；
4. `asset_rules` 能唯一选中正式包；
5. `relations` 写在文件末尾，版本号与当前基线一致；
6. 至少发布一个 Release，且它能被「刷新」拉到。

`release-tags` 模式：

1. 每个该被认作地图的 Release 都带 `<!-- oc2-map … -->` 块，块里至少有 `level_set_name`；
2. 块里的 `level_set_name` / `author` 与 ZIP 里 `info` 一致；
3. `asset` 模板（或资产名本身）能抽出版本号；
4. `note_i18n` 五语写全（或至少 `zh-CN`），玩家才看得到卡片说明；
5. 仓库地址与 `maps.toml` 里声明的 `provider` / `username` / `repository` 完全一致；
6. 源加载时管理器会自动读这个仓库的 Release；发完新 tag 后在管理器里点一次「刷新地图源」。

发布后自测分两条路：

- **默认路径**：`builtin_map_sources_only` 默认关闭，刷新先读远端 `maps.toml`；远端读不到（官方 Repos 仓里 `maps.toml` 目前仍是 404）时 `refresh_map_sources` 回退到 `src-tauri/resources/maps.toml` 里的内置声明并记 `bundled-fallback`，下次刷新继续先试远端。打开「仅使用内置地图源」则只读内置声明（`release-tags` 条目仍要联网读 Release）。内置索引现在只有 `community-maps`：改它指向的 GitHub 仓库后，在管理器里点一次刷新即可。若要在索引里加随包 `repository` / `document` 条目，改完 `maps.toml` 要重启 dev 进程（`build.rs` 把它编进二进制）。
- **对比线上内容**：默认已经是远端索引；要看内置快照就临时打开「仅使用内置地图源」再刷新，验完关回去。远端 `maps.toml` 目前 404，所以远端刷新会落到 bundled 回退。

## 6. 常见失败与原因

| 现象 | 原因 |
|---|---|
| 地图页空白 | 源树没加载成功；看 `logs/rust.log` 的「地图源树加载完成」与子源 warn |
| 某个 `release-tags` 源没有地图 | 仓库不可达、限流，或所有 Release 都没有有效块；日志里逐条写了「没有 oc2-map 块」「块无效」「没有能提取版本号的地图包」 |
| 卡片显示「刷新失败」 | Release API 请求失败（仓库名错、私有仓库、地区限制） |
| 卡片标题变成 `用户名/仓库名` | 块里没有 `name_i18n`，且 `level_set_name*` 也是空的 |
| 卡片说明永远显示「此地图暂无说明」 | 块里没写 `note_i18n`（或 `note`）；块外面的正文是版本更新日志，不是卡片说明 |
| 安装报「与来源声明不一致」 | ZIP 里的 `levelSetName`/`author` 与 note 块里的不一致 |
| 安装报「有 N 个关卡集」 | ZIP 里放了多个关卡集，请拆成多个仓库/Release |
| 装上但游戏里没有 | 缺 `relations` 声明的框架，或框架版本不满足 `version` 区间（含按版本覆盖的表没命中） |
| 卡片显示「缺依赖」 | 本机缺 `diylevel` 或 Web Runtime 之一，或版本低于基线；标签悬停会列出缺的 GUID 与版本要求，详情里的依赖表逐条说明 |
| 改字段后没生效 | 改的是 `author` / `level_set_name`（身份变了），或配置里的 ID 已被旧条目占用 |
| 卡片显示「规则缺少版本号」 | `document` tag 模式下正则没写捕获组，或没写成 `^…$` 整串锚定 |
| 第三方源加载失败并提示相对子源 | 源文档放在 Release 资产里，里面的子源必须写绝对地址（见 §3.7） |
