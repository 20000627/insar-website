"""
InSAR 时序形变数据 → 可视化 + 详情页 模板脚本
================================================
数据格式要求（与 guangancun 一致）：

  ts.txt: 第一行为表头，前4列为 点号/经度/纬度/平均形变，
          第5列起为各时相形变值（表头为日期 YYYYMMDD）
          空格分隔。

  vel.txt（可选）: 点号/经度/纬度/形变速率，空格分隔

用法：修改下方 "== 用户配置 ==" 区域即可
"""

import json, math, random
from pathlib import Path

# ═══════════════════════════════════════════════
# == 用户配置 ===================================
# ═══════════════════════════════════════════════

PROJECT_NAME = "广安村滑坡时序 InSAR 监测"   # 项目名称
PROJECT_TAG  = "地质灾害"                     # 分类标签
TS_FILE      = r"D:\openclaw-workspace\insar-website\case\guangancun_ts.txt"
VEL_FILE     = r"D:\openclaw-workspace\insar-website\case\guangancun_vel.txt"
OUTPUT_DIR   = r"D:\openclaw-workspace\insar-website\case"
JSON_OUT     = "guangancun_data.json"

# Desensitization
DESENSITIZE    = True     # 是否脱敏坐标
DESENSITIZE_SEED = 42     # 随机种子（脱敏可重复）

# 聚类数
N_CLUSTERS = 3

# ═══════════════════════════════════════════════
# == 以下无需修改 ================================
# ═══════════════════════════════════════════════

def compute_stats(arr):
    n=len(arr); m=sum(arr)/n; s=math.sqrt(sum((x-m)**2 for x in arr)/n)
    sa=sorted(arr)
    return dict(n=n,mean=round(m,2),std=round(s,2),min=round(sa[0],2),max=round(sa[-1],2),
                p5=round(sa[int(n*0.05)],2),p25=round(sa[int(n*0.25)],2),
                p50=round(sa[int(n*0.50)],2),p75=round(sa[int(n*0.75)],2),p95=round(sa[int(n*0.95)],2))

def kmeans_1d(values, k=3, max_iter=50):
    n=len(values); sv=sorted(values)
    centroids=[sv[int(n*i/k)] for i in range(k)]
    labels=[0]*n
    for _ in range(max_iter):
        changed=0; sums=[0]*k; cnts=[0]*k
        for i,v in enumerate(values):
            ci=min(range(k), key=lambda ki: abs(v-centroids[ki]))
            if labels[i]!=ci: changed+=1; labels[i]=ci
            sums[ci]+=v; cnts[ci]+=1
        if changed==0: break
        for ci in range(k):
            if cnts[ci]>0: centroids[ci]=sums[ci]/cnts[ci]
    return labels, centroids

def main():
    import os
    if DESENSITIZE:
        random.seed(DESENSITIZE_SEED)
    base = os.path.dirname(TS_FILE)
    fname = os.path.splitext(os.path.basename(TS_FILE))[0]
    out_json = os.path.join(OUTPUT_DIR, JSON_OUT)

    # 1. Read
    with open(TS_FILE, 'r', encoding='utf-8') as f:
        ts_lines = f.readlines()
    header = ts_lines[0].strip().split()
    dates_raw = header[4:]
    dates = [f'{s[:4]}-{s[4:6]}-{s[6:8]}' for s in
             [str(int(float(d))) for d in dates_raw]]
    n_times = len(dates)

    # 2. Parse points
    pts = []
    for line in ts_lines[1:]:
        v = [float(x) for x in line.strip().split()]
        pts.append(dict(id=int(v[0]), lon=v[1], lat=v[2], avg=v[3], ts=v[4:]))

    # 2b. velocities
    vel_map = {}
    if os.path.exists(VEL_FILE):
        with open(VEL_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                v = [float(x) for x in line.strip().split()]
                vel_map[int(v[0])] = dict(rate=v[3])

    # 3. Desensitize
    def des_lon(lon): return round(lon + (random.random()-0.5)*0.001, 4) if DESENSITIZE else lon
    def des_lat(lat): return round(lat + (random.random()-0.5)*0.001, 4) if DESENSITIZE else lat

    for p in pts:
        p['lon_d'] = des_lon(p['lon'])
        p['lat_d'] = des_lat(p['lat'])

    # 4. Statistics
    avgs = [p['avg'] for p in pts]
    rates_arr = [vel_map[p['id']]['rate'] for p in pts if p['id'] in vel_map]
    avg_stats = compute_stats(avgs)
    rate_stats = compute_stats(rates_arr) if rates_arr else {}

    # 5. Cluster analysis
    values = [p['avg'] for p in pts]
    labels, centroids = kmeans_1d(values, k=N_CLUSTERS)
    order = sorted(range(N_CLUSTERS), key=lambda i: centroids[i])
    label_remap = {old:new for new,old in enumerate(order)}
    centroids_sorted = sorted(centroids)
    cluster_labels = [label_remap[l] for l in labels]

    # Naming based on LOS interpretation
    cluster_short = {}
    for ci in range(N_CLUSTERS):
        m = centroids_sorted[ci]
        if m < -2: cluster_short[ci] = '负LOS形变区'
        elif m > 5: cluster_short[ci] = '正LOS形变区'
        else: cluster_short[ci] = '稳定区'

    cluster_colors = {'负LOS形变区': '#0571b0', '稳定区': '#10b981', '正LOS形变区': '#dc2626'}
    default_colors = ['#636efa', '#ef553b', '#00cc96']

    cluster_info = []
    for ci in range(N_CLUSTERS):
        idxs = [j for j,l in enumerate(cluster_labels) if l==ci]
        cpts = [pts[j] for j in idxs]
        cmeans = [cpts[j]['avg'] for j in range(len(cpts))]
        cts_avg = [sum(p['ts'][t] for p in cpts)/len(cpts) for t in range(n_times)]
        cl_name = cluster_short.get(ci, f'Cluster {ci+1}')
        cluster_info.append(dict(
            name=cl_name, count=len(cpts), pct=round(len(cpts)/len(pts)*100,1),
            mean_def=round(centroids_sorted[ci],2),
            min_def=round(min(cmeans),2), max_def=round(max(cmeans),2),
            center_ts=[round(v,2) for v in cts_avg],
            color=cluster_colors.get(cl_name, default_colors[ci%3]),
        ))

    # 6. Trend analysis
    half = n_times // 2
    accel = stable_cnt = decel = 0
    for p in pts:
        fh = sum(p['ts'][:half])/half
        lh = sum(p['ts'][half:])/(n_times-half)
        d = lh - fh
        if abs(d) <= 5: stable_cnt += 1
        elif d > 5: accel += 1
        else: decel += 1
    tot = len(pts)

    # Seasonal
    rep_ts = cluster_info[1]['center_ts'] if len(cluster_info)>1 and cluster_info[1]['count']>0 else pts[len(pts)//2]['ts']
    wet_vals, dry_vals = [], []
    for t, d in enumerate(dates):
        m = int(d[5:7])
        if 4 <= m <= 9: wet_vals.append(rep_ts[t])
        else: dry_vals.append(rep_ts[t])
    wet_avg = sum(wet_vals)/len(wet_vals) if wet_vals else 0
    dry_avg = sum(dry_vals)/len(dry_vals) if dry_vals else 0

    # 7. Web data
    # Top5 POS and NEG
    pos_pts = sorted([p for p in pts if p['avg'] > 0], key=lambda p: p['avg'], reverse=True)
    neg_pts = sorted([p for p in pts if p['avg'] < 0], key=lambda p: p['avg'])
    top5_pos = [dict(id=p['id'], label=f'P#{p["id"]} (+{p["avg"]:.1f}mm)',
                     data=[round(v,2) for v in p['ts']]) for p in pos_pts[:5]]
    top5_neg = [dict(id=p['id'], label=f'P#{p["id"]} ({p["avg"]:.1f}mm)',
                     data=[round(v,2) for v in p['ts']]) for p in neg_pts[:5]]

    # Histogram
    rates_all = [vel_map[p['id']]['rate'] for p in pts if p['id'] in vel_map]
    if rates_all:
        r_min, r_max = min(rates_all), max(rates_all)
        bw = max((r_max - r_min)/10, 0.1)
        h_labels = [f'{r_min+i*bw:.1f}~{r_min+(i+1)*bw:.1f}' for i in range(10)]
        h_bins = [0]*10
        for r in rates_all:
            h_bins[min(int((r-r_min)/bw),9)] += 1
    else:
        h_labels, h_bins = [], []

    # Spatial
    spatial = [dict(id=p['id'], lon=round(p['lon_d'],4), lat=round(p['lat_d'],4),
                    avg=round(p['avg'],2),
                    rate=round(vel_map.get(p['id'],{}).get('rate',0),2),
                    cluster=int(cluster_labels[pts.index(p)]))
               for p in pts]

    cluster_series = [dict(name=ci['name'], count=ci['count'], mean=ci['mean_def'],
                           pct=ci['pct'], data=ci['center_ts'], color=ci['color'])
                      for ci in cluster_info]

    output = dict(
        dates=dates, n_points=len(pts),
        stats=dict(cumulative=avg_stats, rate=rate_stats),
        histogram=dict(labels=h_labels, values=h_bins),
        top5_pos_los=top5_pos,
        top5_neg_los=top5_neg,
        cluster_ts=cluster_series,
        spatial=spatial,
        coords=dict(lon_min=round(min(p['lon_d'] for p in pts),4),
                    lon_max=round(max(p['lon_d'] for p in pts),4),
                    lat_min=round(min(p['lat_d'] for p in pts),4),
                    lat_max=round(max(p['lat_d'] for p in pts),4)),
        desensitized=DESENSITIZE,
        analysis=dict(
            accelerating_pct=round(accel/tot*100,1),
            stable_pct=round(stable_cnt/tot*100,1),
            decelerating_pct=round(decel/tot*100,1),
            seasonal=dict(wet_avg=round(wet_avg,2), dry_avg=round(dry_avg,2),
                          diff=round(wet_avg-dry_avg,2)),
        ),
        cluster_names={str(ci): cluster_short[ci] for ci in range(N_CLUSTERS)},
    )

    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'[OK] → {out_json}')
    print(f'  点数: {len(pts)}, 时相: {n_times}, 时段: {dates[0]}~{dates[-1]}')
    for ci in cluster_info:
        print(f'  [{ci["name"]}] {ci["count"]}点 ({ci["pct"]}%) 均值{ci["mean_def"]}mm')
    print(f'  加速: {accel}({round(accel/tot*100,1)}%) 稳定: {stable_cnt}({round(stable_cnt/tot*100,1)}%) 减速: {decel}({round(decel/tot*100,1)}%)')

if __name__ == '__main__':
    main()
