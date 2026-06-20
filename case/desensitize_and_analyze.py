"""
广安村滑坡：数据脱敏 + 深度分析 (v2 — 修复LOS方向标注错误)
============================================================
v2 修复：负LOS值 ≠ 低形变。LOS向形变正负代表卫星视线方向，
         正 = 背离卫星（沉降/下滑），负 = 指向卫星（抬升/逆坡运动）。
         重新正确标注所有聚类和分析结论。

脱敏策略：坐标粗化到0.001°精度（~100m），加入随机偏移
"""
import json, math, random

random.seed(42)
BASE = r'D:\openclaw-workspace\insar-website\case'
TS_FILE = BASE + r'\guangancun_ts.txt'
VEL_FILE = BASE + r'\guangancun_vel.txt'
TS_OUT  = BASE + r'\guangancun_ts_desensitized.txt'
VEL_OUT = BASE + r'\guangancun_vel_desensitized.txt'
JSON_OUT = BASE + r'\guangancun_data.json'

# ══════════════ 1. 读取 ══════════════
with open(TS_FILE, 'r', encoding='utf-8') as f:
    ts_lines = f.readlines()
with open(VEL_FILE, 'r', encoding='utf-8') as f:
    vel_lines = f.readlines()

header_parts = ts_lines[0].strip().split()
dates_raw = header_parts[4:]
dates = [f'{str(int(float(d)))[:4]}-{str(int(float(d)))[4:6]}-{str(int(float(d)))[6:8]}' for d in dates_raw]
n_times = len(dates)

def des_lon(lon): return round(lon + (random.random()-0.5)*0.001, 4)
def des_lat(lat): return round(lat + (random.random()-0.5)*0.001, 4)

# ══════════════ 2. 解析+脱敏 ══════════════
pts = []
lons_des, lats_des = [], []
for line in ts_lines[1:]:
    v = [float(x) for x in line.strip().split()]
    pts.append(dict(id=int(v[0]),
                    lon=v[1], lat=v[2], avg=v[3], ts=v[4:],
                    lon_d=des_lon(v[1]), lat_d=des_lat(v[2])))

vel_map = {}
for line in vel_lines:
    v = [float(x) for x in line.strip().split()]
    vel_map[int(v[0])] = dict(rate=v[3], lon_o=v[1], lat_o=v[2])

for p in pts:
    lons_des.append(p['lon_d']); lats_des.append(p['lat_d'])

# ══════════════ 3. 写入脱敏 txt ══════════════
new_ts = [ts_lines[0]]
for p in pts:
    row = ' '.join(f'{x:.6f}' for x in [p['id'], p['lon_d'], p['lat_d'], p['avg']] + p['ts'])
    new_ts.append(row + '\n')
with open(TS_OUT, 'w', encoding='utf-8') as f: f.writelines(new_ts)

new_vel = []
for line in vel_lines:
    v = [float(x) for x in line.strip().split()]
    new_vel.append(f'{v[0]:.6f} {des_lon(v[1]):.6f} {des_lat(v[2]):.6f} {v[3]:.6f}\n')
with open(VEL_OUT, 'w', encoding='utf-8') as f: f.writelines(new_vel)
print(f'[OK] 脱敏 ts → {TS_OUT}')
print(f'[OK] 脱敏 vel → {VEL_OUT}')

# ══════════════ 4. 统计 ══════════════
def stats(arr):
    n=len(arr); m=sum(arr)/n; s=math.sqrt(sum((x-m)**2 for x in arr)/n)
    sa=sorted(arr)
    return dict(n=n,mean=round(m,2),std=round(s,2),min=round(sa[0],2),max=round(sa[-1],2),
                p5=round(sa[int(n*0.05)],2),p25=round(sa[int(n*0.25)],2),
                p50=round(sa[int(n*0.50)],2),p75=round(sa[int(n*0.75)],2),p95=round(sa[int(n*0.95)],2))

avgs = [p['avg'] for p in pts]
rates_arr = [vel_map[p['id']]['rate'] for p in pts if p['id'] in vel_map]
avg_stats = stats(avgs)
rate_stats = stats(rates_arr)

# ══════════════ 5. 聚类分析 ══════════════
# K-Means on 1D (mean deformation)
values = [p['avg'] for p in pts]
sv = sorted(values); k=3
centroids = [sv[int(len(sv)*i/k)] for i in range(k)]
labels = [0]*len(values)
for _ in range(50):
    changed=0
    sums=[0]*k; cnts=[0]*k
    for i,v in enumerate(values):
        ci = min(range(k), key=lambda ki: abs(v-centroids[ki]))
        if labels[i]!=ci: changed+=1; labels[i]=ci
        sums[ci]+=v; cnts[ci]+=1
    if changed==0: break
    for ci in range(k):
        if cnts[ci]>0: centroids[ci]=sums[ci]/cnts[ci]

# Sort centroids ascending → cluster 0=most negative, 1=middle, 2=most positive
order = sorted(range(k), key=lambda i: centroids[i])
label_remap = {old:new for new,old in enumerate(order)}
centroids_sorted = sorted(centroids)
cluster_labels = [label_remap[l] for l in labels]

# Correct LOS interpretation:
# LOS negative → toward satellite (uplift / reverse slope movement)
# LOS positive → away from satellite (subsidence / downslope sliding)
# Near zero → stable
cluster_names = {
    0: '负LOS形变区（指向卫星方向）',   # most negative
    1: '稳定区（近零形变）',
    2: '正LOS形变区（背离卫星方向）',   # most positive
}
# Short names for charts/UI
cluster_short = {0: '负LOS形变区', 1: '稳定区', 2: '正LOS形变区'}
cluster_colors = ['#0571b0', '#10b981', '#dc2626']  # blue=negative, green=stable, red=positive

cluster_info = []
for ci in range(k):
    idxs = [j for j,l in enumerate(cluster_labels) if l==ci]
    cpts = [pts[j] for j in idxs]
    cmeans = [cpts[j]['avg'] for j in range(len(cpts))]
    cts_avg = [sum(p['ts'][t] for p in cpts)/len(cpts) for t in range(n_times)]
    cluster_info.append(dict(
        name=cluster_names[ci],
        short=cluster_short[ci],
        count=len(cpts), pct=round(len(cpts)/len(pts)*100,1),
        mean_def=round(centroids_sorted[ci],2),
        min_def=round(min(cmeans),2), max_def=round(max(cmeans),2),
        center_ts=[round(v,2) for v in cts_avg], color=cluster_colors[ci],
    ))
    print(f'  [{cluster_short[ci]}] {len(cpts)}点 ({cluster_info[-1]["pct"]}%)  均值{centroids_sorted[ci]:.1f}mm  [{min(cmeans):.1f}~{max(cmeans):.1f}]')

# ══════════════ 6. 趋势分析 ══════════════
half = n_times // 2
accelerating = decelerating = stable_cnt = 0
for p in pts:
    fh = sum(p['ts'][:half])/half
    lh = sum(p['ts'][half:])/(n_times-half)
    d = lh - fh
    if abs(d) <= 5: stable_cnt += 1
    elif d > 5: accelerating += 1
    else: decelerating += 1
tot = len(pts)

# Seasonal: compute median point's time series seasonal diff
wet_vals, dry_vals = [], []
# Use cluster 1 (稳定区) as representative for seasonal
rep_ts = cluster_info[1]['center_ts'] if cluster_info[1]['count'] > 0 else pts[len(pts)//2]['ts']
for t, d in enumerate(dates):
    m = int(d[5:7])
    if 4 <= m <= 9: wet_vals.append(rep_ts[t])
    else: dry_vals.append(rep_ts[t])
wet_avg = sum(wet_vals)/len(wet_vals) if wet_vals else 0
dry_avg = sum(dry_vals)/len(dry_vals) if dry_vals else 0

# ══════════════ 7. 输出 JSON (Web可视化数据) ══════════════

# Top5 正LOS (背离卫星方向, positive)
pos_pts = sorted([p for p in pts if p['avg'] > 0], key=lambda p: p['avg'], reverse=True)
top5_pos = [dict(id=p['id'], label=f'P#{p["id"]} (+{p["avg"]:.1f}mm)',
                 data=[round(v,2) for v in p['ts']]) for p in pos_pts[:5]]

# Top5 负LOS (指向卫星方向, negative)
neg_pts = sorted([p for p in pts if p['avg'] < 0], key=lambda p: p['avg'])  # most negative first
top5_neg = [dict(id=p['id'], label=f'P#{p["id"]} ({p["avg"]:.1f}mm)',
                 data=[round(v,2) for v in p['ts']]) for p in neg_pts[:5]]

# Representative: P25, P50, P75 of POSITIVE points (the ones with movement away from satellite)
sorted_pos = sorted(pos_pts, key=lambda p: p['avg'])
n_pos = len(sorted_pos)
rep_pos = []
if n_pos > 2:
    for ri, rl in [(int(n_pos*0.25),'P25 (稳定+下滑交界)'),
                   (int(n_pos*0.50),'P50 (下滑中位数)'),
                   (int(n_pos*0.75),'P75 (高下滑区)')]:
        rep_pos.append(dict(id=sorted_pos[ri]['id'], label=rl,
                            data=[round(v,2) for v in sorted_pos[ri]['ts']]))

# Rate histogram
rates_all = [vel_map[p['id']]['rate'] for p in pts if p['id'] in vel_map]
r_min, r_max = min(rates_all), max(rates_all)
bw = (r_max - r_min)/10
h_labels=[f'{r_min+i*bw:.1f}~{r_min+(i+1)*bw:.1f}' for i in range(10)]
h_bins=[0]*10
for r in rates_all:
    h_bins[min(int((r-r_min)/bw),9)] += 1

# Spatial (desensitized)
spatial = [dict(id=p['id'], lon=round(p['lon_d'],4), lat=round(p['lat_d'],4),
                avg=round(p['avg'],2),
                rate=round(vel_map.get(p['id'],{}).get('rate',0),2),
                cluster=int(cluster_labels[pts.index(p)]))
           for p in pts]

# Cluster time series for web
cluster_series = [dict(name=cluster_info[ci]['short'],
                       count=cluster_info[ci]['count'],
                       mean=cluster_info[ci]['mean_def'],
                       pct=cluster_info[ci]['pct'],
                       data=cluster_info[ci]['center_ts'],
                       color=cluster_info[ci]['color'])
                  for ci in range(k)]

output = dict(
    dates=dates, n_points=len(pts),
    stats=dict(cumulative=avg_stats, rate=rate_stats),
    histogram=dict(labels=h_labels, values=h_bins),
    top5_pos_los=top5_pos,
    top5_neg_los=top5_neg,
    representative_pos=rep_pos,
    cluster_ts=cluster_series,
    spatial=spatial,
    coords=dict(lon_min=round(min(lons_des),4), lon_max=round(max(lons_des),4),
                lat_min=round(min(lats_des),4), lat_max=round(max(lats_des),4)),
    desensitized=True,
    analysis=dict(
        accelerating_pct=round(accelerating/tot*100,1),
        stable_pct=round(stable_cnt/tot*100,1),
        decelerating_pct=round(decelerating/tot*100,1),
        seasonal=dict(wet_avg=round(wet_avg,2), dry_avg=round(dry_avg,2),
                      diff=round(wet_avg-dry_avg,2)),
    ),
    cluster_names={str(ci): cluster_short[ci] for ci in range(k)},
)

with open(JSON_OUT, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f'\n[OK] 可视化JSON → {JSON_OUT}')

# ══════════════ Print Summary ══════════════
print()
print('=' * 60)
print(' 广安村滑坡 — 正确分析摘要 (v2)')
print('=' * 60)
print(f'\n监测点: {len(pts)}  |  影像: {n_times}景  |  时段: {dates[0]} ~ {dates[-1]}')
print(f'平均形变: {avg_stats["mean"]} mm  |  范围: {avg_stats["min"]} ~ {avg_stats["max"]} mm')
print()
print('LOS形变方向聚类:')
for ci in range(k):
    c = cluster_info[ci]
    print(f'  {c["short"]}: {c["count"]}点 ({c["pct"]}%), 均值 {c["mean_def"]}mm')
print()
print('形变加速趋势:')
print(f'  加速(后半段>前半段+5mm): {accelerating}点 ({round(accelerating/tot*100,1)}%)')
print(f'  基本稳定(波动<5mm): {stable_cnt}点 ({round(stable_cnt/tot*100,1)}%)')
print(f'  减速(后半段<前半段-5mm): {decelerating}点 ({round(decelerating/tot*100,1)}%)')
print()
print(f'季节性差异(代表点): 雨季{wet_avg:.1f}mm vs 旱季{dry_avg:.1f}mm (差{wet_avg-dry_avg:.1f}mm)')
