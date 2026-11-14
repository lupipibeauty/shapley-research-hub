# IDEA-03 阶段2A：成熟来源编译与同目标精确求解

状态：`STAGE2A_COMPLETED / STAGE2B_NOT_STARTED`。

本目录只使用阶段1冻结的 `STRICT_CONCENTRATED` 与 `STRICT_BALANCED`。算法输入来自16名物理玩家和6个三事实 JOIN 见证；65,536联盟价值表及历史 Harsanyi 结果没有进入编译或求解输入，只在求解结束后作独立正确性核验。

规范运行 `STAGE2A_20261113_CANONICAL` 已验证：官方 LExaShap 可直接编译正 DNF 来源；通过28个 COUNT/SUM 坐标的线性归约和7个 ratio/省际 gap 的6见证有限状态 Möbius 分解，可精确恢复冻结 `v_fid`、`v_gap` 的全部16名玩家 Shapley，最大绝对误差 `1.39e-16`。

主要边界：作者 `DNFCircuit` 不接受外部变量顺序；当前只支持完整相同 DNF 的跨输出缓存，不支持部分公共子表达式或共同数值状态复用。因此固定顺序 OBDD/SDD/VE 比较记为 `INPUT_UNSUPPORTED_AUTHOR_INTERFACE`，不以本地自制通用编译器替代。

入口：

- `00_EVIDENCE_REUSE_AUDIT.md`
- `01_ALGORITHM_COVERAGE_GATE.md`
- `02_SOURCE_AND_NUMERIC_STATE_AUDIT.md`
- `03_EXPERIMENT_A_MATURE_COMPILATION.md`
- `04_STAGE2A_DECISION.md`
- `RUN_REGISTRY.md`

