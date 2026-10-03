import sys, math, json, calendar, platform
import numpy as np, pandas as pd
from core import ROOT, load, OLS, t_p_two
from statlib import norm_cdf

SEED = 20260913
RNG = np.random.default_rng(SEED)
Z975 = 1.959963985
R = {'conventions': dict(hac_kernel='Bartlett', hac_maxlag=12, seed=SEED)}
W = 80
def h(t): print('\n' + '=' * W + f'\n{t}\n' + '=' * W)
def C(*c): return np.column_stack([np.ones(len(c[0]))] + list(c))
def put(k, v): R[k] = float(v) if isinstance(v, (np.floating, np.integer)) else v
def pnorm(z): return 2 * (1 - norm_cdf(abs(z)))


def hacV(m, L=12):
    u = m.resid[:, None] * m.X
    S = (u.T @ u) / m.n
    for l in range(1, L + 1):
        G = (u[l:].T @ u[:-l]) / m.n
        S += (1 - l / (L + 1)) * (G + G.T)
    return m.n * m.XtXi @ S @ m.XtXi


def wald(b, se):
    z = b / se
    return dict(b=b, se=se, z=z, p=pnorm(z), lo=b - Z975 * se, hi=b + Z975 * se)


def month_fe(d):
    return pd.get_dummies(d.month.astype(int), prefix='m', drop_first=True).astype(float).values


df = load()
df['t_c'] = df.t - df.t.mean()
df['ls'] = np.log(df.sales)
N = len(df); put('N', N)
cnt = df.groupby('year').month.count(); fy = cnt[cnt == 12].index
FULL = df.year.isin(fy).values
NY = len(fy)
ann = df[FULL].groupby('year').agg(cdd=('cdd', 'sum'), hdd=('hdd', 'sum'), sales=('sales', 'sum'))
ANN_CDD, ANN_HDD, ANN_SALES = ann.cdd.mean(), ann.hdd.mean(), ann.sales.mean()
for k, v in [('ann_cdd', ANN_CDD), ('ann_hdd', ANN_HDD), ('ann_sales', ANN_SALES),
             ('n_complete_years', NY), ('hdd_cdd_ratio', ANN_HDD / ANN_CDD),
             ('mean_sales', df.sales.mean()), ('sd_sales', df.sales.std(ddof=1)),
             ('min_sales', df.sales.min()), ('max_sales', df.sales.max()),
             ('zero_cdd_n', int((df.cdd == 0).sum()))]:
    put(k, v)
for v in ['cdd', 'hdd', 'tavg']:
    put(f'mean_{v}', df[v].mean()); put(f'sd_{v}', df[v].std(ddof=1))
    put(f'max_{v}', df[v].max()); put(f'min_{v}', df[v].min())
R['season'] = {s: dict(n=int((df.season == s).sum()), mean=df[df.season == s].sales.mean(),
                       sd=df[df.season == s].sales.std(ddof=1))
               for s in ['Winter', 'Spring', 'Summer', 'Fall']}
put('sales_first_year', ann.sales.iloc[0]); put('sales_last_year', ann.sales.iloc[-1])

h('1. Customer counts')
cov = df.dropna(subset=['customers']).sort_values(['year', 'month']).reset_index(drop=True)
seq = cov.year * 12 + cov.month
put('cust_contiguous', bool((seq.diff().dropna() == 1).all()))
cov['mom'] = cov.customers.pct_change() * 100
big = cov[cov.mom.abs() > 2]
R['cust_anomalies'] = [dict(year=int(r.year), month=int(r.month), customers=float(r.customers),
                            mom=float(r.mom)) for _, r in big.iterrows()]
put('cust_jump_pct', float(cov.loc[(cov.year == 2008) & (cov.month == 1), 'mom'].iloc[0]))
put('cust_other_max_pct', float(cov[~((cov.year == 2008) & (cov.month == 1))].mom.abs().max()))
put('cust_excl_cluster_max', float(cov[~cov.index.isin(big.index)].mom.abs().max()))
c2 = cov[(cov.year * 100 + cov.month).between(202105, 202204)]
put('cluster_net_pct', float(100 * (c2.customers.iloc[-1] / c2.customers.iloc[0] - 1)))
j = df[df.month == 1][['year', 'sales', 'customers']].copy()
j['yoy_s'] = j.sales.pct_change() * 100; j['yoy_c'] = j.customers.pct_change() * 100
r08 = j[j.year == 2008].iloc[0]
put('jan08_yoy_sales', float(r08.yoy_s)); put('jan08_yoy_cust', float(r08.yoy_c))
for a in R['cust_anomalies']:
    print(f'  {a["year"]}-{a["month"]:02d}  {a["mom"]:+6.2f}%   {a["customers"]:>12,.0f}')
print(f'  January 2008 year over year: sales {r08.yoy_s:+.1f}%, customers {r08.yoy_c:+.1f}%')

pc = cov[cov.year >= 2008].copy().reset_index(drop=True)
pc['tw'] = pc.t - pc.t.mean()
pc['lspc'] = np.log(pc.spc)
put('pc_tbar', pc.t.mean()); put('n_pc', len(pc)); put('n_pc_all', len(cov))
put('cust_first', pc.customers.iloc[0]); put('cust_last', pc.customers.iloc[-1])
put('spc_first_year', pc[pc.year == 2008].spc.sum())
put('spc_last_year', pc[pc.year == 2025].spc.sum())
put('spc_change_pct', 100 * (R['spc_last_year'] / R['spc_first_year'] - 1))
print(f'  sales per customer, 2008 {R["spc_first_year"]:.2f} MWh, 2025 {R["spc_last_year"]:.2f} MWh '
      f'({R["spc_change_pct"]:+.1f}%)')


h('2. Total-sales models (outcome: log monthly sales)')
mfe = month_fe(df)
specs = {
    'M1': (C(df.cdd.values), ['Intercept', 'CDD']),
    'M2': (C(df.cdd.values, df.hdd.values), ['Intercept', 'CDD', 'HDD']),
    'M3': (C(df.cdd.values, df.hdd.values, df.t_c.values), ['Intercept', 'CDD', 'HDD', 'Year']),
    'M4': (np.column_stack([np.ones(N), df.cdd, df.hdd, df.t_c, mfe]),
           ['Intercept', 'CDD', 'HDD', 'Year'] + [f'M{i}' for i in range(2, 13)]),
}
fits, models = {}, {}
for k, (X, nm) in specs.items():
    m = OLS(df.ls.values, X, nm); fits[k] = m
    V = hacV(m); hse = np.sqrt(np.diag(V))
    d = dict(n=m.n, r2=m.r2, dw=m.dw, coef={})
    for i, v in enumerate(nm[:4]):
        w_ = wald(m.b[i], hse[i]); w_['ols_se'] = m.se[i]
        if v == 'Intercept':
            d['coef'][v] = w_; continue

        w_['pct100'] = 100 * (math.exp(100 * m.b[i]) - 1)
        w_['pct100_lo'] = 100 * (math.exp(100 * w_['lo']) - 1)
        w_['pct100_hi'] = 100 * (math.exp(100 * w_['hi']) - 1)
        w_['pct1'] = 100 * (math.exp(m.b[i]) - 1)
        d['coef'][v] = w_
    models[k] = d
    print(f'  {k} R2={m.r2:.4f} DW={m.dw:.3f}  ' + '  '.join(
        f'{v}: {d["coef"][v]["pct100"]:.2f}%/100 (HAC SE {d["coef"][v]["se"]:.2e})'
        for v in ['CDD', 'HDD'] if v in d['coef']))
put('m1_to_m3_cdd_pct', 100 * (fits['M3'].b[1] / fits['M1'].b[1] - 1))
R['models'] = models


h('3. Do the degree-day slopes change over the 36 years?')
Xint = C(df.cdd.values, df.hdd.values, df.t_c.values, df.cdd * df.t_c, df.hdd * df.t_c)
drift = {}
for lab, y in [('levels', df.sales.values), ('logs', df.ls.values)]:
    m = OLS(y, Xint, ['c', 'CDD', 'HDD', 'Y', 'CDDxY', 'HDDxY']); se = np.sqrt(np.diag(hacV(m)))
    t0, t1 = 1990.5 - df.t.mean(), 2025.5 - df.t.mean()
    drift[lab] = dict(z_cdd=m.b[4] / se[4], z_hdd=m.b[5] / se[5],
                      p_cdd=pnorm(m.b[4] / se[4]), p_hdd=pnorm(m.b[5] / se[5]),
                      cdd_1990=m.b[1] + m.b[4] * t0, cdd_2025=m.b[1] + m.b[4] * t1,
                      hdd_1990=m.b[2] + m.b[5] * t0, hdd_2025=m.b[2] + m.b[5] * t1)
    dd = drift[lab]
    dd['cdd_change_pct'] = 100 * (dd['cdd_2025'] / dd['cdd_1990'] - 1)
    dd['hdd_change_pct'] = 100 * (dd['hdd_2025'] / dd['hdd_1990'] - 1)
    print(f'  {lab:<6} CDDxYear z={dd["z_cdd"]:6.2f} p={dd["p_cdd"]:.4f}   '
          f'HDDxYear z={dd["z_hdd"]:6.2f} p={dd["p_hdd"]:.4f}   '
          f'CDD slope 1990->2025 {dd["cdd_change_pct"]:+.0f}%  HDD {dd["hdd_change_pct"]:+.0f}%')
R['drift'] = drift


h('4. Heating and cooling components')
S_ = df.sales.values; CDD_ = df.cdd.values; HDD_ = df.hdd.values


def comps(bc, bh, cdd=CDD_, hdd=HDD_):
    ec = (S_ * (1 - np.exp(-bc * cdd)))[FULL].sum() / NY
    eh = (S_ * (1 - np.exp(-bh * hdd)))[FULL].sum() / NY
    dc = (S_ * cdd * np.exp(-bc * cdd))[FULL].sum() / NY
    dh = (S_ * hdd * np.exp(-bh * hdd))[FULL].sum() / NY
    return ec, eh, dc, dh


def block_boot(m, i, jx, B=4000, L=12):
    X, y = m.X, m.y
    nb = int(np.ceil(m.n / L)); starts = np.arange(m.n - L + 1)
    out = []
    for _ in range(B):
        s = RNG.choice(starts, nb, replace=True)
        idx = np.concatenate([np.arange(q, q + L) for q in s])[:m.n]
        b, *_ = np.linalg.lstsq(X[idx], y[idx], rcond=None)
        if b[i] <= 0 or b[jx] <= 0: continue
        ec, eh, _, _ = comps(b[i], b[jx])
        out.append(eh / ec)
    return np.array(out)


comp = {}
for key in ['M3', 'M4']:
    m = fits[key]; V = hacV(m)
    bc, bh = m.b[1], m.b[2]
    ec, eh, dc, dh = comps(bc, bh)
    ratio = eh / ec
    g = np.zeros(m.k); g[1] = -eh * dc / ec ** 2; g[2] = dh / ec
    se = math.sqrt(float(g @ V @ g))
    bs = block_boot(m, 1, 2)
    comp[key] = dict(e_cool=ec, e_heat=eh, ratio=ratio, ratio_se=se,
                     lo=ratio - Z975 * se, hi=ratio + Z975 * se,
                     share_cool=ec / ANN_SALES, share_heat=eh / ANN_SALES,
                     remainder=ANN_SALES - ec - eh,
                     boot_lo=float(np.percentile(bs, 2.5)), boot_hi=float(np.percentile(bs, 97.5)),
                     boot_n=int(len(bs)), corr=float(V[1, 2] / math.sqrt(V[1, 1] * V[2, 2])))
    c = comp[key]
    print(f'  {key}: cooling {ec/1e6:.2f}M MWh ({c["share_cool"]:.1%})  heating {eh/1e6:.2f}M '
          f'({c["share_heat"]:.1%})  ratio {ratio:.3f}  delta CI [{c["lo"]:.3f}, {c["hi"]:.3f}]  '
          f'boot [{c["boot_lo"]:.3f}, {c["boot_hi"]:.3f}]')
R['comp'] = comp

h('5. Robustness of the heating-to-cooling ratio (Model 3 form unless noted)')
sens = {}
def ratio_from(m, i=1, jx=2, cdd=CDD_, hdd=HDD_):
    ec, eh, _, _ = comps(m.b[i], m.b[jx], cdd, hdd); return eh / ec
t2 = df.t_c.values ** 2
sens['quadratic_trend'] = ratio_from(OLS(df.ls.values, C(CDD_, HDD_, df.t_c.values, t2)))
days = df.days.values

md = OLS(np.log(S_ / days), C(CDD_ / days, HDD_ / days, df.t_c.values))
ec = (S_ * (1 - np.exp(-md.b[1] * CDD_ / days)))[FULL].sum()
eh = (S_ * (1 - np.exp(-md.b[2] * HDD_ / days)))[FULL].sum()
sens['per_day'] = eh / ec
ml3 = OLS(df.ls.values[:-3], C(CDD_[:-3], HDD_[:-3], df.t_c.values[:-3]))
sens['drop_last3'] = ratio_from(ml3)
for key, X in [('levels_M3', specs['M3'][0]), ('levels_M4', specs['M4'][0])]:
    m = OLS(S_, X)
    sens[key] = (m.b[2] * ANN_HDD) / (m.b[1] * ANN_CDD)

best = None
T = df.tavg.values
for tc in np.arange(55, 72.01, .5):
    for th in np.arange(45, tc + .01, .5):
        xc = np.maximum(T - tc, 0) * days; xh = np.maximum(th - T, 0) * days
        m = OLS(df.ls.values, C(xc, xh, df.t_c.values), hac_lag=1)
        if best is None or m.sse < best[0]:
            best = (m.sse, tc, th, m, xc, xh)
_, tc, th, mh, xc, xh = best
ec = (S_ * (1 - np.exp(-mh.b[1] * xc)))[FULL].sum(); eh = (S_ * (1 - np.exp(-mh.b[2] * xh)))[FULL].sum()
sens['hinge'] = eh / ec
put('hinge_cool', tc); put('hinge_heat', th); put('hinge_r2', mh.r2)
R['sens'] = sens
for k, v in sens.items():
    print(f'  {k:<16} ratio {v:.3f}')
print(f'  hinge thresholds: cooling {tc:.1f} F, heating {th:.1f} F, R2 {mh.r2:.3f} '
      f'(Model 3: {fits["M3"].r2:.3f})')


h('6. Per-customer models, January 2008 to April 2026')
mfe_pc = month_fe(pc)
Xp = np.column_stack([np.ones(len(pc)), pc.cdd, pc.hdd, pc.tw, pc.cdd * pc.tw, pc.hdd * pc.tw])
nmp = ['Intercept', 'CDD', 'HDD', 'Year', 'CDDxYear', 'HDDxYear']
pspec = {'M5': (pc.spc.values, Xp), 'M6': (pc.spc.values, np.column_stack([Xp, mfe_pc])),
         'M7': (pc.lspc.values, Xp), 'M8': (pc.lspc.values, np.column_stack([Xp, mfe_pc]))}
lo_t, hi_t = pc.tw.min(), pc.tw.max()


def pc_fit(y, X, L=12):
    m = OLS(y, X); V = hacV(m, L); se = np.sqrt(np.diag(V))
    out = dict(n=m.n, r2=m.r2, dw=m.dw, coef={})
    for i, v in enumerate(nmp):
        out['coef'][v] = wald(m.b[i], se[i]); out['coef'][v]['ols_p'] = m.p(i)
    out['pct_cdd'] = 100 * ((m.b[1] + m.b[4] * hi_t) / (m.b[1] + m.b[4] * lo_t) - 1)
    out['pct_hdd'] = 100 * ((m.b[2] + m.b[5] * hi_t) / (m.b[2] + m.b[5] * lo_t) - 1)
    d = np.zeros(m.k); d[4] = 1; d[5] = -1
    out['diff'] = wald(m.b[4] - m.b[5], math.sqrt(float(d @ V @ d)))
    return out, m


pmods = {}
for k, (y, X) in pspec.items():
    pmods[k], m = pc_fit(y, X)
    o = pmods[k]
    print(f'  {k} R2={o["r2"]:.3f}  CDDxYear p={o["coef"]["CDDxYear"]["p"]:.4f} '
          f'({o["pct_cdd"]:+.1f}%)  HDDxYear p={o["coef"]["HDDxYear"]["p"]:.4f} '
          f'({o["pct_hdd"]:+.1f}%)  cool-heat p={o["diff"]["p"]:.4f}')
R['pmods'] = pmods
lagsweep = {}
for k, (y, X) in pspec.items():
    lagsweep[k] = {str(L): pc_fit(y, X, L)[0]['coef']['CDDxYear']['p'] for L in [3, 6, 12, 18, 24]}
    print(f'  {k} CDDxYear p across lags 3-24: ' +
          ', '.join(f'{v:.4f}' for v in lagsweep[k].values()))
R['lagsweep'] = lagsweep
for k in ['M5', 'M6', 'M7', 'M8']:
    put(f'{k}_lagmax', max(lagsweep[k].values())); put(f'{k}_lagmin', min(lagsweep[k].values()))

h('7. Estimation window')
anom = (cov.year * 100 + cov.month).isin([202106, 202111, 202112, 202201, 202202])
excl = {}
for lab, sub in [('2008-2026', cov[cov.year >= 2008]),
                 ('2007-2026', cov),
                 ('2009-2026', cov[cov.year >= 2009]),
                 ('2008-2026 without 2021-22', cov[(cov.year >= 2008) & (~anom)])]:
    s = sub.copy(); s['tw'] = s.t - s.t.mean()
    X = np.column_stack([np.ones(len(s)), s.cdd, s.hdd, s.tw, s.cdd * s.tw, s.hdd * s.tw])
    XF = np.column_stack([X, month_fe(s)])
    lo_, hi_ = s.tw.min(), s.tw.max()
    row = dict(n=len(s))
    for tag, y, XX in [('lvl', s.spc.values, X), ('lvlfe', s.spc.values, XF),
                       ('log', np.log(s.spc.values), X), ('logfe', np.log(s.spc.values), XF)]:
        m = OLS(y, XX); se = np.sqrt(np.diag(hacV(m)))
        row[f'p_{tag}'] = pnorm(m.b[4] / se[4])
        row[f'pct_{tag}'] = 100 * ((m.b[1] + m.b[4] * hi_) / (m.b[1] + m.b[4] * lo_) - 1)
    excl[lab] = row
    print(f'  {lab:<28} n={len(s)}  levels {row["pct_lvl"]:+.1f}% (p {row["p_lvl"]:.4f}) / '
          f'{row["pct_lvlfe"]:+.1f}% (p {row["p_lvlfe"]:.4f})   logs {row["pct_log"]:+.1f}% '
          f'(p {row["p_log"]:.4f}) / {row["pct_logfe"]:+.1f}% (p {row["p_logfe"]:.4f})')
R['exclusion'] = excl

h('8. Annual per-customer slopes (for the figure)')
rows = []
for yr, g_ in pc.groupby('year'):
    if len(g_) < 12: continue
    m = OLS(g_.spc.values, C(g_.cdd.values, g_.hdd.values))
    rows.append(dict(year=int(yr), b_cdd=m.b[1], se_cdd=m.se[1], b_hdd=m.b[2], se_hdd=m.se[2],
                     r2=m.r2))
pd.DataFrame(rows).to_csv(ROOT / 'results' / 'annual_slopes.csv', index=False)
print(f'  wrote annual_slopes.csv ({len(rows)} years)')

h('9. Diagnostics and other checks')
for key in ['M1', 'M3', 'M4']:
    r = fits[key].resid; rm = r - r.mean()
    put(f'acf1_{key}', float(np.corrcoef(r[1:], r[:-1])[0, 1]))
    put(f'acf12_{key}', float((rm[12:] * rm[:-12]).sum() / (rm ** 2).sum()))
    print(f'  {key} residual autocorrelation: lag 1 {R[f"acf1_{key}"]:.2f}, '
          f'lag 12 {R[f"acf12_{key}"]:.2f}')
bwq = {}
for k in ['M3', 'M4']:
    bwq[k] = {v: [float(np.sqrt(np.diag(hacV(fits[k], L)))[i]) for L in [3, 6, 12, 18, 24]]
              for v, i in [('CDD', 1), ('HDD', 2)]}
    for v in ['CDD', 'HDD']:
        b = fits[k].b[1 if v == 'CDD' else 2]
        put(f'{k}_{v}_zmin', min(b / s for s in bwq[k][v]))
R['bw_sweep'] = bwq
tv = df.t_c.values
def det(v):
    X = C(tv); b, *_ = np.linalg.lstsq(X, v, rcond=None); return v - X @ b
y_ = df.ls.values
put('r_all', float(np.corrcoef(CDD_, y_)[0, 1]))
put('r_detrend', float(np.corrcoef(det(CDD_), det(y_))[0, 1]))
put('r_diff1', float(np.corrcoef(np.diff(CDD_), np.diff(y_))[0, 1]))
put('r_diff12', float(np.corrcoef(CDD_[12:] - CDD_[:-12], y_[12:] - y_[:-12])[0, 1]))
for k, v in [('r_all', 'raw'), ('r_detrend', 'detrended'), ('r_diff1', '1st diff'),
             ('r_diff12', '12-month diff')]:
    print(f'  corr(CDD, log sales) {v:<14} {R[k]:.3f}')

R['software'] = dict(python=sys.version.split()[0], numpy=np.__version__, pandas=pd.__version__)
R['heating'] = dict(nc_central_heat_pump_pct=38, sc=41, al=39, tn=35, fl=31, nc_furnace_pct=50)
df.drop(columns=['ls']).to_csv(ROOT / 'results' / 'analysis_panel.csv', index=False)
json.dump(R, open(ROOT / 'results' / 'results.json', 'w'), indent=1, default=float)
print(f'\nwrote results.json and analysis_panel.csv')
