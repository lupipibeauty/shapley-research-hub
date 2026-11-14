# IDEA-03-2 状态更新：联合价值与共享编译

- 历史 G1：`VERIFIED_EQUIVALENT_TO_GR`。
- k=2 E0：`VERIFIED_INTERACTION`，但 GC 为满联盟 unanimity，`NOT_GENERAL_BENCHMARK`。
- E1 三配对：SQL/结构核验完成，`PARTIAL_CONTROL`；尚非跨省共享。
- B2 共享 ROADD：`VERIFIED_EXACT_SOLVER_N_LE_16`，未显示速度优势。
- B3 官方 LExaShap 分量缓存：精确；冷 solve 有改善，冷端到端优势很小，warm 属摊销场景。
- TPC-H SF0.1：自然/供应商共享结构存在性已核验；未做性能排名，未运行 SF1。
- 两个超预算运行均保留为 `RESOURCE_LIMIT`，没有删除或改写。

下一门槛：N≤16 真正跨省共享、多个 GC 中间非零状态、固定状态/证明数的正交配对；通过后才适配多输出成熟知识编译并做冷端到端比较。
