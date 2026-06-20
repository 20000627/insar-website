# InSAR 全流程时序处理管道

**适用**: Windows 轻薄笔记本 | **依赖**: Python 3.8+ | **重计算**: 云端

## 快速开始

```bash
# 安装依赖
pip install requests numpy tqdm

# 搜索可用数据
python run.py search --lon 109.63 --lat 31.56 --start 2017-10 --end 2019-11

# SBAS 反演演示
python run.py sbas-demo

# 云端处理 (需 ASF API Token)
python run.py hyp3-run --lon 109.63 --lat 31.56 --start 2017-10 --end 2019-11 --token YOUR_TOKEN
```

## 全流程架构

```
用户输入 (AOI, 时间范围)
        │
        ▼
┌──────────────────┐
│ 1. 数据搜索       │ ← ESA Data Space (直连) / ASF (备选)
│    (download.py) │
└──────┬───────────┘
       │
       ▼ (选择轨道)
┌──────────────────┐
│ 2. 干涉图生成     │ ← 方案A: ASF HyP3 云端 (推荐)
│    (hyp3.py)     │    方案B: SNAP GPT 本地 (小ROI)
└──────┬───────────┘
       │
       ▼ (下载干涉图)
┌──────────────────┐
│ 3. SBAS 时序反演  │ ← 本地轻量计算 (numpy加速)
│    (sbas.py)     │    输入: 干涉图对 → 输出: 累计形变时序
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 4. 可视化 + 页面   │ ← 生成 JSON → 案例详情页
│    (template)     │    与 template_process.py 集成
└──────────────────┘
```

## 模块说明

| 模块 | 文件 | 功能 | 资源消耗 |
|------|------|------|----------|
| 数据搜索 | `download.py` | ESA/ASF Sentinel-1 搜索 | 网络 |
| 云端处理 | `hyp3.py` | ASF HyP3 API 封装 | 网络 (云) |
| SBAS反演 | `sbas.py` | 最小二乘/SVD时序反演 | CPU 轻量 |
| 主入口 | `run.py` | CLI 命令行 | — |
| 配置 | `config.py` | 默认参数 | — |

## SBAS 反演算法

```
干涉图相位 dφ_i = φ_slave - φ_master
                  ┌                    ┐ ┌      ┐
设计矩阵:  A * x = │ -1  0  +1  0   0  │ │ φ_t1 │ = dφ_i
                  │  0 -1   0 +1   0  │ │ φ_t2 │
                  │ -1  0   0  +1   0  │ │ φ_t3 │
                  └                    ┘ │ φ_t4 │
                                         │ φ_t5 │
                                         └      ┘
求解: x = A⁺ * b  (SVD 伪逆，截断小奇异值)
速率: v = (x_last - x_first) / 时间跨度(年)
```

## 从零到案例详情页

```
1. python run.py search --lon X --lat Y --start S --end E
      → 找到可用数据 → 确定轨道

2. python run.py hyp3-run --lon X --lat Y ... --token TOKEN
      → 提交云端处理 → 等完成

3. python run.py hyp3-dl --output case/hyp3_results
      → 下载干涉图 GeoTIFF

4. python case/template_process.py (修改配置)
      → 生成 JSON → 自动创建详情页

5. git add . && git commit && git push
      → 上线
```

## 实测 (from China)

| 服务 | 状态 | 说明 |
|------|------|------|
| ESA Data Space | ✅ 直连 | 搜索/下载 Sentinel-1 数据 |
| ASF HyP3 | ⚠️ 根可达 | 需免费注册获取 API Token |
| SNAP 本地 | ❌ 未安装 | 需要时再装 (1.5GB, D盘) |
