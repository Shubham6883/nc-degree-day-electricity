import sys, math, calendar
from pathlib import Path
import numpy as np, pandas as pd
from statlib import t_sf, t_p_two, f_sf, t_ppf, norm_cdf

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data_raw'
STATE = '031'


def parse_climdiv(path, name, state=STATE):
    rows = []
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            p = line.split()
            idc = p[0]
            if idc[:3] != state:
                continue
            yr = int(idc[6:10])
            for m, v in enumerate([float(v) for v in p[1:13]], 1):
                rows.append((yr, m, np.nan if v <= -9998 else v))
    return pd.DataFrame(rows, columns=['year', 'month', name]).sort_values(['year', 'month'])


def load():
    cdd = parse_climdiv(f'{RAW}/climdiv-cddcst-v1.0.0-20260604', 'cdd')
    hdd = parse_climdiv(f'{RAW}/climdiv-hddcst-v1.0.0-20260604', 'hdd')
    tmp = parse_climdiv(f'{RAW}/climdiv-tmpcst-v1.0.0-20260604', 'tavg')
    clim = cdd.merge(hdd, on=['year', 'month']).merge(tmp, on=['year', 'month'])

    e = pd.concat([pd.read_csv(f'{RAW}/eia861m_1990_2009.csv', dtype=str, encoding='utf-8-sig'),
                   pd.read_csv(f'{RAW}/eia861m_2010_present.csv', dtype=str, encoding='utf-8-sig')],
                  ignore_index=True).drop_duplicates()
    e = e.rename(columns={'Year': 'year', 'Month': 'month', 'State': 'state', 'res_sales': 'sales',
                          'res_customers': 'customers', 'res_price': 'price'})
    e = e[e.state == 'NC'].copy()
    for c in ['year', 'month', 'sales', 'customers', 'price']:
        e[c] = pd.to_numeric(e[c].astype(str).str.replace(',', '', regex=False), errors='coerce')

    df = clim.merge(e[['year', 'month', 'sales', 'customers', 'price']], on=['year', 'month'])
    df = df.dropna(subset=['cdd', 'sales']).sort_values(['year', 'month']).reset_index(drop=True)
    df['season'] = df.month.map(lambda m: 'Winter' if m in (12, 1, 2) else 'Spring' if m in (3, 4, 5)
                                else 'Summer' if m in (6, 7, 8) else 'Fall')
    df['days'] = [calendar.monthrange(int(a), int(b))[1] for a, b in zip(df.year, df.month)]
    df['spc'] = df.sales / df.customers
    df['t'] = df.year + (df.month - 1) / 12
    return df


class OLS:
    def __init__(self, y, X, names=None, hac_lag=12):
        self.y = np.asarray(y, float)
        self.X = np.asarray(X, float)
        self.n, self.k = self.X.shape
        self.names = names or [f'x{i}' for i in range(self.k)]
        self.b, *_ = np.linalg.lstsq(self.X, self.y, rcond=None)
        self.resid = self.y - self.X @ self.b
        self.dof = self.n - self.k
        self.sse = self.resid @ self.resid
        self.sst = ((self.y - self.y.mean()) ** 2).sum()
        self.r2 = 1 - self.sse / self.sst
        self.adj_r2 = 1 - (1 - self.r2) * (self.n - 1) / self.dof
        self.XtXi = np.linalg.inv(self.X.T @ self.X)
        self.se = np.sqrt(np.diag(self.XtXi) * self.sse / self.dof)
        self.hac_se = self._hac(hac_lag)
        self.lag1 = np.corrcoef(self.resid[1:], self.resid[:-1])[0, 1] if self.n > 3 else np.nan
        self.dw = ((np.diff(self.resid)) ** 2).sum() / self.sse
        self.f = (self.sst - self.sse) / (self.k - 1) / (self.sse / self.dof) if self.k > 1 else np.nan
        self.f_p = f_sf(self.f, self.k - 1, self.dof) if self.k > 1 else np.nan

    def _hac(self, L):
        u = self.resid[:, None] * self.X
        S = (u.T @ u) / self.n
        for l in range(1, min(L, self.n - 1) + 1):
            w = 1 - l / (L + 1)
            G = (u[l:].T @ u[:-l]) / self.n
            S += w * (G + G.T)
        V = self.n * self.XtXi @ S @ self.XtXi
        d = np.diag(V).copy()
        d[d < 0] = np.nan
        return np.sqrt(d)

    def t(self, i, hac=False):
        return self.b[i] / (self.hac_se[i] if hac else self.se[i])

    def p(self, i, hac=False, one_sided=False):
        tv = self.t(i, hac)
        return t_sf(tv, self.dof) if one_sided else t_p_two(tv, self.dof)

    def ci(self, i, hac=False, level=.95):
        s = self.hac_se[i] if hac else self.se[i]
        c = t_ppf(1 - (1 - level) / 2, self.dof)
        return self.b[i] - c * s, self.b[i] + c * s

    def summary(self, label=''):
        out = [f'--- {label}  n={self.n} R2={self.r2:.4f} adjR2={self.adj_r2:.4f} DW={self.dw:.3f} lag1={self.lag1:.3f}']
        for i, nm in enumerate(self.names):
            lo, hi = self.ci(i)
            out.append(f'    {nm:<16} b={self.b[i]:>14,.1f}  SE={self.se[i]:>10,.1f}  HAC={self.hac_se[i]:>10,.1f}'
                       f'  t={self.t(i):>7.2f}  tHAC={self.t(i,True):>7.2f}  95%CI[{lo:,.1f}, {hi:,.1f}]')
        return '\n'.join(out)


def gls_ar1(y, X):
    y = np.asarray(y, float); X = np.asarray(X, float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    rho = 0.0
    for _ in range(50):
        r = y - X @ b
        rho_new = (r[1:] @ r[:-1]) / (r[:-1] @ r[:-1])
        yt = y[1:] - rho_new * y[:-1]
        Xt = X[1:] - rho_new * X[:-1]
        b_new, *_ = np.linalg.lstsq(Xt, yt, rcond=None)
        if abs(rho_new - rho) < 1e-10 and np.allclose(b, b_new, rtol=1e-12):
            b, rho = b_new, rho_new
            break
        b, rho = b_new, rho_new
    yt = y[1:] - rho * y[:-1]; Xt = X[1:] - rho * X[:-1]
    r = yt - Xt @ b
    s2 = (r @ r) / (len(yt) - X.shape[1])
    se = np.sqrt(np.diag(np.linalg.inv(Xt.T @ Xt)) * s2)
    return b, se, rho


def fmt_p(p, apa=True):
    if p < .001:
        return 'p < .001'
    return 'p = ' + f'{p:.3f}'.lstrip('0') if apa else f'p = {p:.3f}'


def nz(x, d=2):
    s = f'{x:.{d}f}'
    return s.replace('0.', '.', 1) if s.startswith('0.') else s.replace('-0.', '-.', 1)


def cm(x):
    return f'{round(x):,}'
