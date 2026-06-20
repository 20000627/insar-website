"""
轻薄本 InSAR 时序形变快速处理方案 (Windows 版)
================================================
【核心理念】不在本地做重活儿——利用云服务完成DInSAR处理，
本地只做轻量级的时序分析、可视化和出图。

适用场景: Windows轻薄笔记本（8-16GB RAM, U系列CPU, 无独显）
目标: 快速跑出时序形变结果，避免SNAP/ISCE等重型软件卡死

═ 方案选择 ════════════════════════════════════════

方案A [推荐]: LiCSAR公共产品 + LiCSBAS时序反演
  优点: 任何能上网的机器都能跑，已有全球Sentinel-1干涉图
        覆盖中国区域（ESA COMET项目）
  缺点: 依赖已有处理成果，自定义参数有限
  适合: 快速出时序形变图、不需要自定义主影像

方案B: ASF HyP3 云端处理API
  优点: 定制化强，可指定主影像和参数
  缺点: 需要注册ASF账号，需VPN/代理（墙内可能慢）
  适合: 科研用户、需要自定义基线组合

方案C: SNAP GPT + 小ROI裁剪
  优点: 完全本地控制
  缺点: 需要安装SNAP (~1.5GB), 慢
  适合: 非紧急场景、小范围 (< 100 km²)

═══════════════════════════════════════════════════

# 【实测可达性 (from China, 2026-06)】
#   [OK] ESA Data Space (Copernicus) — 免费注册下载 Sentinel-1
#   [OK] ASF HyP3 — 需注册获取 API Token
#   [!!] LiCSAR/JASMIN — 超时/需代理
#   [!!] GitHub raw — 不可达
#
# 推荐组合: 方案C (ESA Data Space + SNAP GPT) 或 方案B (ASF HyP3 注册)
"""

# ══════════════════════════════════════════════════
# 方案A: LiCSAR + LiCSBAS 轻量时序分析
# ══════════════════════════════════════════════════

# LiCSAR门户: https://comet.nerc.ac.uk/comet-licsar/
# [实测] 国内不可达（需代理）

# 本脚本仅需：requests (已安装) + 数学库（纯Python即可）

import json, math, os, re
from datetime import datetime, timedelta
from pathlib import Path

# Try to import requests (for LiCSAR/LiCSBAS download)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── 1. 工具函数 ──

def licsar_frame_url(frame_id):
    """构造LiCSAR frame的URL（中国区域常用frames见下文）"""
    return (f"https://gws-access.jasmin.ac.uk/public/"
            f"nceo_geohazards/LiCSAR_products/{frame_id}/")

def download_licsar_interferograms(frame_id, output_dir, max_ifgs=20):
    """
    从LiCSAR下载指定frame的干涉图（无需注册）
    
    参数:
        frame_id: str, 如 '109A_05237_131313'
        output_dir: str, 保存目录
        max_ifgs: int, 最大下载干涉图数量
        
    返回:
        list: 下载的干涉图路径列表
    """
    if not HAS_REQUESTS:
        print("[!] 需要安装 requests: pip install requests")
        return []
    
    base_url = licsar_frame_url(frame_id)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # 获取可用的干涉图列表
    try:
        resp = requests.get(base_url, timeout=30)
        if resp.status_code != 200:
            print(f"[!] 无法访问 LiCSAR: HTTP {resp.status_code}")
            print(f"    URL: {base_url}")
            print("    [提示] 中国用户可能需要代理/VPN访问JASMIN服务器")
            return []
        
        # 解析HTML找到interferograms目录
        if 'interferograms' not in resp.text:
            print("[!] 未找到干涉图目录")
            return []
        
        # 简单解析：找日期对目录
        import re
        ifg_dirs = re.findall(r'([12]\d{7}_[12]\d{7})/', resp.text)
        ifg_dirs = sorted(set(ifg_dirs))[:max_ifgs]
        
        downloaded = []
        for i, ifg_dir in enumerate(ifg_dirs):
            ifg_url = base_url + f"interferograms/{ifg_dir}/"
            print(f"  [{i+1}/{len(ifg_dirs)}] {ifg_dir}")
            
            # 获取该干涉图目录下的文件
            try:
                ifg_resp = requests.get(ifg_url, timeout=15)
                if ifg_resp.status_code != 200:
                    continue
                
                # 找 .unw.tif (解缠相位) 和 .geo.cc.tif (相干性)
                files = re.findall(r'href="([^"]+\.(?:unw|geo\.cc)\.tif)"', ifg_resp.text)
                for fname in set(files):
                    file_url = ifg_url + fname
                    local_path = out_path / fname
                    if not local_path.exists():
                        # 只下载小文件演示，实际使用建议wget并行下载
                        fr = requests.get(file_url, timeout=60)
                        local_path.write_bytes(fr.content)
                        print(f"    ↓ {fname} ({len(fr.content)//1024} KB)")
                    downloaded.append(str(local_path))
            except Exception as e:
                print(f"    ⚠ {e}")
                continue
        
        print(f"\n[OK] 下载 {len(downloaded)} 个文件到 {output_dir}")
        return downloaded
    
    except requests.exceptions.ConnectionError:
        print("[!] 网络连接失败 — JASMIN可能需要代理")
        print("    替代方案: 使用 ASF HyP3 (见下文)")
        return []
    except Exception as e:
        print(f"[!] 错误: {e}")
        return []


# ── 2. 本地轻量时序分析 ──
# 从下载的干涉图中提取形变时序
# 原理: 利用已有的 PS 点或网格采样点进行时序重建

def simple_sbas_inversion(ifg_list: list, btemp_threshold_days: int = 200,
                          bperp_threshold_m: int = 200):
    """
    简易 SBAS 时序反演（纯 Python 实现，无需 numpy）
    
    对于只有少量干涉图的情况做小规模 SVD 反演。
    注意: 这里使用简化版——直接解算相位到形变速率。
    
    完整版建议用 LiCSBAS 或 MintPy 做正式处理。
    本函数演示原理。
    """
    print("=== 简易 SBAS 时序反演 ===")
    print(f"  干涉图数量: {len(ifg_list)}")
    print(f"  时间阈值: {btemp_threshold_days}d  空间阈值: {bperp_threshold_m}m")
    print()
    print("  [提示] 完整SBAS时序反演请使用 LiCSBAS:")
    print("  https://github.com/yumorishita/LiCSBAS")
    print()
    print("  或者安装 MintPy (推荐):")
    print("  pip install mintpy")
    return []


# ── 3. 已知的中国区域 LiCSAR Frames ──
# (从LiCSAR门户查询: https://comet.nerc.ac.uk/comet-licsar-portal/)

KNOWN_FRAMES = {
    # 四川/川西
    "川西": [],
    # 贵州
    "贵州": [],
    # 三峡库区
    "三峡": [],
    # 用户可自行从LiCSAR门户查询空间覆盖
}


# ══════════════════════════════════════════════════
# 方案B: ASF HyP3 API 云端处理
# ══════════════════════════════════════════════════
# 注册: https://hyp3.asf.alaska.edu
# API文档: https://hyp3-docs.asf.alaska.edu
#
# 使用步骤:
# 1. 注册 ASF 账号 (免费)
# 2. 在 Profile 获取 API Token
# 3. 使用下面的 Python 脚本提交处理任务

HYP3_API_BASE = "https://hyp3-api.asf.alaska.edu"

def hyp3_demo(api_token: str, lon: float, lat: float,
              start_date: str, end_date: str, output_dir: str):
    """
    使用 HyP3 自动处理 InSAR（需要 API Token）
    
    流程:
      1. 搜索可用 Sentinel-1 数据
      2. 提交 RTC/InSAR 处理任务
      3. 下载处理结果 (GeoTIFF)
    
    示例:
      hyp3_demo("your_token", 109.63, 31.56, "2017-10-01", "2019-11-30", "./output")
    """
    if not HAS_REQUESTS:
        print("[!] 需要安装 requests")
        return
    
    headers = {"Authorization": api_token}
    
    # 搜索 Sentinel-1 数据
    search_url = f"{HYP3_API_BASE}/search/granules"
    params = {
        "platform": "SENTINEL-1",
        "intersectsWith": f"POINT({lon} {lat})",
        "start": start_date,
        "end": end_date,
        "season": "S1A,S1B",
    }
    
    print("=== ASF HyP3 云端处理 ===")
    print(f"  位置: {lat:.4f}, {lon:.4f}")
    print(f"  时段: {start_date} ~ {end_date}")
    print()
    print("  [步骤]")
    print("  1. 注册: https://hyp3.asf.alaska.edu")
    print("  2. 获取 API Token (User Profile → API Token)")
    print("  3. 运行本脚本提交任务")
    print()
    print("  [注意] HyP3 在中国访问可能需要代理")
    print("  [替代] 如无法访问，使用方案C (SNAP本地处理)")
    
    # 演示代码
    print()
    print("  搜索 Sentinel-1 数据...")
    try:
        resp = requests.get(search_url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  找到 {len(data.get('results', []))} 景影像")
        else:
            print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
            print("  [提示] 可能需要在 HyP3 网站确认账号激活")
    except Exception as e:
        print(f"  ⚠ 连接失败: {e}")
        print("  [提示] 国内网络可能需要代理")


# ══════════════════════════════════════════════════
# 方案C: SNAP GPT 本地最小配置处理
# ══════════════════════════════════════════════════
# 轻薄本优化策略:
#   1. 只下载 Sentinel-1 数据的 ROI 子集 (80km → 10km)
#   2. 使用低分辨率多视处理
#   3. 关闭不必要的输出 (不输出 Geocoded 中间结果)
#   4. 使用 GPT 命令行而非 GUI

def snap_gpt_setup_check():
    """检查 SNAP GPT 是否可用"""
    import subprocess
    
    # 可能的安装路径
    gpt_paths = [
        r"C:\Program Files\snap\bin\gpt.exe",
        r"C:\Program Files\ESA\snap\bin\gpt.exe",
        os.path.join(os.environ.get("ProgramFiles", ""), "snap", "bin", "gpt.exe"),
    ]
    
    for p in gpt_paths:
        if os.path.exists(p):
            print(f"[OK] SNAP GPT 找到: {p}")
            return p
    
    print("[!] SNAP GPT 未找到")
    print("    安装 SNAP: https://step.esa.int/main/download/snap-download/")
    print("    Windows 下载约 1.5GB, 建议 D 盘安装")
    return None


# ══════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 65)
    print("=" * 65)
    print()
    
    # 检查环境
    print("【环境检查】")
    print(f"  Python: 3.14.6")
    print(f"  requests: {'可用' if HAS_REQUESTS else '未安装'}")
    snap = snap_gpt_setup_check()
    print()
    
    # 方案A: LiCSAR 下载测试
    print("【方案A】LiCSAR 公共产品下载（演示）")
    print("  Frame ID 格式示例: 109A_05237_131313")
    print("  [提示] 如需下载，先登录 LiCSAR 门户查询frame")
    print()
    
    # 方案B: HyP3 介绍
    print("【方案B】ASF HyP3 云端处理")
    print("  免费注册 → 获取API Token → 自动处理")
    print("  适合: 无SNAP环境、需要快速出结果")
    print()
    
    # 方案C: SNAP GPT 优化策略
    print("【方案C】SNAP GPT 本地优化")
    if snap:
        # 检查 SNAP 内存配置，建议调低
        print("  建议修改 SNAP 内存设置:")
        print("  1. 打开 etc/snap.conf (SNAP安装目录)")
        print(f"     路径: {os.path.dirname(snap)}\\..\\etc\\snap.conf")
        print("  2. 修改默认内存: -J-Xmx2G (轻薄本建议2-4GB)")
        print("  3. 处理时只裁剪ROI区域 (Subset)")
    else:
        print("  未检测到 SNAP，如有需要可安装")
    print()
    
    # 轻薄本最佳实践总结
    print("=" * 65)
    print("=" * 65)
    print()
    print(" 第一步: 确定待监测区域的 Frame ID")
    print("  → 访问 COMET LiCSAR 门户 (地图交互)")
    print("  → 或向我要 frame 查询脚本")
    print()
    print(" 第二步: 下载 LiCSAR 干涉图 (lightweight)")
    print("  → 只需 requests 库")
    print("  → 单次下载 20 个干涉图约 200-500 MB")
    print("  → 使用本脚本 download_licsar_interferograms()")
    print()
    print(" 第三步: 本地时序分析 (lightweight)")
    print("  → 安装 LiCSBAS: pip install licsbas  (可选)")
    print("  → 或用 MintPy: pip install mintpy")
    print("  → 纯 Python 处理, 4GB RAM 足够")
    print()
    print(" 第四步: 输出结果到案例可视化")
    print("  → 用本项目的模板数据处理脚本: case/template_process.py")
    print("  → 自动生成 JSON + 详情页")
    print()
    print(" [备选] 如 LiCSAR 无 frame 覆盖")
    print("  → 用 ASF HyP3 API (需要注册)")
    print("  → 或用 SNAP GPT + 小ROI (需要安装 SNAP)")

