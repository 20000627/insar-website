"""
ASF HyP3 云端 InSAR 处理
=========================
使用 HyP3 API 提交 INSAR_GAMMA 作业，生成干涉图
仅需 Python + requests，所有重计算在云端完成
"""
import requests, json, os, time, re
from datetime import datetime
from pathlib import Path

HYP3_BASE = "https://hyp3-api.asf.alaska.edu"

class HyP3Client:
    """ASF HyP3 InSAR 云处理客户端"""
    
    def __init__(self, api_token=None):
        """
        参数:
            api_token: str — ASF 账号 Profile 中的 API Token
        """
        self.base = HYP3_BASE
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
        })
        if api_token:
            self.session.headers.update({"Authorization": api_token})
        self.api_token = api_token
    
    def check_auth(self):
        """检查 API Token 是否有效"""
        try:
            r = self.session.get(f"{self.base}/user", timeout=10)
            if r.status_code == 200:
                user = r.json()
                print(f"[HyP3] 已认证: {user.get('name', '?')}")
                return True
            else:
                print(f"[HyP3] 认证失败: HTTP {r.status_code}")
                print("   请检查 API Token (ASF Profile → API Token)")
                return False
        except Exception as e:
            print(f"[HyP3] 连接异常: {e}")
            return False
    
    def get_available_granules(self, granule_list):
        """
        按 granule name 列表查询可用性
        
        参数:
            granule_list: list[str] — scene names
        
        返回: list[dict]
        """
        url = f"{self.base}/search/granules"
        params = {"granuleList": ",".join(granule_list)}
        try:
            r = self.session.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json().get("results", [])
            return []
        except Exception as e:
            print(f"[!] granule 查询失败: {e}")
            return []
    
    def submit_insar_job(self, reference_scene, secondary_scene,
                         name_prefix="insar", **kwargs):
        """
        提交 InSAR 干涉图处理作业
        
        参数:
            reference_scene: str — 主影像 scene name (如 S1A_IW_SLC__...)
            secondary_scene: str — 从影像 scene name
            name_prefix: str — 作业名称前缀
        
        可选参数 (见 config.HYP3_INSAR_DEFAULTS):
            looks, phase_filter, unw_method, include_dem, ...
        
        返回: str — job_id, 或 None
        """
        if not self.api_token:
            print("[!] 需要设置 API Token")
            return None
        
        from config import HYP3_INSAR_DEFAULTS
        params = dict(HYP3_INSAR_DEFAULTS)
        params.update(kwargs)
        
        payload = {
            "job_type": "INSAR_GAMMA",
            "name": f"{name_prefix}_{reference_scene[:20]}",
            "granules": [{
                "granule_id": reference_scene,
                "granule_type": "sentinel1_slc",
            }, {
                "granule_id": secondary_scene,
                "granule_type": "sentinel1_slc",
            }],
            "job_parameters": params,
        }
        
        print(f"[HyP3] 提交 InSAR 作业: {reference_scene[:30]} ↔ {secondary_scene[:30]}")
        try:
            r = self.session.post(
                f"{self.base}/jobs",
                json=payload, timeout=30
            )
            if r.status_code in (200, 201):
                job = r.json()
                job_id = job.get("job_id", "")
                print(f"  [OK] 作业已提交: {job_id}")
                print(f"  状态: {job.get('status_code', '')}")
                return job_id
            else:
                print(f"  [!!] 提交失败: HTTP {r.status_code}")
                print(f"  {r.text[:300]}")
                return None
        except Exception as e:
            print(f"  [!!] 异常: {e}")
            return None
    
    def submit_sbas_batch(self, scene_list, max_baseline_days=200,
                          max_baseline_perp=200, name_prefix="sbas"):
        """
        批量提交 SBAS 干涉对
        
        参数:
            scene_list: list[dict] — 按日期排序的影像列表
                        [{"name": "...", "date": "YYYY-MM-DD"}, ...]
            max_baseline_days: int — 最大时间基线（天）
            max_baseline_perp: int — 最大空间基线（米）
        
        返回: list[str] — job_id 列表
        """
        if len(scene_list) < 2:
            print("[!] 至少需要 2 景影像")
            return []
        
        # 生成干涉对（小基线集）
        pairs = []
        for i in range(len(scene_list)):
            d1 = scene_list[i]["date"]
            for j in range(i + 1, len(scene_list)):
                d2 = scene_list[j]["date"]
                days = (datetime.strptime(d2, "%Y-%m-%d") -
                        datetime.strptime(d1, "%Y-%m-%d")).days
                if 12 <= days <= max_baseline_days:  # 至少12天（Sentinel-1重访周期）
                    pairs.append((scene_list[i]["name"],
                                  scene_list[j]["name"],
                                  d1, d2, days))
        
        print(f"[HyP3] 生成 {len(pairs)} 个干涉对 (基线≤{max_baseline_days}d)")
        
        job_ids = []
        for i, (ref, sec, d1, d2, days) in enumerate(pairs):
            print(f"\n  [{i+1}/{len(pairs)}] {d1} ↔ {d2} ({days}d)")
            jid = self.submit_insar_job(ref, sec, name_prefix=name_prefix)
            if jid:
                job_ids.append(jid)
            # 避免 API 限流
            if (i + 1) % 5 == 0:
                print("  ... 等待 2 秒避免限流 ...")
                time.sleep(2)
        
        return job_ids
    
    def check_job_status(self, job_id):
        """查询作业状态"""
        try:
            r = self.session.get(f"{self.base}/jobs/{job_id}", timeout=10)
            if r.status_code == 200:
                return r.json()
            return None
        except:
            return None
    
    def list_jobs(self, status=None, limit=50):
        """列出所有作业"""
        params = {"limit": limit}
        if status:
            params["status_code"] = status
        try:
            r = self.session.get(f"{self.base}/jobs", params=params, timeout=15)
            if r.status_code == 200:
                return r.json().get("jobs", [])
            return []
        except:
            return []
    
    def wait_for_jobs(self, job_ids, poll_interval=30, timeout_hours=4):
        """
        等待所有作业完成
        
        返回: dict — job_id → 下载URL列表
        """
        print(f"\n[HyP3] 等待 {len(job_ids)} 个作业完成...")
        start = time.time()
        completed = {}
        remaining = set(job_ids)
        
        while remaining and (time.time() - start) < timeout_hours * 3600:
            done = []
            for jid in list(remaining):
                status = self.check_job_status(jid)
                if status is None:
                    continue
                code = status.get("status_code", "")
                if code == "SUCCEEDED":
                    # 获取下载链接
                    files = status.get("files", [])
                    urls = [f["url"] for f in files if f.get("url")]
                    completed[jid] = {
                        "urls": urls,
                        "expiration": status.get("expiration_time", ""),
                    }
                    done.append(jid)
                    print(f"  [OK] {jid[:12]}... → 完成")
                elif code in ("FAILED", "CANCELLED"):
                    print(f"  [!!] {jid[:12]}... → {code}")
                    done.append(jid)
            
            for jid in done:
                remaining.discard(jid)
            
            if remaining:
                print(f"  ... 等待中 ({len(remaining)}/{len(job_ids)}), "
                      f"已过 {int(time.time()-start)//60} 分钟")
                time.sleep(poll_interval)
        
        if remaining:
            print(f"[!] {len(remaining)} 个作业未完成（超时）")
        
        return completed
    
    def download_results(self, completed_jobs, output_dir):
        """
        下载完成的结果文件
        
        返回: list[str] — 本地文件路径
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        downloaded = []
        
        for jid, info in completed_jobs.items():
            for url in info.get("urls", []):
                fname = url.split("/")[-1]
                if not fname.endswith((".tif", ".pdf", ".png", ".kml")):
                    continue
                local_path = out / fname
                if local_path.exists():
                    print(f"  [skip] {fname}")
                    downloaded.append(str(local_path))
                    continue
                
                try:
                    r = requests.get(url, stream=True, timeout=60)
                    if r.status_code == 200:
                        local_path.write_bytes(r.content)
                        print(f"  [↓] {fname} ({len(r.content)//1024} KB)")
                        downloaded.append(str(local_path))
                except Exception as e:
                    print(f"  [!] {fname}: {e}")
        
        return downloaded
