"""
InSAR 全流程主入口
===================
用法:
  python run.py --help
  python run.py search --lon 109.63 --lat 31.56 --start 2017-10 --end 2019-11
  python run.py visualize --data case/guangancun_data.json

流程（需要 ASF HyP3 API Token）:
  python run.py hyp3-run --lon 109.63 --lat 31.56 --start 2017-10-01 --end 2019-11-01 --token YOUR_TOKEN
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from download import Sentinel1Search, ASFSearch
from hyp3 import HyP3Client

def cmd_search(args):
    """搜索可用 Sentinel-1 数据"""
    searcher = Sentinel1Search()
    results = searcher.search_scenes(args.lon, args.lat, args.start, args.end,
                                     max_results=args.max or 50)
    
    if not results:
        print("\n尝试 ASF 搜索...")
        results = ASFSearch.search(args.lon, args.lat, args.start, args.end)
    
    if results:
        print(f"\n{'='*60}")
        print(f"找到 {len(results)} 景影像:")
        print(f"{'='*60}")
        # 按日期分组统计
        by_month = {}
        for r in results:
            m = r.get("date", r.get("sceneName", "")[:8])[:7]
            by_month.setdefault(m, []).append(r)
        
        for m in sorted(by_month.keys()):
            scenes = by_month[m]
            print(f"  {m}: {len(scenes)} 景")
            for s in scenes[:3]:
                name = s.get("name", s.get("sceneName", ""))[:40]
                print(f"    {name} ...")
            if len(scenes) > 3:
                print(f"    ... and {len(scenes)-3} more")
        
        # 建议的干涉图数量
        print(f"\n  建议处理: 选择同一轨道号的 ~{len(results)//2} 个干涉对")
    else:
        print("[!] 未找到数据")
        print("  可能的解决方案:")
        print("  1. 确认坐标在 Sentinel-1 覆盖范围内")
        print("  2. 扩展搜索时间范围")
        print("  3. 使用 ESA Data Space 手动下载")

def cmd_hyp3(args):
    """使用 HyP3 云端处理 InSAR"""
    if not args.token:
        print("[!] 需要 ASF API Token")
        print("  获取方式: https://hyp3.asf.alaska.edu → Profile → API Token")
        return
    
    client = HyP3Client(args.token)
    if not client.check_auth():
        return
    
    # 搜索可用数据
    search = Sentinel1Search()
    scenes = search.search_scenes(args.lon, args.lat, args.start, args.end)
    
    if not scenes:
        print("[!] 未找到数据")
        return
    
    # 按降轨/升轨分组
    tracks = {}
    for s in scenes:
        key = (s.get("orbit_dir", "?"), s.get("relative_orbit", 0))
        tracks.setdefault(key, []).append(s)
    
    print(f"\n可用轨道: {len(tracks)}")
    for (orb_dir, rel_orb), scs in sorted(tracks.items()):
        print(f"  {orb_dir} 轨道#{rel_orb}: {len(scs)} 景")
    
    # 选择使用哪一组
    best_track = None
    for (orb_dir, rel_orb), scs in tracks.items():
        if len(scs) >= 6:
            best_track = (orb_dir, rel_orb)
            break
    if not best_track:
        best_track = max(tracks.keys(), key=lambda k: len(tracks[k]))
    
    selected = tracks[best_track]
    print(f"\n选择: {best_track[0]} 轨道#{best_track[1]} ({len(selected)} 景)")
    
    # 提交 SBAS 批量处理
    scene_list = [{"name": s.get("name", ""), "date": s.get("date", "")[:10]}
                  for s in selected if s.get("name")]
    scene_list.sort(key=lambda x: x["date"])
    
    output_dir = args.output or os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "case", "hyp3_results")
    
    job_ids = client.submit_sbas_batch(scene_list, max_baseline_days=args.max_days or 200)
    
    print(f"\n提交了 {len(job_ids)} 个作业")
    print(f"作业 ID 已保存, 后续使用:")
    print(f"  python run.py hyp3-check --ids {','.join(job_ids[:3])}...")
    print(f"  python run.py hyp3-dl --output {output_dir} --token YOUR_TOKEN")

def cmd_hyp3_check(args):
    """检查 HyP3 作业状态"""
    token = args.token or os.environ.get("HYP3_TOKEN", "")
    client = HyP3Client(token)
    
    job_ids = args.ids.split(",")
    for jid in job_ids:
        jid = jid.strip()
        status = client.check_job_status(jid)
        if status:
            code = status.get("status_code", "?")
            files = status.get("files", [])
            print(f"  {jid[:20]}...: {code}  ({len(files)} files)")
        else:
            print(f"  {jid[:20]}...: 查询失败")

def cmd_hyp3_dl(args):
    """下载 HyP3 结果"""
    token = args.token or os.environ.get("HYP3_TOKEN", "")
    client = HyP3Client(token)
    
    jobs = client.list_jobs(status="SUCCEEDED")
    completed = {}
    for j in jobs:
        jid = j.get("job_id", "")
        files = j.get("files", [])
        urls = [f["url"] for f in files if f.get("url")]
        completed[jid] = {"urls": urls}
    
    downloaded = client.download_results(completed, args.output or "case/hyp3_results")
    print(f"\n下载了 {len(downloaded)} 个文件")


def main():
    parser = argparse.ArgumentParser(
        description="InSAR 全流程时序处理 (轻薄本 Windows 版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 搜索可用数据
  python run.py search --lon 109.63 --lat 31.56 --start 2017-10-01 --end 2019-11-01
  
  # HyP3 云端处理 (需 API Token)
  python run.py hyp3-run --lon 109.63 --lat 31.56 --start 2017-10 --end 2019-11 --token YOUR_TOKEN
  
  # 下载已有结果
  python run.py hyp3-dl --output case/hyp3_results --token YOUR_TOKEN
        """
    )
    parser.add_argument("command", nargs="?", default="help",
                        choices=["search", "hyp3-run", "hyp3-check", "hyp3-dl",
                                 "sbas-demo", "help"])
    
    # 通用参数
    parser.add_argument("--lon", type=float, default=109.63)
    parser.add_argument("--lat", type=float, default=31.56)
    parser.add_argument("--start", default="2017-10-01")
    parser.add_argument("--end", default="2019-11-01")
    parser.add_argument("--max", type=int, default=50)
    parser.add_argument("--max-days", type=int, default=200)
    parser.add_argument("--token", default="")
    parser.add_argument("--ids", default="")
    parser.add_argument("--output", default="")
    
    args = parser.parse_args()
    
    if args.command == "help":
        parser.print_help()
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "hyp3-run":
        cmd_hyp3(args)
    elif args.command == "hyp3-check":
        cmd_hyp3_check(args)
    elif args.command == "hyp3-dl":
        cmd_hyp3_dl(args)
    elif args.command == "sbas-demo":
        from sbas import demo_sbas
        demo_sbas()

if __name__ == "__main__":
    main()
