---
title: 用 ProteinMPNN 做环化设计时，三个容易被忽略的细节
date: 2026-08-30
tags: 方法, 蛋白设计, 论文阅读
summary: tie 的到底是哪几个残基、链 ID 怎么传、采样温度选多少——这三件事决定了你拿到的是设计还是噪声。
---

ProteinMPNN 用起来只有一行命令，但真正决定结果质量的，是三个几乎没人细讲的地方。

## 一、`--tied_chains` 绑的是对称，不是你想的那个

环化设计里经常有人想「让 linker 两端保持一致」，于是去传 `--tied_chains`。这个参数的本意是**同源多聚体的对称约束**：它假设两条链的序列应当相同，并且在解码时共享概率。

对环化体系，这通常不是你想要的。你想要的往往是「linker 区允许更高柔性、其余区域保持原序列」，那应该用 `--fixed_positions` 加上一个位置列表：

```bash
python protein_mpnn_run.py \
  --pdb_path scaffold.pdb \
  --fixed_positions fixed.jsonl \
  --num_seq_per_target 100 \
  --sampling_temp "0.1" \
  --out_folder out/
```

`fixed.jsonl` 里每条记录对应一个结构：

```json
{"scaffold.pdb": ["1", "2", "3", "A45", "A46", "A47"]}
```

链 ID 必须带上。这是第二件事。

## 二、链 ID 不写清楚，它就在猜

ProteinMPNN 内部对残基的索引方式是 `<chain_id><resnum>`。如果你的 PDB 里链 ID 是空的（很多从建模工具导出的结构都是），它会把整条蛋白当成一条链，编号从 1 开始。

于是你写的 `A45` 根本匹配不上，`fixed_positions` 静默失效——**不报错，只是全部位置都被重新设计了**。

跑之前先查：

```python
from Bio.PDB import PDBParser
s = PDBParser(QUIET=True).get_structure("x", "scaffold.pdb")
for chain in s[0]:
    res = [r for r in chain if r.id[0] == " "]
    print(chain.id or "<empty>", len(res), res[0].id[1], res[-1].id[1])
```

如果输出是 `<empty>`，先用 `pdb_selchain` 或者 PyMOL 补上链 ID，再做后续步骤。

## 三、`sampling_temp` 不是「多样性旋钮」

默认 `0.1`。很多人以为调高就是「更有多样性」，于是直接拉到 `0.5`，然后抱怨序列没法表达。

实际上在环化体系里，温度升高最先崩掉的是 **linker 与核心的界面**——那部分本来就没多少进化约束，高温下会采样出大量疏水暴露的构象。

我的经验区间：

| 场景 | `sampling_temp` | 说明 |
| --- | --- | --- |
| 保守重设计（保核心） | 0.05–0.1 | 首选 |
| linker 区单独设计 | 0.1–0.2 | 配合 `fixed_positions` |
| 探索新序列空间 | 0.2–0.3 | 必须配合严格筛选 |
| > 0.3 | 不建议 | 表达成功率断崖 |

另外 `--num_seq_per_target` 给 100 就够了。给 1000 的收益远小于多跑一个骨架。

## 一个组合起来的小例子

真实场景里这三件事是叠在一起的。我通常这么做：

```bash
# 1. 先固定核心与活性位点，只放开 linker 两侧各 3 个残基
python protein_mpnn_run.py \
  --pdb_path scaffold_chainA.pdb \
  --fixed_positions fixed_core.jsonl \
  --sampling_temp "0.15" \
  --num_seq_per_target 64 \
  --batch_size 1 \
  --out_folder mpnn_out/

# 2. 用 pLDDT + 界面接触数粗筛
python scripts/filter_mpnn.py --in mpnn_out/ --min_contacts 24 --min_plddt 0.82
```

第 2 步的阈值同样要按体系标定。`min_contacts` 我一般取「原结构中 linker 界面接触数的 70%」——低于这个值，链基本贴不回去。

## 小结

这三点的共同点是：**它们都不会报错**。工具安静地跑完，给你一堆看起来合理的序列，然后你在第 6 周发现一条都表达不出来。

所以在把 MPNN 接进流水线之前，我会先做一次「对照」：拿原始序列当输入，看它能不能在设计模式下把原始序列重新采样出来。如果重采样结果的 identity 低于 0.6，说明输入的结构或索引有问题。

这个检查只要五分钟。
