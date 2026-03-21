# 残差驱动自适应加权A*路径规划算法

刘家树

南方科技大学 机械与能源工程系，广东 深圳 518055

**摘　要：** 针对A\*算法在复杂栅格环境中搜索效率受限、路径质量不佳的问题，提出了一种残差驱动自适应加权A\*路径规划算法（Residual-Driven Adaptive Weighted A\*，RDA\*）。该算法以Octile距离作为启发函数，引入局部障碍物密度概念，通过积分图实现O(1)复杂度的逐节点障碍率查询，设计自适应权重函数α(n)=1+β(1−ρ_local(n))，使搜索在空旷区域加速探索、在密集区域保守寻优；同时采用两阶段路径平滑策略（视线简化与角点插值），在保证路径合法性的前提下显著缩短路径长度并减少转弯次数。在MovingAI公开基准数据集的15张地图上，以20条任务×7种算法进行对比实验，结果表明：与A\*(欧氏)相比，RDA\*的路径长度缩短3.6%（p<0.001），转弯次数减少76.4%（p<0.001），扩展节点减少61.5%（p<0.001），总运行时间缩短31.9%；消融实验验证了自适应权重与路径平滑两个模块各自的独立贡献。补充实验在长路径场景下（平均最优路径≈626步）进一步验证了算法的鲁棒性。

**关键词：** 路径规划；A\*算法；自适应权重；障碍物密度；路径平滑；栅格地图

**文献标志码：** A　**中图分类号：** TP242　**doi：** 10.3778/j.issn.1002-8331.XXXX-XXXX

---

## Residual-Driven Adaptive Weighted A\* Path Planning Algorithm

LIU Jiashu

Department of Mechanical and Energy Engineering, Southern University of Science and Technology, Shenzhen, Guangdong 518055, China

**Abstract:** To address the limited search efficiency and suboptimal path quality of the A\* algorithm in complex grid environments, a Residual-Driven Adaptive Weighted A\* (RDA\*) path planning algorithm is proposed. The algorithm employs octile distance as the heuristic function and introduces a local obstacle density concept, achieving O(1) per-node obstacle ratio queries via integral images. An adaptive weight function α(n)=1+β(1−ρ_local(n)) is designed to accelerate exploration in open areas while maintaining conservative search in dense regions. A two-stage path smoothing strategy (line-of-sight simplification and corner interpolation) significantly reduces path length and turn count while ensuring path legality. Experiments on 15 maps from the MovingAI benchmark dataset with 20 tasks × 7 algorithms show that compared with A\*(Euclidean), RDA\* reduces path length by 3.6% (p<0.001), turn count by 76.4% (p<0.001), expanded nodes by 61.5% (p<0.001), and total runtime by 31.9%. Ablation studies confirm the independent contributions of the adaptive weight and path smoothing modules. Supplementary experiments on long-path scenarios (average optimal path ≈ 626 steps) further validate the algorithm's robustness.

**Keywords:** path planning; A\* algorithm; adaptive weight; obstacle density; path smoothing; grid map

---

## 0　引言

路径规划是实现移动机器人自主导航的关键技术之一，其目标是在已知或部分已知的环境中规划一条从起点到目标点的最优路径，同时避开障碍物并满足路径长度、转弯次数、搜索效率等多项性能指标[1]。随着机器人技术在物流仓储[2]、巡检作业[3]、游戏AI[4]等领域的广泛应用，路径规划算法的性能需求日益提高。

A\*算法作为一种经典的启发式搜索算法[5]，通过代价函数f(n)=g(n)+h(n)引导搜索方向，兼顾了Dijkstra算法的最优性和贪心搜索的高效性，是目前全局路径规划中应用最为广泛的算法之一。然而，传统A\*算法在复杂栅格环境中仍存在以下不足：（1）搜索效率受限，在大规模地图中扩展节点过多，导致运行时间较长；（2）规划路径包含大量冗余转折点，不利于机器人平稳运行；（3）启发函数权重固定，无法根据局部环境特征自适应调整搜索策略。

针对上述问题，国内外学者进行了大量研究。在启发函数权重优化方面，Algfoor等[6]提出三种加权启发式搜索技术，分别基于迭代次数、起终点距离和行进代价设计权重，并应用于A\*、双向A\*和JPS算法，在MovingAI基准数据集上验证了加权方法的加速效果，但其权重为预设常数，在搜索过程中保持不变，且加权后路径代价显著增加。冯志乾等[7]将量化的障碍物信息作为启发函数的自适应调节权重，提高了算法搜索效率，但其权重基于起点到终点矩形区域的全局障碍率，在搜索过程中为固定值，无法根据局部环境动态调整。高建京等[8]引入启发函数动态加权方法，根据当前节点到目标点的距离比例调整权重，减少了寻路时间，但该方法的权重仅依赖启发值本身的衰减，未利用环境结构信息。毕竟等[9]引入障碍率概念设计评价函数f(n)=g(n)+(1−lnP)×h(n)，但其障碍率基于起点与目标点间的全局统计，在搜索过程中为固定值。

在路径平滑与优化方面，赵江等[10]借助几何方法对A\*算法规划的路径进行优化，缩短了运输路径长度和减少了转折次数，但路径仍存在不平滑转折点。冯泽鹏等[11]提出三角形边界与三邻域搜索相结合的搜索机制，引入三次B样条曲线平滑处理，在搜索时间和遍历节点方面取得显著改进，但未考虑局部障碍物密度对搜索策略的影响。

在搜索策略优化方面，赵晓等[12]采用跳点搜索算法改进A\*，搜索节点明显减少，但无法实现动态避障。吴鹏等[13]提出双向搜索及自适应权重算法，减少了路径规划时间，但路径平滑性不足。

综上所述，现有改进A\*算法在启发函数权重设计方面普遍采用全局固定或仅基于距离衰减的策略，未能充分利用局部环境结构信息实现逐节点的搜索策略自适应调整。此外，多数研究采用自设计地图进行验证，缺乏在公开基准数据集上的系统性对比和统计检验。

针对上述不足，本文提出残差驱动自适应加权A\*路径规划算法（RDA\*），主要贡献如下：

（1）提出基于局部障碍物密度的逐节点自适应权重机制。通过积分图实现O(1)复杂度的局部障碍率查询，设计权重函数α(n)=1+β(1−ρ_local(n))，使算法在空旷区域增大启发权重加速搜索，在障碍物密集区域降低权重保守寻优，实现搜索效率与路径质量的自适应平衡。

（2）设计两阶段路径平滑策略。第一阶段基于严格supercover视线检测的路径简化，第二阶段基于角点加权插值的路径平滑，在保证路径合法性的前提下显著缩短路径长度并减少转弯次数。

（3）在MovingAI公开基准数据集的15张地图上，采用7种算法（含2组消融）×20条任务的大规模实验设计，结合Wilcoxon符号秩检验和BH-FDR校正进行统计分析，系统验证了算法的有效性和鲁棒性。

