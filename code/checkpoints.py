"""Reproduce checkpoint values from the analysis panel and from the raw NOAA and EIA
files, then compute the proportional-trend contrasts."""
import sys, math, json
import numpy as np, pandas as pd
from core import ROOT, load, OLS, t_p_two, t_ppf
from statlib import norm_cdf

W = 80
def h(t): print('\n' + '=' * W + f'\n{t}\n' + '=' * W)
def C(*c): return np.column_stack([np.ones(len(c[0]))] + list(c))

CSV = ROOT / 'results' / 'analysis_panel.csv'
panel = pd.read_csv(CSV)
raw = load()

h('A. Does the supplied CSV match an independent reconstruction from raw files?')
cols = ['year', 'month', 'cdd', 'hdd', 'tavg', 'sales', 'customers', 'price']
a = panel[cols].sort_values(['year', 'month']).reset_index(drop=True)
b = raw[cols].sort_values(['year', 'month']).reset_index(drop=True)
print(f'  CSV rows {len(a)}   reconstruction rows {len(b)}')
same_shape = a.shape == b.shape
diffs = {}
for c in cols:
    if a[c].dtype.kind in 'fc':
        d = np.nanmax(np.abs(a[c].values - b[c].values)) if same_shape else np.nan
    else:
        d = int((a[c].values != b[c].values).sum()) if same_shape else np.nan
    diffs[c] = d
print('  max abs difference per column:', {k: (f'{v:.3g}' if isinstance(v, float) else v)
                                           for k, v in diffs.items()})
nan_match = (a.customers.isna().values == b.customers.isna().values).all()
print(f'  missing-value pattern for customers identical: {nan_match}')
print(f'  => CSV and raw reconstruction agree: '
      f'{same_shape and all((v == 0) or (isinstance(v, float) and v < 1e-9) for v in diffs.values()) and nan_match}')

df = raw.copy()
df['t_c_full'] = df.t - df.t.mean()

h('B. Panel-level checkpoints')
def ck(name, got, want, tol):
    ok = abs(got - want) <= tol
    print(f'  {name:<42} got {got:>18,.6f}   want {want:>18,.6f}   '
          f'{"MATCH" if ok else "**DIFFERS**"}')
    return ok
ck('N months', len(df), 436, 0)
print(f'  {"duplicate year-month keys":<42} {df.duplicated(["year","month"]).sum()}')
cnt = df.groupby('year').month.count(); fy = cnt[cnt == 12].index
ann = df[df.year.isin(fy)].groupby('year').agg(cdd=('cdd', 'sum'), hdd=('hdd', 'sum'),
                                               sales=('sales', 'sum'))
ANN_CDD, ANN_HDD, ANN_SALES = ann.cdd.mean(), ann.hdd.mean(), ann.sales.mean()
ck('mean annual CDD (complete years)', ANN_CDD, 1476.0, 1e-9)
ck('mean annual HDD (complete years)', ANN_HDD, 3303.194444444, 1e-6)
ck('mean annual sales', ANN_SALES, 51528766.0, 1e-6)

h('C. Model checkpoints (HAC: Bartlett, maxlag 12, no prewhite, no small-sample factor)')
mfe = pd.get_dummies(df.month.astype(int), prefix='m', drop_first=True).astype(float).values
m1 = OLS(df.sales.values, C(df.cdd.values), ['Intercept', 'CDD'], hac_lag=12)
m3 = OLS(df.sales.values, C(df.cdd.values, df.hdd.values, df.t_c_full.values),
         ['Intercept', 'CDD', 'HDD', 'Year'], hac_lag=12)
m4 = OLS(df.sales.values,
         np.column_stack([np.ones(len(df)), df.cdd, df.hdd, df.t_c_full, mfe]),
         ['Intercept', 'CDD', 'HDD', 'Year'] + [f'M{i}' for i in range(2, 13)], hac_lag=12)
ck('M1 CDD slope', m1.b[1], 2833.93016, 1e-4)
ck('M1 R2', m1.r2, 0.1404696, 1e-6)
ck('M1 HAC SE (CDD)', m1.hac_se[1], 217.93534, 1e-4)
ck('M3 CDD slope', m3.b[1], 7490.15609, 1e-4)
ck('M3 HDD slope', m3.b[2], 3596.11966, 1e-4)
ck('M3 trend', m3.b[3], 67579.90407, 1e-3)
ck('M3 R2', m3.r2, 0.8547042, 1e-6)
ck('M3 HAC SE (CDD)', m3.hac_se[1], 292.28477, 1e-4)
ck('M3 HAC SE (HDD)', m3.hac_se[2], 151.27603, 1e-4)
ck('M4 CDD slope', m4.b[1], 5269.49703, 1e-4)
ck('M4 HDD slope', m4.b[2], 3411.63099, 1e-4)
ck('M4 R2', m4.r2, 0.9083116, 1e-6)
ck('M4 HAC SE (CDD)', m4.hac_se[1], 641.23697, 1e-4)
ck('M4 HAC SE (HDD)', m4.hac_se[2], 306.23351, 1e-4)

def hacV(m, L=12):
    u = m.resid[:, None] * m.X; S = (u.T @ u) / m.n
    for l in range(1, L + 1):
        w = 1 - l / (L + 1); G = (u[l:].T @ u[:-l]) / m.n; S += w * (G + G.T)
    return m.n * m.XtXi @ S @ m.XtXi

for nm, m in [('M3', m3), ('M4', m4)]:
    bc, bh = m.b[1], m.b[2]
    Ec, Eh = bc * ANN_CDD, bh * ANN_HDD
    ratio = Eh / Ec
    V = hacV(m)
    g = np.zeros(m.k); g[1] = -Eh * ANN_CDD / Ec ** 2; g[2] = ANN_HDD / Ec
    se = math.sqrt(float(g @ V @ g))
    want_r, want_ci = ((1.07446197, (1.03970, 1.10922)) if nm == 'M3'
                       else (1.44890753, (1.12406, 1.77375)))
    ck(f'{nm} component ratio', ratio, want_r, 1e-6)
    ck(f'{nm} ratio CI lo (normal ref)', ratio - 1.959963985 * se, want_ci[0], 1e-4)
    ck(f'{nm} ratio CI hi (normal ref)', ratio + 1.959963985 * se, want_ci[1], 1e-4)

h('D. July-January checkpoints')
jul = df[df.month == 7][['year', 'sales']].rename(columns={'sales': 'jul'})
jan = df[df.month == 1][['year', 'sales']].rename(columns={'sales': 'jan'})
pr = jul.merge(jan, on='year'); d_ = (pr.jul - pr.jan).values; n_ = len(d_)
sd = d_.std(ddof=1); sem = sd / math.sqrt(n_); dof = n_ - 1
ck('mean paired difference', d_.mean(), 19123.58333, 1e-4)
ck('SD paired differences', sd, 590002.69306, 1e-4)
ck('two-sided paired p', t_p_two(d_.mean() / sem, dof), 0.846927, 1e-5)
from statlib import t_sf
for delta, want in [(0.3, 0.058682), (0.4, 0.017039), (0.5, 0.004074)]:
    D = delta * sd
    pmax = max(t_sf((d_.mean() + D) / sem, dof), 1 - t_sf((d_.mean() - D) / sem, dof))
    ck(f'TOST p at +/-{delta} SD', pmax, want, 1e-5)

h('E. Proportional-trend contrast, Models 7 and 8')
cov = df.dropna(subset=['customers']).copy()
pc = cov[cov.year >= 2008].copy()
tbar = pc.t.mean()
print(f'  per-customer window: n = {len(pc)}, {int(pc.year.iloc[0])}-{int(pc.month.iloc[0]):02d} '
      f'to {int(pc.year.iloc[-1])}-{int(pc.month.iloc[-1]):02d}')
print(f'  time origin = mean of the analysis window = {tbar:.6f}')
print(f'  (the CSV t_c column is centred on the FULL 1990-2026 window, mean '
      f'{df.t.mean():.4f}; it is NOT reused here)')
pc['tw'] = pc.t - tbar
mfe_pc = pd.get_dummies(pc.month.astype(int), prefix='m', drop_first=True).astype(float).values
X7 = np.column_stack([np.ones(len(pc)), pc.cdd, pc.hdd, pc.tw, pc.cdd * pc.tw, pc.hdd * pc.tw])
nm7 = ['Intercept', 'CDD', 'HDD', 'Year', 'CDDxYear', 'HDDxYear']
m7 = OLS(pc.spc.values, X7, nm7, hac_lag=12)
m8 = OLS(pc.spc.values, np.column_stack([X7, mfe_pc]),
         nm7 + [f'M{i}' for i in range(2, 13)], hac_lag=12)

def contrast(m):
    i_c, i_h = m.names.index('CDD'), m.names.index('HDD')
    i_x, i_hx = m.names.index('CDDxYear'), m.names.index('HDDxYear')
    bc, bh, bx, bhx = m.b[i_c], m.b[i_h], m.b[i_x], m.b[i_hx]
    g_ = bx / bc - bhx / bh
    grad = np.zeros(m.k)
    grad[i_c] = -bx / bc ** 2; grad[i_x] = 1 / bc
    grad[i_h] = bhx / bh ** 2; grad[i_hx] = -1 / bh
    V = hacV(m)
    se = math.sqrt(float(grad @ V @ grad))
    z = g_ / se
    return dict(g=g_, se=se, z=z,
                p_norm=2 * (1 - norm_cdf(abs(z))),
                p_t=t_p_two(z, m.dof),
                lo=g_ - 1.959963985 * se, hi=g_ + 1.959963985 * se, dof=m.dof)
res = {}
for nm, m, want in [('M7', m7, dict(g=-0.00297602, se=0.00258617, lo=-0.00804492,
                                    hi=0.00209288, p_norm=0.24984, p_t=0.25112)),
                    ('M8', m8, dict(g=-0.00675635, se=0.00283646, lo=-0.01231582,
                                    hi=-0.00119688, p_norm=0.01722, p_t=0.01814))]:
    c = contrast(m); res[nm] = c
    print(f'\n  {nm}: contrast g = {c["g"]:+.8f}/yr, HAC SE = {c["se"]:.8f}, '
          f'resid df = {c["dof"]}')
    print(f'      normal-ref 95% CI [{c["lo"]:+.8f}, {c["hi"]:+.8f}]')
    print(f'      normal-ref p = {c["p_norm"]:.5f}   |   t({c["dof"]})-ref p = {c["p_t"]:.5f}')
    for k in ['g', 'se', 'lo', 'hi', 'p_norm', 'p_t']:
        ok = abs(c[k] - want[k]) <= (2e-7 if k in ('g', 'se', 'lo', 'hi') else 2e-4)
        if not ok:
            print(f'      **{k} DIFFERS: got {c[k]:.8f} want {want[k]:.8f}**')
    print(f'      all six checkpoints match: '
          f'{all(abs(c[k]-want[k]) <= (2e-7 if k in ("g","se","lo","hi") else 2e-4) for k in want)}')

print('\n  Does the time origin change the contrast? (sanity: it must, via the main effects)')
pc['tf'] = pc.t - df.t.mean()
X7f = np.column_stack([np.ones(len(pc)), pc.cdd, pc.hdd, pc.tf, pc.cdd * pc.tf, pc.hdd * pc.tf])
m7f = OLS(pc.spc.values, X7f, nm7, hac_lag=12)
cf = contrast(m7f)
print(f'      interaction coefficients unchanged: '
      f'{np.allclose(m7.b[4:6], m7f.b[4:6])}')
print(f'      but main effects shift, so contrast becomes {cf["g"]:+.8f} '
      f'(p = {cf["p_norm"]:.4f}) instead of {res["M7"]["g"]:+.8f}')

json.dump({k: {kk: float(vv) for kk, vv in v.items()} for k, v in res.items()},
          open(ROOT / 'results' / 'contrasts.json', 'w'), indent=1)
print('\nwrote contrasts.json')
