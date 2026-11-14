# 机制成本比较

固定总多项式次数64，child数取2、4、8、16、32。主要指标为卷积系数乘加、反卷积更新及中间存储；单次墙钟时间仅作辅助。

## 操作量

相对当前反卷积的主要cell operations：

| child数 | Prefix/suffix | Product tree |
|---:|---:|---:|
|2|0.67×|0.33×|
|4|0.89×|0.78×|
|8|1.31×|1.26×|
|16|2.01×|1.70×|
|32|3.06×|2.03×|

原失败点 `r=12,N=60`：当前6078、prefix/suffix 10152（1.67×）、product tree 9441（1.55×）。替代方法没有数量级开销，product tree始终优于显式prefix/suffix。

## 存储

固定次数64时，product tree的估算峰值工作cells由197增至773，当前方法由98增至128；在r=32时约为当前6.04倍，但绝对量为773个系数。prefix/suffix在r=32达到2241 cells，约17.5倍，因此不是首选替代。

原失败点：当前峰值117、prefix/suffix 862、product tree 543；三种方法的返回message总量均为672 cells。若按作者方式逐child立刻消费message，当前方法工作内存最低；product tree需要局部树缓存，但没有复制或展开d-tree。

## 墙钟时间

辅助单次计时中，SciPy反卷积路径反而显著慢于两个纯NumPy卷积替代；该结果受函数调用与库实现影响，不作为复杂度结论。它至少说明冻结规模下没有观察到实际运行时间惩罚。

## 判断

显式 sibling message 的稳定替代存在常数/对数因子的操作与缓存增加，但没有出现数量级时间代价，也不改变作者总体多项式时间边界。标准算术电路reverse-mode还可直接通过乘积树门传播adjoint，避免必须物化全部`Q_-i`；因此本实验的缓存上界不是理论必需成本。

完整数据见 `results/operation_counts.csv` 与 `storage_metrics.csv`。
