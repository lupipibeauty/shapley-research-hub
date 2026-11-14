# 阶段2A首次启动失败记录

- 状态：`FAILED_ADAPTER_PREFLIGHT`，不属于算法实验结果。
- 现象：官方 `DNFCircuitNode` 在构造时读取类级 `DNFCircuit.timeout`；最小适配器为了分别测量编译与 backward 求解，绕过了 `DNFCircuit.__init__`，遗漏了作者构造器原本设置的 `timeout=3600` 与 `start_time`。
- 原始错误：`TimeoutError: timeout exceeded`，发生在第一个来源电路构造前。
- 修正：在调用作者 `DNFCircuitNode` 前显式恢复作者构造器的原有超时与起始时间设置；未修改作者源码、输入、算法或实验参数。
- 研究含义：无。不得记为 `RESOURCE_LIMIT`、算法失败或编译性能数据。
