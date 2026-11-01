---
title: 跑 200 ns 之前，我在 GROMACS 上踩过的七个坑
date: 2026-10-05
tags: 科研随笔, GROMACS
summary: 环境、拓扑、力场、压力耦合……这些坑不会写进论文的方法部分，但每一个都能让你白跑三天。
---

每次组里来新人，我都要重讲一遍这些东西。索性写下来，以后直接甩链接。

## 一、先确认你看的是哪份 `mdrun`

这是最蠢也最常见的一个。装完 GROMACS 之后 `which gmx` 和 `gmx --version` 出来的可能不是同一个东西——conda 环境里一份、`/usr/local/bin` 一份、`module load` 又一份。

跑之前先固定住：

```bash
$ which gmx
$ gmx --version | head -3
$ echo $GMXBIN
```

如果同一台机器上多人共用，把版本号写进你的提交脚本注释里。半年后你会感谢自己。

> 我曾经因为集群默认模块被管理员升级，同一个 `tpr` 在两次提交里跑出了不同的能量漂移，排查了两天。

## 二、`pdb2gmx` 的 `-ignh` 不是可选项

晶体结构里的氢原子位置大多来自建模，力场参数化时并不认这些坐标。加 `-ignh` 让 GROMACS 自己重建：

```bash
gmx pdb2gmx -f input.pdb -o processed.gro -water tip3p -ff amber99sb-ildn -ignh
```

不加的后果是：要么直接报错说残基名不认识，要么更糟——它默默接受了，然后你在 50 ns 处看到一个莫名其妙的氢键网络。

## 三、盒子边界离蛋白太近

`editconf -bt cubic -d 1.0` 里的 `d` 是**蛋白到盒子边的最小距离**，不是盒子边长。对球形蛋白 1.0 nm 够用，但对 elongated 的或者带长 linker 的构象，旋转一下就会撞到周期性边界。

我的习惯是：

| 体系 | `-d` | 备注 |
| --- | --- | --- |
| 球状单体（< 60 kDa） | 1.0 nm | 常规 |
| 带长 linker / 环化肽 | 1.2–1.4 nm | 防止自相互作用 |
| 膜蛋白 | 1.0 nm（z 单独加） | 配合 `-c -box` |

跑完 `gmx editconf` 之后一定打开 `gmx view` 或者 PyMOL 转一圈，看看蛋白在盒子里是不是真的居中。

## 四、离子中和之后忘了检查净电荷

`genion` 会报 `System has net charge`，但很多人加了 `-neutral` 就不再管。问题是生理盐浓度（0.15 M）和「刚好中和」是两回事。

```bash
gmx genion -s ions.tpr -o solv_ions.gro -p topol.top \
  -pname NA -nname CL -neutral -conc 0.15
```

加完之后重新数一遍：

```bash
gmx grompp -f ions.mdp -c solv_ions.gro -p topol.top -o check.tpr
# 看输出里的 System total charge
```

## 五、能量最小化「收敛」了但其实没收敛

`emtol = 1000` 是默认值，对很多体系太松。更要命的是：`Fmax` 停在 990 附近不动，看起来收敛了，实际上是一个原子卡在初始位置。

两个信号说明有问题：

- `Potential Energy` 在最后几百步几乎不变，但 `Maximum force` 一直贴着 `emtol` 上下抖；
- 收敛步数恰好等于 `nsteps`。

把 `emtol` 降到 `100–200`，`nsteps` 给到 `50000`，多花十分钟，省掉后面 200 ns 的结构崩坏。

## 六、`tcoupl` 和 `pcoupl` 的时间常数

NPT 平衡阶段，`tau_t = 0.1` 和 `tau_p = 5.0` 是常见配置，但如果你从 NVT 直接跳到生产，中间缺少足够的 NPT 平衡，密度会一路往下漂。

我的顺序是：

1. NVT 100 ps（`tau_t = 0.1`）
2. NPT 500 ps（`tau_p = 2.0`，位置限制）
3. NPT 500 ps（去掉位置限制，`tau_p = 5.0`）
4. 生产

第 2 步保留 `-DPOSRES` 非常关键，否则蛋白侧链会在盒子还没稳定时就开始乱动。

## 七、轨迹没做 PBC 处理

跑完 200 ns 打开轨迹，发现蛋白「散架」了——其实只是跨过了周期性边界。别慌，也别重跑：

```bash
gmx trjconv -s md.tpr -f md.xtc -o center.xtc -pbc mol -center
# 选 Protein 做 center，选 System 做 output
gmx trjconv -s md.tpr -f center.xtc -o fit.xtc -fit rot+trans
```

`-pbc mol` 之后再 `-fit rot+trans`，两个步骤缺一不可。前者保证分子完整，后者消除整体转动。

## 最后

这七条没有一条出现在论文的方法部分，但它们决定了你那 200 ns 到底是在产生数据，还是在产生垃圾。

我的原则很简单：**报错了先读日志，跑完了先看轨迹**。前者能省一天，后者能省一周。
