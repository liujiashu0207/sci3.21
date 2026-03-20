# Path Comparison Visual Audit — exp_v1

| Fig | Map | TaskIdx | Start | Goal | OptLen | Algo | PL | TC | CF |
|-----|-----|---------|-------|------|--------|------|----|----|----| 
| short_arena2_40 | arena2 | 40 | (49, 129) | (36, 138) | 16.7 | A*(Euc) | 16.73 | 6 | ✅ |
| short_arena2_40 | arena2 | 40 | (49, 129) | (36, 138) | 16.7 | A*(Oct) | 16.73 | 1 | ✅ |
| short_arena2_40 | arena2 | 40 | (49, 129) | (36, 138) | 16.7 | WA*(1.2) | 16.73 | 1 | ✅ |
| short_arena2_40 | arena2 | 40 | (49, 129) | (36, 138) | 16.7 | Ours | 15.81 | 0 | ✅ |
| short_arena2_40 | arena2 | 40 | (49, 129) | (36, 138) | 16.7 | NoAdapt | 15.81 | 0 | ✅ |
| short_arena2_40 | arena2 | 40 | (49, 129) | (36, 138) | 16.7 | NoSmooth | 16.73 | 1 | ✅ |
| short_Berlin_0_256_45 | Berlin_0_256 | 45 | (184, 232) | (189, 246) | 16.1 | A*(Euc) | 16.07 | 5 | ✅ |
| short_Berlin_0_256_45 | Berlin_0_256 | 45 | (184, 232) | (189, 246) | 16.1 | A*(Oct) | 16.07 | 3 | ✅ |
| short_Berlin_0_256_45 | Berlin_0_256 | 45 | (184, 232) | (189, 246) | 16.1 | WA*(1.2) | 16.07 | 1 | ✅ |
| short_Berlin_0_256_45 | Berlin_0_256 | 45 | (184, 232) | (189, 246) | 16.1 | Ours | 14.87 | 0 | ✅ |
| short_Berlin_0_256_45 | Berlin_0_256 | 45 | (184, 232) | (189, 246) | 16.1 | NoAdapt | 14.87 | 0 | ✅ |
| short_Berlin_0_256_45 | Berlin_0_256 | 45 | (184, 232) | (189, 246) | 16.1 | NoSmooth | 16.07 | 1 | ✅ |
| short_blastedlands_48 | blastedlands | 48 | (82, 289) | (78, 273) | 17.7 | A*(Euc) | 17.66 | 4 | ✅ |
| short_blastedlands_48 | blastedlands | 48 | (82, 289) | (78, 273) | 17.7 | A*(Oct) | 17.66 | 3 | ✅ |
| short_blastedlands_48 | blastedlands | 48 | (82, 289) | (78, 273) | 17.7 | WA*(1.2) | 17.66 | 1 | ✅ |
| short_blastedlands_48 | blastedlands | 48 | (82, 289) | (78, 273) | 17.7 | Ours | 16.49 | 0 | ✅ |
| short_blastedlands_48 | blastedlands | 48 | (82, 289) | (78, 273) | 17.7 | NoAdapt | 16.49 | 0 | ✅ |
| short_blastedlands_48 | blastedlands | 48 | (82, 289) | (78, 273) | 17.7 | NoSmooth | 17.66 | 1 | ✅ |
| long_brc000d_2 | brc000d | 2 | (138, 62) | (14, 36) | 338.3 | A*(Euc) | 338.29 | 59 | ✅ |
| long_brc000d_2 | brc000d | 2 | (138, 62) | (14, 36) | 338.3 | A*(Oct) | 338.29 | 43 | ✅ |
| long_brc000d_2 | brc000d | 2 | (138, 62) | (14, 36) | 338.3 | WA*(1.2) | 343.93 | 40 | ✅ |
| long_brc000d_2 | brc000d | 2 | (138, 62) | (14, 36) | 338.3 | Ours | 330.75 | 18 | ✅ |
| long_brc000d_2 | brc000d | 2 | (138, 62) | (14, 36) | 338.3 | NoAdapt | 324.73 | 15 | ✅ |
| long_brc000d_2 | brc000d | 2 | (138, 62) | (14, 36) | 338.3 | NoSmooth | 356.72 | 82 | ✅ |
| long_Berlin_0_256_1 | Berlin_0_256 | 1 | (12, 5) | (240, 253) | 371.1 | A*(Euc) | 371.14 | 86 | ✅ |
| long_Berlin_0_256_1 | Berlin_0_256 | 1 | (12, 5) | (240, 253) | 371.1 | A*(Oct) | 371.14 | 40 | ✅ |
| long_Berlin_0_256_1 | Berlin_0_256 | 1 | (12, 5) | (240, 253) | 371.1 | WA*(1.2) | 409.19 | 73 | ✅ |
| long_Berlin_0_256_1 | Berlin_0_256 | 1 | (12, 5) | (240, 253) | 371.1 | Ours | 352.48 | 5 | ✅ |
| long_Berlin_0_256_1 | Berlin_0_256 | 1 | (12, 5) | (240, 253) | 371.1 | NoAdapt | 352.07 | 4 | ✅ |
| long_Berlin_0_256_1 | Berlin_0_256 | 1 | (12, 5) | (240, 253) | 371.1 | NoSmooth | 390.07 | 71 | ✅ |
| long_battleground_1 | battleground | 1 | (104, 60) | (443, 415) | 531.7 | A*(Euc) | 531.74 | 50 | ✅ |
| long_battleground_1 | battleground | 1 | (104, 60) | (443, 415) | 531.7 | A*(Oct) | 531.74 | 44 | ✅ |
| long_battleground_1 | battleground | 1 | (104, 60) | (443, 415) | 531.7 | WA*(1.2) | 537.54 | 37 | ✅ |
| long_battleground_1 | battleground | 1 | (104, 60) | (443, 415) | 531.7 | Ours | 513.49 | 17 | ✅ |
| long_battleground_1 | battleground | 1 | (104, 60) | (443, 415) | 531.7 | NoAdapt | 508.22 | 11 | ✅ |
| long_battleground_1 | battleground | 1 | (104, 60) | (443, 415) | 531.7 | NoSmooth | 574.18 | 93 | ✅ |

## Legality: ALL PASS ✅
Figures generated: 6

## Figure-Data Consistency: PASS ✅
All paths drawn from real algorithm output. β=0.3. No manual editing.

## Caption Template
> 图X 不同算法在同一场景下的路径对比。黑色区域为障碍物，绿色圆点为起点，红色星标为终点。改进算法(红色)在保持路径合法性的前提下，拐点更少、路径更平滑。所有路径均经过逐段碰撞检测验证。该图对应任务来自 strict scen。