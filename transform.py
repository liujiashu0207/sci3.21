#!/usr/bin/env python3
"""
Convert ROS map (.pgm + .yaml) to MovingAI format (.map + .scen)
Usage: 
  python ros2movingai.py map.pgm map.yaml output_prefix [--threshold 50] [--scen SCEN_FILE] [--num_scenes 10] [--seed 42]
  or provide explicit scenes via --scen_file scenes.txt
"""

import sys
import yaml
import numpy as np
from PIL import Image
import argparse
import random
import os
from typing import List, Tuple, Optional

def ros_to_movingai(pgm_path, yaml_path, output_map_path, threshold=50):
    """将ROS地图转换为MovingAI .map文件"""
    # 读取YAML
    with open(yaml_path, 'r') as f:
        map_meta = yaml.safe_load(f)
    
    resolution = map_meta.get('resolution', 0.05)
    occupied_thresh = map_meta.get('occupied_thresh', 0.65)
    negate = map_meta.get('negate', 0)
    
    # 读取PGM
    img = Image.open(pgm_path)
    img_array = np.array(img)
    if len(img_array.shape) == 3:
        img_gray = img_array[:, :, 0]
    else:
        img_gray = img_array
    
    height, width = img_gray.shape
    
    # 转换为二值地图
    if img_gray.max() <= 1.0:
        occupancy = (img_gray >= occupied_thresh).astype(np.uint8)
    elif img_gray.max() <= 255:
        occupancy = np.zeros_like(img_gray, dtype=np.uint8)
        occupancy[img_gray >= threshold] = 1
        if negate:
            occupancy = 1 - occupancy
    else:
        raise ValueError(f"Unknown pixel range: {img_gray.min()}-{img_gray.max()}")
    
    # 写入.map文件
    with open(output_map_path, 'w') as f:
        f.write(f"# Converted from {pgm_path}\n")
        f.write(f"# resolution: {resolution}\n\n")
        for row in range(height):
            line = ' '.join(str(occupancy[row, col]) for col in range(width))
            f.write(line + '\n')
    
    print(f"Map saved: {output_map_path} ({width}x{height})")
    return width, height, occupancy

def generate_random_scenes(occupancy: np.ndarray, num_scenes: int, seed: int = None,
                          max_attempts: int = 1000) -> List[Tuple[int, int, int, int]]:
    """在地图上生成随机可行的起点终点对（无碰撞）"""
    if seed is not None:
        random.seed(seed)
    
    h, w = occupancy.shape
    free_cells = list(zip(*np.where(occupancy == 0)))
    if len(free_cells) < 2:
        raise ValueError("Not enough free cells to generate scenes")
    
    scenes = []
    attempts = 0
    while len(scenes) < num_scenes and attempts < max_attempts * num_scenes:
        start = random.choice(free_cells)
        goal = random.choice(free_cells)
        if start == goal:
            continue
        # 可选：添加简单连通性检查（BFS），避免生成不连通的场景
        # 这里为了效率，先不做检查，留到后续计算最优长度时再判断
        scenes.append((start[1], start[0], goal[1], goal[0]))  # 转换为 (x, y)
        attempts += 1
    return scenes

def compute_optimal_length(occupancy: np.ndarray, start: Tuple[int, int], goal: Tuple[int, int]) -> float:
    """计算两点间的最优路径长度（使用A*或Dijkstra）"""
    # 这里可以调用之前实现的算法，但需要避免循环依赖
    # 简单实现：使用BFS/DFS+八方向移动，计算最短路径长度
    from collections import deque
    import math
    
    h, w = occupancy.shape
    start_r, start_c = start[1], start[0]  # (x,y) -> (row,col)
    goal_r, goal_c = goal[1], goal[0]
    
    if occupancy[start_r, start_c] == 1 or occupancy[goal_r, goal_c] == 1:
        return float('inf')
    
    # BFS with diagonal moves (anti-tunneling)
    queue = deque()
    queue.append((start_r, start_c, 0.0))
    visited = set()
    visited.add((start_r, start_c))
    
    directions = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
    
    while queue:
        r, c, dist = queue.popleft()
        if (r, c) == (goal_r, goal_c):
            return dist
        
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < h and 0 <= nc < w):
                continue
            if occupancy[nr, nc] == 1:
                continue
            if dr != 0 and dc != 0:  # diagonal
                if occupancy[r + dr, c] == 1 or occupancy[r, c + dc] == 1:
                    continue
            step = math.sqrt(2.0) if dr != 0 and dc != 0 else 1.0
            if (nr, nc) not in visited:
                visited.add((nr, nc))
                queue.append((nr, nc, dist + step))
    return float('inf')

def write_scen_file(output_scen_path: str, map_name: str, width: int, height: int,
                   scenes: List[Tuple[int, int, int, int]], optimal_lengths: List[float] = None):
    """写入.scen文件"""
    with open(output_scen_path, 'w') as f:
        f.write("version 1\n")
        f.write(f"# Generated from {map_name}\n")
        for i, (sx, sy, gx, gy) in enumerate(scenes):
            opt = optimal_lengths[i] if optimal_lengths and i < len(optimal_lengths) else 0.0
            f.write(f"{map_name} {width} {height} {sx} {sy} {gx} {gy} {opt:.6f}\n")
    print(f"Scen file saved: {output_scen_path} with {len(scenes)} scenes")

def main():
    parser = argparse.ArgumentParser(description='Convert ROS map to MovingAI format')
    parser.add_argument('pgm', help='Input PGM file')
    parser.add_argument('yaml', help='Input YAML file')
    parser.add_argument('output_prefix', help='Output prefix (e.g., map) -> map.map and map.scen')
    parser.add_argument('--threshold', type=int, default=50, help='Occupancy threshold (0-100)')
    parser.add_argument('--scen', help='Output .scen file path (default: <output_prefix>.scen)')
    parser.add_argument('--num_scenes', type=int, default=10, help='Number of random scenes to generate')
    parser.add_argument('--seed', type=int, default=None, help='Random seed')
    parser.add_argument('--scen_file', help='Read scenes from a text file (format: start_x start_y goal_x goal_y per line)')
    parser.add_argument('--compute_optimal', action='store_true', help='Compute optimal lengths for scenes (may be slow)')
    args = parser.parse_args()
    
    # 转换地图
    output_map = f"{args.output_prefix}.map"
    width, height, occupancy = ros_to_movingai(args.pgm, args.yaml, output_map, args.threshold)
    
    # 确定.scen文件名
    output_scen = args.scen if args.scen else f"{args.output_prefix}.scen"
    
    # 获取场景列表
    scenes = []
    if args.scen_file:
        # 从文件读取场景
        with open(args.scen_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 4:
                    sx, sy, gx, gy = map(int, parts[:4])
                    scenes.append((sx, sy, gx, gy))
    else:
        # 生成随机场景
        scenes = generate_random_scenes(occupancy, args.num_scenes, args.seed)
    
    if not scenes:
        print("No scenes generated.")
        return
    
    # 可选：计算最优长度
    optimal_lengths = None
    if args.compute_optimal:
        print("Computing optimal lengths (this may take a while)...")
        optimal_lengths = []
        for sx, sy, gx, gy in scenes:
            length = compute_optimal_length(occupancy, (sx, sy), (gx, gy))
            optimal_lengths.append(length)
            if length == float('inf'):
                print(f"Warning: Scene {sx},{sy} -> {gx},{gy} is unreachable.")
    
    # 写入.scen
    write_scen_file(output_scen, os.path.basename(output_map), width, height, scenes, optimal_lengths)

if __name__ == '__main__':
    main()