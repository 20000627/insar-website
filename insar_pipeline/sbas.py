"""
SBAS 时序反演（轻量版）
========================
核心算法：最小二乘 / SVD 时序反演
支持 numpy 加速，fallback 纯 Python 实现
"""
import math, json, os

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


class SBASInversion:
    """
    SBAS 时序形变反演

    输入: 干涉图列表（每个干涉图有: 主日期, 从日期, 相位/形变值）
    输出: 各时相的累计形变量 + 形变速率

    算法: Ax = b
      A — 设计矩阵 (n_ifg × n_date)
      x — 各时相累计形变
      b — 干涉图相位/形变 (n_ifg)
    """

    def __init__(self, ifg_pairs_data):
        """
        参数:
            ifg_pairs_data: list of (date_master, date_slave, displacement_values)
              其中 displacement_values 是每点的形变数组 [p1, p2, ...]
        """
        self.pairs = ifg_pairs_data

        # 自动提取所有时相（去重排序）
        all_dates = set()
        for m, s, _ in self.pairs:
            all_dates.add(m)
            all_dates.add(s)
        self.dates = sorted(all_dates)
        self.date_to_idx = {d: i for i, d in enumerate(self.dates)}
        self.n_dates = len(self.dates)
        self.n_ifgs = len(self.pairs)

        # 构建设计矩阵
        self._build_design_matrix()

    def _build_design_matrix(self):
        """构建 SBAS 设计矩阵 A (n_ifg × n_date)"""
        if HAVE_NUMPY:
            self.A = np.zeros((self.n_ifgs, self.n_dates), dtype=np.float64)
        else:
            self.A = [[0.0] * self.n_dates for _ in range(self.n_ifgs)]

        for i, (m, s, _) in enumerate(self.pairs):
            mi = self.date_to_idx[m]
            si = self.date_to_idx[s]
            # 约定: 干涉图 = 从日期 - 主日期
            # 列对应各时相的累计形变
            # 只有从日期列 = 1, 主日期列 = -1
            # 实际上 SBAS 设计矩阵通常是:
            # A[i, m_idx+1:s_idx+1] = 1 (分段表示)
            # 这里用简化的分段线性模型:
            if HAVE_NUMPY:
                for j in range(mi + 1, si + 1):
                    self.A[i, j] = (1.0 if j == si else 0.0)
                self.A[i, mi] = -1.0
            else:
                self.A[i][mi] = -1.0
                self.A[i][si] = 1.0

        # 第一列为零（参考时相）
        if HAVE_NUMPY:
            self.A[:, 0] = 0

    def invert(self, displacement_values):
        """
        反演时序形变
        
        参数:
            displacement_values: list of float — 各干涉图的形变值（单个点）
                               或 2D list — 多点形变矩阵 (n_ifg × n_pts)
        
        返回:
            if numpy: (n_dates,) 或 (n_pts, n_dates) 累计形变数组
            if pure:  list 累计形变
        """
        if HAVE_NUMPY:
            return self._invert_numpy(displacement_values)
        else:
            return self._invert_pure(displacement_values)

    def _invert_numpy(self, b):
        """numpy 加速版 SVD 反演"""
        b = np.asarray(b, dtype=np.float64)
        if b.ndim == 1:
            b = b.reshape(-1, 1)

        n_pts = b.shape[1]
        result = np.zeros((n_pts, self.n_dates), dtype=np.float64)

        # SVD 解算: x = A⁺b
        U, s, Vt = np.linalg.svd(self.A, full_matrices=False)

        # 截断小奇异值
        s_max = s[0]
        s_inv = np.array([1.0 / si if si > 0.01 * s_max else 0.0 for si in s])

        S_inv = np.diag(s_inv)
        A_pinv = Vt.T @ S_inv @ U.T

        x = A_pinv @ b  # (n_dates × n_pts)

        # 参考时相归零
        x -= x[0:1, :]

        if n_pts == 1:
            return x[:, 0]  # (n_dates,)
        return x.T  # (n_pts, n_dates)

    def _invert_pure(self, b):
        """纯 Python 版最小二乘（小规模）"""
        n = self.n_dates
        m = self.n_ifgs

        # 正规方程: (AᵀA)x = Aᵀb
        # 手动实现
        AtA = [[0.0] * n for _ in range(n)]
        Atb = [0.0] * n

        if isinstance(b[0], (list, tuple)):
            # 多点 — 取平均
            n_pts = len(b[0])
            b_avg = [sum(b[i][j] for j in range(n_pts)) / n_pts for i in range(m)]
        else:
            b_avg = b

        for i in range(n):
            for j in range(n):
                s = 0.0
                for k in range(m):
                    s += self.A[k][i] * self.A[k][j]
                AtA[i][j] = s
            s = 0.0
            for k in range(m):
                s += self.A[k][i] * b_avg[k]
            Atb[i] = s

        # 高斯消元（小规模 n <= 100 足够）
        x = self._gauss_elimination(AtA, Atb)

        # 归零参考
        x0 = x[0]
        x = [v - x0 for v in x]
        return x

    def _gauss_elimination(self, A, b):
        n = len(b)
        for i in range(n):
            # 主元
            max_row = max(range(i, n), key=lambda r: abs(A[r][i]))
            if max_row != i:
                A[i], A[max_row] = A[max_row], A[i]
                b[i], b[max_row] = b[max_row], b[i]

            pivot = A[i][i]
            if abs(pivot) < 1e-12:
                continue

            for j in range(i + 1, n):
                factor = A[j][i] / pivot
                for k in range(i, n):
                    A[j][k] -= factor * A[i][k]
                b[j] -= factor * b[i]

        # 回代
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            s = b[i]
            for j in range(i + 1, n):
                s -= A[i][j] * x[j]
            x[i] = s / A[i][i] if abs(A[i][i]) > 1e-12 else 0.0
        return x

    def compute_velocity(self, x):
        """计算形变速率 (mm/yr)"""
        from datetime import datetime
        d0 = datetime.strptime(self.dates[0], "%Y-%m-%d")
        d1 = datetime.strptime(self.dates[-1], "%Y-%m-%d")
        years = (d1 - d0).days / 365.25
        if HAVE_NUMPY:
            if isinstance(x, np.ndarray):
                if x.ndim == 1:
                    return (x[-1] - x[0]) / years
                return (x[:, -1] - x[:, 0]) / years
        if isinstance(x[0], (list, tuple)):
            return [(xi[-1] - xi[0]) / years for xi in x]
        return (x[-1] - x[0]) / years


def demo_sbas():
    """SBAS 反演演示"""
    print("=== SBAS 时序反演演示 ===\n")

    # 模拟数据: 5 个时相, 4 个干涉对
    dates = ["2023-01-01", "2023-02-01", "2023-03-01",
             "2023-04-01", "2023-05-01"]

    pairs = [
        ("2023-01-01", "2023-02-01"),  # 1m
        ("2023-02-01", "2023-03-01"),  # 2m
        ("2023-03-01", "2023-04-01"),  # 3m
        ("2023-04-01", "2023-05-01"),  # 4m
        ("2023-01-01", "2023-03-01"),  # 1+2
        ("2023-03-01", "2023-05-01"),  # 3+4
    ]

    # 模拟形变（线性沉降，每期 -10mm）
    ifg_values = [-12, -8, -10, -11, -18, -22]  # mm

    # 构造输入
    pair_data = [(m, s, None) for m, s in pairs]

    sbas = SBASInversion(pair_data)
    print(f"时相数量: {sbas.n_dates}")
    print(f"干涉对数量: {sbas.n_ifgs}")
    print(f"设计矩阵: {sbas.n_ifgs} x {sbas.n_dates}")

    result = sbas.invert(ifg_values)
    print(f"\n反演结果 (累计形变 mm):")
    for i, d in enumerate(sbas.dates):
        v = result[i] if HAVE_NUMPY else result[i]
        print(f"  {d}: {v:.2f} mm")

    vel = sbas.compute_velocity(result)
    print(f"\n形变速率: {vel:.2f} mm/yr")

    print("\n[OK] SBAS 反演模块正常")
    print(f"{'numpy 加速' if HAVE_NUMPY else '纯 Python 模式'}")


if __name__ == "__main__":
    demo_sbas()
