# 组合 06：DYNAMIC_AND_TASK（B1 + B2 + D2）

## 一句话问题

当买方任务和数据库版本同时变化时，哪些贡献更新可精确复用，哪些只能近似？

## 依赖与删除检验

- 同时变化会形成二维维护问题，但若任务和版本变化独立，可能只是两套动态算法的笛卡尔积。
- 去掉 B1/B2 仍有动态数据 Shapley；去掉 D2 仍有多任务复用。

## 最强竞争

Yang 2026 D-Shap、Xia 2025 dynamic data Shapley、F-IVM/LMFAO。

## 最大风险

现有 D-Shap 已以 player-by-task matrix 直接覆盖大部分概念；本项目仅换为 SQL utility。

## 当前判断

`NEXT_ROUND_MEDIUM_LOW`。先完成同一目标的精确/近似边界表，不急于实验。

