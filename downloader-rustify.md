# yutto 下载器 Rust 化设计方案

> 状态：Draft
>
> 本文设计 `Fetcher` 下载部分的 Rust 多源下载器 `haya` 及其 yutto 接入方式。通用核心 crate 定名为 `haya`，HTTP adapter 定名为 `haya-http`，yutto 集成 crate 定名为 `yutto`。

## 1. 结论

将当前 `Fetcher.download_file_with_offset()`、`AsyncFileBuffer` 和外围分块任务调度替换为一个 Rust 多源下载器是可行且值得的。

第一阶段的目标应收敛为一个通用能力：

- 给定多个被调用方声明为等价的 source；
- 以固定大小的 page 和较大的 HTTP Range block 并发读取；
- 使用有限 look-ahead window 控制内存和网络在途量；
- 优先修复阻塞连续提交的最前缺口；
- 对 source 做健康度、冷却、切换和有限重试；
- 只将连续前缀顺序写入 sink，使文件长度天然成为续传位置；
- 通过粗粒度 API 和状态快照接入 Python，不让每个 page 穿越 PyO3。

## 2. 当前实现与问题

当前媒体下载路径大致为：

```text
DownloadPlan
  -> slice_blocks()
  -> 为每个 block 创建一个 coroutine/task
  -> ExecutionScope.download_limiter 控制同时运行的 task 数
  -> Fetcher.download_file_with_offset()
  -> AsyncFileBuffer 按 offset 入堆
  -> 连续 chunk 顺序 append 到文件
```

相关实现：

- `src/yutto/downloader/transfer.py`
- `src/yutto/utils/fetcher.py`
- `src/yutto/utils/file_buffer.py`
- `src/yutto/downloader/progressbar.py`

现有设计中值得保留的性质是：

```text
文件实际长度 == 已经连续提交的远端字节数
```

因此进程退出后只需要读取文件长度，就能从连续前缀继续下载；尚未连续提交的内存块丢失也不会破坏文件。

当前主要问题不是堆本身，而是缺少一个掌握全局状态的调度器：

1. `download_guard()` 包住整个 block 的无限重试循环。坏块会一直占用 worker；坏块数量达到并发上限后，全局可能永久停止。
2. 所有 block task 一次性创建，只靠 semaphore 控制活跃数量。调度器不知道哪个 block 正在阻塞连续提交。
3. mirror 每次随机等权选择，没有 source 健康度、冷却时间或失败原因分类。
4. 没有有限 attempt、总重试预算和明确的失败终点。
5. 后方 block 可以持续下载并进入缓冲区，缺少 bounded look-ahead 和真正的反压。
6. Range 响应状态、`Content-Range` 和实际长度未被严格校验；clean EOF 可能被误判为完成。
7. `AsyncFileBuffer.ensure_flushed()` 只能证明内存 pending 为空，不能证明已提交位置等于预期结尾。
8. progress 直接读取 `AsyncFileBuffer.buffer` 内部结构，下载状态与展示层耦合。
9. 部分交叠 chunk 当前会整块丢弃；若其中还含有未写入后缀，语义不明确。

## 3. 目标

#### 通用传输能力

- source 不限于 B 站 CDN；只要能探测资源并读取 byte range 即可接入。
- sink 不限于本地文件；核心只依赖“读取连续提交位置”和“顺序追加”能力。
- HTTP、文件系统和 yutto 适配位于核心外层。
- source 选择、retry、窗口和 blocker 恢复有明确状态，而不是散落在请求循环中。

#### 正确性

- 只有完整、经过边界校验的 page 才能进入 ordered buffer。
- 只有从 committed cursor 开始连续的 page 才能写入 sink。
- 已知总长度时，成功条件必须是 `committed_offset == expected_end`。
- 任意错误、取消或 panic 都不能把不连续数据伪装成可续传前缀。
- 多个 source 必须属于同一资源等价组，且每次 Range 响应均需校验。

#### 可控性

- 内存上限由 `page_size * window_pages` 决定。
- 网络在途量由 window reservation 和 worker limit 共同决定。
- 单个坏 source 或坏 block 不能永久占用全局 worker。
- 当前 blocker 始终获得优先调度和独立恢复机会。
- progress 能区分“已收到”“等待前序”“已提交”。

#### 渐进迁移

- Python CLI、Server、JSON-RPC 和现有事件语义可继续使用。
- Rust backend 未成为默认前，可以显式选择旧 Python backend 或新 Rust backend；一次传输过程中禁止静默切换 backend。
- Rust backend 稳定后删除 Python 分块下载实现，避免长期维护两套下载器。

## 4. 术语与默认参数

### 4.1 Page

ordered buffer 接收的原子数据单元。除全局最后一页外，每个 page 大小固定。

建议默认值：

```text
page_size = 64 KiB
```

page 边界相对于本次传输的 `origin` 计算，而不是必须相对于文件绝对偏移 0 对齐。续传时：

```text
origin = 现有文件长度
page 0 = [origin, origin + page_size)
```

### 4.2 Block

一次 HTTP Range attempt 负责的较大连续区间。一个 block 包含多个 page。

建议默认值：

```text
block_size = 512 KiB
pages_per_block = 8
```

除最后一个 block 外，`block_size` 必须是 `page_size` 的整数倍。外层传入任意 block size 时，应在创建 `TransferSpec` 时量化到合法值，而不是让 HTTP adapter 临时猜测。

### 4.3 Window

从 `next_page` 开始、允许被保留和下载的 page 范围：

```text
[next_page, next_page + window_pages)
```

建议默认值：

```text
window_pages = max(2 * workers * pages_per_block, pages_per_block)
```

在默认 `workers=8`、`pages_per_block=8` 时，window 为 128 pages，即最多约 8 MiB page 数据。实现还需计算 channel、HTTP client 和单个 response 内部缓冲造成的额外内存。

### 4.4 Attempt

对某个 source 和某段 Range 的一次有限 HTTP 请求。attempt 不自行无限重试，只返回结果，由 coordinator 决定后续动作。

### 4.5 Committed cursor

下一个尚未写入 sink 的绝对字节位置：

```text
[0, committed_offset) 已顺序写入
[committed_offset, ...) 可能已收到，也可能存在缺口
```

### 4.6 Blocker

包含 `committed_offset`、因而直接阻止连续提交继续前进的 page 或 block。

## 5. 总体架构

```text
                    +-----------------------+
                    |     yutto adapter     |
                    | URLs / cookies / UI   |
                    +-----------+-----------+
                                |
                         TransferSpec
                                |
                                v
+-------------------+   +-------+---------+   +--------------------+
| HTTP RangeSource  |<--| TransferEngine |-->| Sequential FileSink|
| primary + mirrors |   |   coordinator  |   | ordered append     |
+---------+---------+   +--+----------+---+   +----------+---------+
          |                |          |                  |
          | Range attempts |          | Ready pages      | file length
          v                v          v                  v
    reqwest streams   source pool   bounded ring    resume cursor
                          |
                          +-> retry / cooldown / hedge / split
```

运行时至少包含三个角色：

1. `TransferCoordinator`：唯一掌握 block 状态、source 状态、window、优先级和 retry 预算的组件。
2. Range workers：只执行一次有限 attempt，将任意网络碎片规范化为完整 page。
3. Ordered writer：独占 sink 和 ring，按连续顺序写入，并向 coordinator 发布新的 committed cursor/credits。

## 6. Crate 与 workspace 边界

相关 Rust 代码集中在 `packages/yutto-core` 下，由一个 Cargo workspace 管理。按外部依赖和职责拆 crate，不按内部类名拆包；目录归属不改变通用 crate 的依赖方向。

### 6.1 `haya`

公共下载器核心 crate，包含：

- `TransferSpec`、`ByteRange`、`PageIndex`、`SourceId` 等模型；
- `TransferCoordinator` 和 block/page 状态机；
- source health、retry、backoff、cooldown、hedging、split 策略；
- bounded window reservation；
- ordered buffer 的公共语义和默认实现；
- `RangeSource`、`CommitSink` 等 port；
- `TransferEvent`、`TransferSnapshot` 和错误类型；
- cancellation 协议；
- 默认顺序文件 sink。

默认文件 sink 放在 `haya::file` 内，不单独发布 `haya-file`。它负责：

- `Overwrite` 与 `ResumeFromLength` 打开模式；
- 单 writer；
- 顺序 append；
- flush/close；
- 将普通文件 I/O 放到合适的 blocking pool 或专用 writer 执行上下文。

它不得依赖：

- reqwest；
- PyO3；
- yutto 类型；
- B 站 URL 或 headers；
- 中文日志；
- 具体输出文件命名。

首版允许依赖 Tokio。通用能力优先不等于必须 runtime-neutral；强行抽象 timer、task 和 channel 会显著增加 API 成本，而目前没有第二个 runtime 的真实需求。

### 6.2 `haya-http`

公共 crate，提供 reqwest `RangeSource` adapter：

- 资源大小与 Range capability 探测；
- `Range` 请求构造；
- `Accept-Encoding: identity`；
- `206`、`Content-Range`、实际长度验证；
- redirect、proxy、cookie、header 和 TLS 配置接入；
- response `Bytes` stream；
- reqwest 错误到通用 `SourceError` 的分类。

该 crate 应允许注入外部构造的 `reqwest::Client`，不能强制创建一套固定连接池：

```rust
let source = HttpRangeSource::new(shared_client, url, headers);
```

client 的 headers、cookies、proxy、TLS 和连接池配置由 yutto adapter 统一构造并注入。

### 6.3 `yutto`

`packages/yutto-core` 内的 yutto 集成 crate，同时构建 PyO3 extension；它负责：

- PyO3 async 边界；
- 将 `DownloadPlan` 转换为 `TransferSpec`；
- 将主 URL 和 mirrors 转换为 source 列表；
- 注入 cookies、headers、proxy 和当前策略；
- 将 snapshot/event 投影为现有下载事件和中文展示；
- Python cancellation 与 Rust `CancellationToken` 的双向传播；
- 将 Rust 错误转换为稳定的 Python 异常。

`yutto-core` 是承载该 extension 的独立 native Python package，import 名为 `yutto_core`；Rust crate 从一开始就使用并发布为 `yutto`，将来 yutto 完成纯 Rust 化后继续沿用该 crate 名。

### 6.4 Workspace 布局与依赖方向

```text
packages/yutto-core/
├── pyproject.toml
├── src/
│   └── yutto_core/
│       └── __init__.py
└── rust/
    ├── Cargo.toml
    ├── Cargo.lock
    └── crates/
        ├── haya/
        │   └── Cargo.toml
        ├── haya-http/
        │   └── Cargo.toml
        └── yutto/
            └── Cargo.toml
```

依赖必须保持单向：

```text
haya-http ─────────────→ haya
yutto ────────→ haya + haya-http
Python yutto ─→ yutto_core
```

`haya` 即使位于 `packages/yutto-core` 目录内，也不得依赖 PyO3、yutto 类型或 binding crate。`haya`、`haya-http` 和 `yutto` 从同一 workspace 独立打包，并按依赖顺序发布：

1. `haya`；
2. `haya-http`；
3. `yutto`。

首个 crates.io 版本均为 `0.0.1`，从本地执行发布。workspace 内的 path dependency 必须同时声明相同的 crates.io version，使打包后的 crate 不依赖仓库目录结构。

Maturin 从 workspace 中明确选择 binding crate：

```toml
[tool.maturin]
manifest-path = "rust/crates/yutto/Cargo.toml"
module-name = "yutto_core._core"
```

### 6.5 暂不单独拆出的 crate

以下内容第一版留在 `haya` 内部：

- ring buffer；
- retry policy；
- source health；
- scheduler；
- progress accumulator。

它们共同维护同一个状态机。过早分别发布会让内部演化被跨 crate semver API 卡住。只有出现独立调用方和稳定契约后，再考虑抽出 `ordered-buffer` 等 crate。

## 7. 核心公共模型

以下 API 为方向性伪代码，不作为最终命名承诺。

### 7.1 TransferSpec

```rust
pub struct TransferSpec {
    pub expected_size: Option<u64>,
    pub resource_key: Option<String>,
    pub page_size: NonZeroUsize,
    pub block_size: NonZeroUsize,
    pub window_pages: NonZeroUsize,
    pub max_in_flight: NonZeroUsize,
    pub retry: RetryConfig,
    pub source_policy: SourcePolicyConfig,
}
```

约束：

- `block_size % page_size == 0`；
- `window_pages >= pages_per_block`；
- 已知大小且 `resume_offset > expected_size` 时立即失败；
- 未知总大小时退化为单流顺序模式，不做多 Range 并发；
- `resource_key` 是调用方提供的等价资源标识，核心不解析其业务含义。

### 7.2 RangeSource

```rust
pub trait RangeSource: Send + Sync {
    async fn probe(&self) -> Result<SourceMeta, SourceError>;

    async fn fetch_range(
        &self,
        request: RangeRequest,
        cancel: CancellationToken,
    ) -> Result<ByteStream, SourceError>;
}
```

```rust
pub struct SourceMeta {
    pub size: Option<u64>,
    pub range_support: RangeSupport,
    pub validator: Option<ResourceValidator>,
}
```

`ByteStream` 可以产生任意长度的 `Bytes`。固定 page 的规范化由 attempt/pager 完成，不要求 HTTP/TCP 天然按 64 KiB 分帧。

### 7.3 CommitSink

```rust
pub trait CommitSink: Send {
    async fn committed_len(&self) -> Result<u64, SinkError>;
    async fn append(&mut self, data: Bytes) -> Result<(), SinkError>;
    async fn flush(&mut self) -> Result<(), SinkError>;
    async fn finish(self) -> Result<(), SinkError>;
}
```

核心只允许顺序 `append()`，从类型边界上保证 sink 只能接收连续前缀。

### 7.4 AttemptOutcome

```rust
pub enum AttemptOutcome {
    Complete {
        range: ByteRange,
        source: SourceId,
    },
    Retryable {
        remaining: ByteRange,
        source: SourceId,
        error: SourceError,
        progress_bytes: u64,
    },
    Fatal {
        range: ByteRange,
        source: SourceId,
        error: SourceError,
    },
}
```

worker 只报告事实；是否重试、何时重试、是否换源或拆块由 coordinator 决定。

## 8. Page 规范化

网络响应可以产生任意大小碎片。每个 attempt 使用局部 pager：

```text
arbitrary Bytes stream
  -> accumulate
  -> 满 page_size 后提交完整 page
  -> clean EOF 时验证剩余字节
```

规则：

1. 非全局最后一页必须恰好为 `page_size`。
2. 已知 Range 长度时，短页只有在其结尾等于全局 `expected_end` 时合法。
3. timeout、connection reset 或取消不能把局部残片标记为最终页。
4. 出错时，只记录已经提交给 ordered buffer 的完整页；残片丢弃，下一 attempt 从首个未完成页重新读取。
5. clean EOF 但实际字节数少于请求 Range 时返回 `TruncatedRange`，不能报告完成。
6. Range response 超出请求长度时返回协议错误，不能截断后假装成功。

已知总大小示例：

```text
remaining = 150 KiB
page 0    = 64 KiB
page 1    = 64 KiB
page 2    = 22 KiB  // 唯一合法短页
```

未知总大小时：

- 只启动一个顺序 source；
- pager 仅在 clean EOF 后提交最终短页并 `finish()`；
- 若服务端忽略续传 Range 返回完整资源，应由 adapter 明确要求 restart 或失败，不能继续 append 造成重复前缀。

## 9. Bounded ordered buffer

### 9.1 状态

```rust
struct Slot {
    page_index: u64,
    state: SlotState,
}

enum SlotState {
    Empty,
    Reserved,
    Ready(Bytes),
}

struct OrderedBuffer {
    origin: u64,
    next_page: u64,
    committed_offset: u64,
    slots: Vec<Slot>,
}
```

`page_index` 必须保存在 slot 中，因为环形复用会发生：

```text
page 0 % capacity == page capacity % capacity
```

### 9.2 不变量

1. `committed_offset` 单调递增。
2. 所有 `< next_page` 的页均已成功写入 sink。
3. 只有完整 page 或经过验证的最终短页能进入 `Ready`。
4. 同一 page 最多存在一个有效 reservation。
5. window 外 page 不能保留 slot。
6. sink 写入成功后才能推进 `next_page` 和释放 credit。
7. 传输成功必须同时满足 buffer 无 pending 且 `committed_offset == expected_end`。

### 9.3 Drain

```rust
while slot(next_page).matches(next_page, Ready) {
    let page = take_ready(next_page);
    sink.append(page.data).await?;
    committed_offset += page.data.len() as u64;
    next_page += 1;
    release_slot_and_credit();
}
```

如果 sink 写入失败，传输进入 terminal failure，不能推进 cursor 或继续接受数据。

### 9.4 Ring 与 BTreeMap

公共契约只承诺 fixed page 和 bounded window。默认实现可以直接使用 ring：

- page index 到 slot 为 `O(1)`；
- 内存和分配可预测；
- window 边界天然明确。

如果首版实现阶段发现非对齐输入、reservation 或错误恢复尚未稳定，可以暂用 bounded `BTreeMap<PageIndex, Page>` 作为内部实现验证语义。两者应共享同一测试套件，公共 API 不因实现切换而改变。

## 10. Window reservation 与反压

普通 semaphore 只能限制数量，不能保证 blocker 有位置。若较远 page 抢完 permit，缺失的 `next_page` 可能永远无法进入，造成 head-of-line deadlock。

因此使用带 page index 的滑动窗口 reservation：

```text
当前允许：[next_page, next_page + window_pages)
窗口之外：不发 permit
```

对 HTTP block，优先一次性预留其全部 pages：

```rust
let permit = coordinator.reserve_range(start_page, page_count).await?;
let outcome = worker.run_attempt(source, range, permit).await;
coordinator.handle(outcome);
```

先 reserve，再取得 network worker permit，再发请求：

```text
RangePermit
  -> network permit
  -> HTTP attempt
  -> release network permit
  -> coordinator 决定 retry/backoff
```

禁止先占用 network permit 再等待 window，否则多个远端 block 可能占满 worker，让 blocker 无法启动。

完整反压链：

```text
ordered window 无新 credit
  -> coordinator 不调度新 Range
  -> worker 不继续 poll response 或不启动请求
  -> bounded channel 填满
  -> socket receive buffer / HTTP2 flow control 生效
  -> 上游发送速率下降
```

Tokio bounded `mpsc` 可以承担 ReadyPage 传递，但 channel capacity 不能替代 index-aware window；channel FIFO 中可能全是较远 page。

## 11. 调度器

### 11.1 Block 状态

```rust
enum BlockState {
    Pending,
    Reserved,
    InFlight { source: SourceId, attempt: u32 },
    RetryWait { ready_at: Instant, last_error: SourceError },
    Complete,
    Failed,
}
```

Coordinator 而不是 worker 持有这些状态。

### 11.2 优先级

建议优先级顺序：

1. 包含 `committed_offset` 的 blocker；
2. 距离 blocker 最近且位于 window 内的 block；
3. 已到 retry 时间的 block；
4. 从未尝试的普通 block；
5. hedged/投机任务。

音频和视频各自拥有独立 transfer engine 或独立逻辑队列时，由 yutto 外层决定总体并发分配；第一版不在通用核心内硬编码音视频公平策略。

### 11.3 有限 attempt

每次 attempt 都必须有：

- connect timeout；
- read-stall timeout；
- 可选总 deadline；
- cancellation；
- 明确的 Range 和 source。

attempt 结束后立即释放 network worker。backoff 位于 coordinator 中，不占 worker。

### 11.4 Blocker 恢复

对 blocker 使用更积极但有上限的策略：

1. 当前 source 超过 soft stall deadline 后切换健康 source；
2. 失败 source 增加 failure score 并进入 cooldown；
3. blocker 长时间无进展时，可在不同 source 上启动至多一个 hedge；
4. 较大剩余 Range 多次失败后，拆成更小 Range，最小不低于一个 page；
5. 达到全局重试/时间预算后明确失败并报告证据。

hedge 只用于关键 blocker，不能对所有慢块复制请求。第一个成功结果获胜，其他 attempt 被取消；重复 page 必须按 page index 幂等处理。

### 11.5 Critical lane

实现应保证 blocker 始终有执行机会。可以采用以下任一方式：

- scheduler 绝对优先 blocker；
- 在普通 worker 之外保留一个 recovery permit；
- hedged blocker 临时借用受限的额外 permit。

首选 scheduler 绝对优先；只有确认 starvation 仍存在时再引入独立 recovery permit。

## 12. Source pool

### 12.1 Source 等价性

多 source 下载的前提是它们返回同一资源字节序列。通用核心不能从 URL 推断等价性，必须由调用方声明一个 source group，并尽可能验证：

- 总长度一致；
- Range capability 一致或可用；
- `Content-Range` 与请求一致；
- 可用时比较 strong ETag/digest；
- yutto 提供业务 `resource_key`，例如由视频身份、清晰度和 codec 等构成。

跨 CDN 的 ETag 可能不同，因此不能把 ETag 相等设为唯一条件。首版提供两种策略：

```rust
enum EquivalencePolicy {
    StrictValidator,
    TrustedGroupWithSizeCheck,
}
```

yutto 默认使用 `TrustedGroupWithSizeCheck`，因为主 URL 和 mirrors 来自同一媒体候选；任何长度或 Range 响应冲突仍应立即隔离 source。

### 12.2 健康状态

```rust
struct SourceHealth {
    consecutive_failures: u32,
    cooldown_until: Option<Instant>,
    latency_ewma: Option<Duration>,
    throughput_ewma: Option<f64>,
    range_support: RangeSupport,
    last_error: Option<SourceErrorKind>,
}
```

### 12.3 选择策略

- 排除 cooldown 中的 source；
- 排除确认不支持 Range 或 identity 冲突的 source；
- retry 同一 block 时优先切换 source；
- 对近期成功和吞吐稳定的 source 增加权重；
- 所有 source 冷却时等待最早恢复时间；
- 所有 source 永久不可用时返回 `NoUsableSource`。

禁止继续使用无状态的均匀随机选择。

## 13. Retry 与错误分类

### 13.1 错误分类

```rust
enum TransferError {
    Cancelled,
    NoUsableSource,
    RetryBudgetExhausted,
    Source(SourceError),
    Sink(SinkError),
    Protocol(ProtocolError),
    Resume(ResumeError),
    InternalInvariant(InternalInvariantError),
}
```

`SourceError` 至少区分：

- connect timeout；
- read stall；
- DNS/TLS/proxy；
- connection reset；
- retryable HTTP status；
- permanent HTTP status；
- Range unsupported/ignored；
- `Content-Range` mismatch；
- truncated/oversized response；
- resource identity mismatch。

### 13.2 预算

首版必须同时支持：

- 单 source 连续失败阈值；
- 单 block attempt 上限；
- 单 block 总耗时上限；
- 整体无进展 deadline；
- 指数 backoff 与 jitter；
- blocker 的独立策略。

默认值需要通过真实网络测试确定，不在设计阶段直接沿用无限重试。超出预算后必须返回包含 range、source、attempt 和最后错误的结构化错误。

## 14. 断点续传与文件语义

### 14.1 第一版默认策略

```text
resume_offset = 现有文件长度
origin        = resume_offset
```

如果 `overwrite=True`，打开 sink 前将文件截断为零。

如果总大小已知：

- `resume_offset == expected_size`：直接完成；
- `resume_offset < expected_size`：从该位置开始；
- `resume_offset > expected_size`：返回 `ResumeError::ExistingFileTooLarge`，不得断言或静默重写。

因为只顺序 append，文件长度始终是连续 committed cursor，进程重启后直接从该长度继续。

### 14.2 续传信任边界

仅凭文件长度无法证明现有文件属于同一资源。首版由 yutto 保证临时路径与媒体候选身份稳定，并在 size probe 时检查总大小；通用 crate 应把这一信任边界写入 API 文档。

`resource_key` 用于本次传输内的 source 等价组校验；恢复已有文件时，yutto 仍需保证目标路径对应同一媒体候选。

## 15. Progress、事件与可观察性

### 15.1 Snapshot

```rust
pub struct TransferSnapshot {
    pub accepted_bytes: u64,
    pub network_bytes: u64,
    pub buffered_bytes: u64,
    pub committed_bytes: u64,
    pub expected_bytes: Option<u64>,
    pub active_attempts: usize,
    pub buffered_pages: usize,
    pub blocking_offset: u64,
    pub blocker_attempts: u32,
    pub useful_speed: f64,
    pub network_speed: f64,
}
```

定义：

- `accepted_bytes`：首次通过校验并被核心接受的唯一资源字节，包含 committed 和尚未连续提交的数据，不因 retry/hedge 重复累计；
- `network_bytes`：所有 attempt 实际收到的物理字节，包含 retry、hedge 和随后被丢弃的重复流量；
- `buffered_bytes`：当前 ordered window 中 Ready 的数据；
- `committed_bytes`：已经顺序写入 sink 的总字节；
- `blocking_offset`：当前最前缺口。

`accepted_bytes` 在总长度已知时不得超过 `expected_bytes`；`network_bytes` 可以因为 retry/hedge 超过资源大小。不得用单一 `written + buffered` 值同时代表网络进度、物理流量和可恢复进度。

### 15.2 Event

生命周期和诊断事件使用有界、可靠 channel：

```rust
enum TransferEvent {
    Started,
    SourceStateChanged,
    AttemptStarted,
    RetryScheduled,
    BlockSplit,
    BlockerChanged,
    Warning,
    Completed,
    Failed,
    Cancelled,
}
```

高频 progress 使用 `watch`/latest snapshot 语义，只保留最新值，不持久化每个采样点。Python UI 可以按当前 250 ms 周期读取 snapshot，避免 page 级 PyO3 回调。

## 16. 取消与资源清理

- 每个 transfer 拥有根 `CancellationToken`；worker 和 writer 使用 child token。
- Python task 被取消时必须触发 Rust token，而不是仅丢弃 Python future。
- coordinator 取消后停止发放 reservation，并取消所有 attempt。
- response stream、network permits、range permits 和 channel sender 必须在取消路径释放。
- writer 在取消时 flush 已经成功 append 的连续前缀，但不得强制提交缺口后的数据。
- 文件保留策略继续由 yutto 决定，以保护现有中断后续传语义。
- terminal error 必须等待子任务回收后再返回，避免后台请求继续写文件。

## 17. yutto/Python 接入

### 17.1 粗粒度 FFI

禁止下列接口：

```python
await native.push_page(offset, bytes)
```

推荐一次提交完整传输：

```python
transfer = await native.start_transfer(
    sources=[primary, *mirrors],
    target=path,
    expected_size=size,
    resource_key=resource_key,
    options=options,
)

while not transfer.done():
    snapshot = transfer.snapshot()
    emit_progress(snapshot)
    await asyncio.sleep(0.25)

await transfer.result()
```

Rust 内部拥有 reqwest stream、pager、scheduler、ring 和 writer，避免大数据和高频控制跨越 FFI。

### 17.2 Python 代码替换边界

第一阶段只替换：

- `Fetcher.download_file_with_offset()`；
- `slice_blocks()` 的执行职责；
- `AsyncFileBuffer`；
- 当前基于多个 block coroutine 的 `_run_download_lifecycle()` 路径；
- progress 对 buffer 内部结构的访问。

继续保留：

- `Fetcher.fetch_json()`；
- `Fetcher.fetch_text()`；
- `Fetcher.fetch_bin()`；
- B 站 extractor/API；
- URL 和 mirror 解析；
- Python 下载计划和 artifact/FFmpeg 流程。

普通 API 请求继续由现有 httpx 路径承担；媒体传输统一进入 Rust downloader，仓库中只保留一套分块调度、重试和文件重组实现。

### 17.3 Backend 切换

迁移期允许显式 backend：

```text
python
rust
```

Rust backend 失败时不得在同一次下载中静默 fallback 到 Python，否则会掩盖 Range、resume 和文件生命周期错误。可以在下一次独立执行中由用户或测试显式选择旧 backend。

### 17.4 打包

将 `yutto-core` 做成 `packages/yutto-core` 下的独立 native Python workspace package，类似当前 `biliass` 的 maturin/ABI3 打包方式，使顶层 yutto 在迁移期仍保持 Python package 结构。其 `rust/` 子目录同时承载发布到 crates.io 的 `haya`、`haya-http` 和 `yutto` Cargo workspace。

本阶段只发布这三个 Rust crate；`yutto-core` Python package 暂不发布。

发布前需要明确：

- macOS x86_64/arm64；
- Linux glibc/musl；
- Windows；
- CPython 3.11+ 和 free-threaded Python；
- TLS backend、证书根和 proxy 行为；
- wheel 大小及 Rust panic 策略。

不要在本迁移中顺便改变 TLS 校验默认值；该行为应单独决策和验证。

## 18. 测试设计

### 18.1 Core 确定性测试

使用 in-memory `RangeSource`、`CommitSink` 和可控 clock：

- 完全顺序；
- 完全逆序；
- 随机乱序；
- 重复 page；
- 缺失 page；
- source 返回部分交叠/错误长度；
- 最终短页；
- 总长度正好整 page；
- 空文件；
- 续传 origin 不对齐绝对 64 KiB；
- ring wrap-around；
- window 满后的反压；
- blocker 始终获得调度机会；
- 取消、sink error 和 channel close。

必须验证不变量：

```text
committed_offset 单调
输出字节严格等于源资源
内存不超过设计上限
同一 page 不会提交两次
失败时不会越过缺口
```

建议使用 property test 随机生成 source 延迟、失败、顺序和取消点。

### 18.2 Scheduler/Fault 测试

- 一个 source 永久失败，其他 source 正常；
- 一个 source 只在特定 Range 失败；
- blocker 慢、后方 block 快；
- 多个后方 block 同时完成，不能挤掉 blocker reservation；
- timeout 后 worker permit 被释放；
- backoff 不占 worker；
- circuit breaker/cooldown 生效；
- hedge 只产生一个获胜提交；
- block split 不产生重叠提交；
- 所有 source 失败后有限时间内 terminal failure。

### 18.3 本地 HTTP 集成测试

构造可注入故障的本地 Range server：

- 正常 `206`；
- 忽略 Range 返回 `200`；
- 错误 `Content-Range`；
- clean truncated EOF；
- 返回多余字节；
- 分段延迟/stall；
- connection reset；
- redirect；
- 不同 source 内容或长度冲突；
- HTTP/1.1 与 HTTP/2；
- proxy 和 SOCKS（按平台/CI 能力）；
- cancellation 后连接关闭。

### 18.4 File/Resume 测试

- 从零开始；
- 从任意非对齐文件长度继续；
- existing size 等于 expected size；
- existing size 大于 expected size；
- 中途 kill 后重启；
- sink write/flush/close 失败；
- overwrite；
- 未知总大小的顺序模式；
- 失败后仅保留连续前缀。

### 18.5 Python 契约测试

- 现有 CLI 文案和事件阶段顺序；
- video/audio 聚合进度；
- 取消后 buffer/file 关闭；
- 失败后临时媒体保留；
- mirror 过滤和 headers/cookies/proxy 传递；
- Python future 取消能停止 Rust 后台任务；
- JSON-RPC/server 的 task state 和 event replay 不因 progress 高频事件膨胀。

### 18.6 真实 smoke

使用本地 checkout 而非全局 yutto：

- 单视频；
- 音视频同时下载；
- 中断后再次运行；
- 主 URL 禁用/失效、mirror 接管；
- 人为限速或断网恢复；
- 最终 FFmpeg 合并和 artifact 清单。

真实网络结果与本地确定性测试分别记录，不能用一次真实成功替代故障测试。

## 19. 性能与资源预算

首版性能目标不是追求极限吞吐，而是：

- 吞吐不低于当前 Python downloader 的可重复基线；
- 坏块情况下仍有可解释进展和有限恢复时间；
- 内存随 window 有界，不随文件大小增长；
- task 数量与 worker/window 成正比，不与文件 block 总数成正比；
- Python/Rust FFI 不承载媒体数据页。

需要记录：

- 总吞吐和 committed 吞吐；
- CPU；
- RSS 峰值；
- 每秒 page/event 数；
- Range 请求数与重试流量；
- blocker 恢复时间；
- 不同 page/block/window 参数的影响。

文件写入使用单 writer，避免同一文件上的并发 seek/write，并保持连续提交语义。

## 20. 分阶段实施

### Phase 0：锁定契约与基线

- 为当前 Python downloader 补充 Range、resume、取消和最终长度测试；
- 建立本地 fault Range server；
- 记录一组 CLI/事件/真实下载基线；
- 确认 yutto 外层提供 source 等价组和 `resource_key` 的方式。

交付物：测试和设计，不改默认下载路径。

### Phase 1：`haya` 核心

- 实现模型、coordinator、有限 attempt 结果、source pool；
- 实现 fixed page pager、window reservation 和 ordered buffer；
- 使用 in-memory source/sink 完成确定性和 property tests；
- 暂不接 reqwest/PyO3。

交付物：一个可独立测试的通用核心 crate。

### Phase 2：`haya-http` 与默认文件 sink

- 在 `haya-http` 接入 reqwest；
- 完成 Range/响应验证；
- 在 `haya::file` 完成顺序文件 sink 与长度续传；
- 使用本地 fault server 做端到端测试；
- 提供小型 Rust example/CLI 便于手动验证。

交付物：不依赖 yutto 的通用多源文件下载能力。

### Phase 3：`yutto-core` 实验接入

- 建立 `packages/yutto-core` Cargo workspace 和 Python package；
- 在 `yutto` crate 建立 PyO3 粗粒度 `TransferHandle`；
- 映射 DownloadPlan、events、snapshot 和 cancellation；
- 增加显式 `rust` backend；
- 保留 Python backend 作为独立对照；
- 运行相关格式、lint、pytest、Rust fmt/clippy/test 和真实 smoke。

交付物：可选择但非默认的 Rust 下载路径。

### Phase 4：切换默认并删除 Python 下载核心

- 达到验收条件后将 Rust backend 设为默认；
- 删除 `Fetcher.download_file_with_offset()`；
- 删除 `AsyncFileBuffer` 和旧 block task 生命周期；
- 保留 Python presentation/planning adapter；
- 更新文档和 wheel CI。

交付物：仓库中只剩一套媒体下载核心。

### Phase 5：高级控制策略

- source EWMA；
- blocker hedge；
- 自适应 block/window；
- 更完整的 circuit breaker；
- 跨 transfer 全局公平/带宽限制。

这些策略应基于 Phase 4 的观测数据逐项加入，避免在核心正确性未稳定时一次实现全部自适应逻辑。

## 21. 验收条件

在 Rust backend 成为默认并删除 Python downloader 前，必须满足：

### 正确性

- 已知总大小的成功传输严格满足最终文件长度和内容；
- Range 被忽略、截断或越界时不会静默成功；
- 任意乱序和 retry 下 committed cursor 单调；
- 中断后从文件长度继续，最终内容正确；
- 最后一页、空文件和整 page 文件均正确；
- 取消和错误路径无后台写入泄漏。

### 调度与控制

- 单个永久坏 source 不阻止健康 mirror 完成下载；
- 单个坏 block 不永久占用所有 worker；
- 所有 source 失败时在预算内 terminal failure；
- window 满时内存保持有界；
- blocker 不会被较远 block 饿死；
- backoff 不占 network worker。

### 兼容性

- 单次 CLI、音视频下载、续传、mirror fallback 和 FFmpeg 行为保持；
- 现有用户可见中文阶段文案和关键事件顺序保持；
- server/JSON-RPC 取消与最终状态保持；
- headers、cookies、proxy 和镜像过滤语义有测试覆盖；
- wheel 覆盖当前支持平台和 Python 版本。

### 工程质量

- Rust fmt、Clippy `-D warnings`、单元/集成/property tests 通过；
- Python fmt、lint、相关 pytest 通过；
- 无 `uv.lock` 或发布配置的无关改动；
- 真实 smoke 使用本地构建产物完成；
- 文档明确错误预算、source 等价信任边界和 resume 限制。

## 22. 风险与对策

### Source 实际不等价

风险：不同 CDN URL 长度相同但内容不同，造成混合文件。

对策：调用方声明等价组；校验 size/Range；支持 validator；发现冲突立即隔离 source；真实 yutto source identity 建立契约测试。

### Async FFI 生命周期

风险：Python future 取消后 Rust task 继续运行，或 Tokio runtime 关闭顺序错误。

对策：粗粒度 handle、显式 cancellation token、终止前回收子任务、专门的 Python async integration tests。

### Native wheel 复杂度

风险：Rust TLS、代理、ABI3/free-threaded 和多平台 wheel 增加发布成本。

对策：复用 biliass 的构建经验，但为 async/network extension 单独建立矩阵；在默认切换前完成平台 smoke。

### 过早公共 API 稳定

风险：`haya` 和 `haya-http` 在第一版就被 semver 约束。

对策：先在 workspace 内孵化并标记 experimental；只公开 source/sink/spec/event 等稳定边界；内部 scheduler/ring 模块暂不承诺兼容。

## 23. 待决策项

实现前需要明确：

1. 公共 crate 的许可证；从 GPL 仓库抽取代码时不得默认改变既有版权条件。
2. yutto 的 `resource_key` 由哪些媒体字段组成，以及路径是否足以保证同一资源。
3. `TrustedGroupWithSizeCheck` 是否足以作为默认 source 等价策略。
4. page/block/window 的默认值是否保留 64 KiB / 512 KiB / 约 8 MiB window。
5. attempt、block 和整体无进展预算的默认值。
6. 是否需要独立 recovery permit，还是 blocker 绝对优先已经足够。

这些决策应在对应 phase 开始前逐项确认，不能由局部实现顺便改变现有用户语义。
