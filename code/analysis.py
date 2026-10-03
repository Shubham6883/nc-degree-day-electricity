"""Main analysis for the NC degree-day study.

Conventions:
  HAC   Newey-West, Bartlett kernel, maxlag 12 months, no prewhitening,
        no finite-sample covariance multiplier.
  REF   Robust Wald statistics are referred to the standard normal distribution;
        the residual-df t reference is also reported where it matters.
  SEED  numpy default_rng(20260913) for all resampling.
"""
import sys, math, json, itertools, calendar, platform
import numpy as np, pandas as pd
from core import ROOT, load, OLS, gls_ar1, t_p_two, t_ppf, t_sf
from statlib import norm_cdf

SEED = 20260913
RNG = np.random.default_rng(SEED)
Z975 = 1.959963985
R = {'conventions': dict(hac_kernel='Bartlett', hac_maxlag=12, prewhite=False,
                         small_sample_multiplier=False, wald_reference='standard normal',
                         seed=SEED)}
W = 80
def h(t): print('\n' + '=' * W + f'\n{t}\n' + '=' * W)
def C(*c): return np.column_stack([np.ones(len(c[0]))] + list(c))
def put(k, v): R[k] = float(v) if isinstance(v, (np.floating, np.integer)) else v

def chi2_sf(x, df):
    """Upper tail. Exact closed forms for df = 1, 2, 3 (all that is needed here)."""
    if df == 1: return 2 * (1 - norm_cdf(math.sqrt(x)))
    if df == 2: return math.exp(-x / 2)
    if df == 3: return 2 * (1 - norm_cdf(math.sqrt(x))) + math.sqrt(2 * x / math.pi) * math.exp(-x / 2)
    raise ValueError('df not supported')
assert abs(chi2_sf(3.841459, 1) - .05) < 1e-6
assert abs(chi2_sf(5.991465, 2) - .05) < 1e-6
assert abs(chi2_sf(7.814728, 3) - .05) < 1e-6
print('chi2_sf self-check passed at df = 1, 2, 3 (published 5% critical points)')

df = load()
df['t_c'] = df.t - df.t.mean()
N = len(df); put('N', N)
cnt = df.groupby('year').month.count(); fy = cnt[cnt == 12].index
ann = df[df.year.isin(fy)].groupby('year').agg(cdd=('cdd', 'sum'), hdd=('hdd', 'sum'),
                                               sales=('sales', 'sum'))
ANN_CDD, ANN_HDD, ANN_SALES = ann.cdd.mean(), ann.hdd.mean(), ann.sales.mean()
for k, v in [('ann_cdd', ANN_CDD), ('ann_hdd', ANN_HDD), ('ann_sales', ANN_SALES),
             ('n_complete_years', len(fy)), ('hdd_cdd_ratio', ANN_HDD / ANN_CDD),
             ('mean_sales', df.sales.mean()), ('sd_sales', df.sales.std(ddof=1)),
             ('min_sales', df.sales.min()), ('max_sales', df.sales.max()),
             ('zero_cdd_n', int((df.cdd == 0).sum())),
             ('jan_cdd', df[df.month == 1].cdd.mean()),
             ('jul_cdd', df[df.month == 7].cdd.mean())]:
    put(k, v)
for v in ['cdd', 'hdd', 'tavg']:
    put(f'mean_{v}', df[v].mean()); put(f'sd_{v}', df[v].std(ddof=1))
    put(f'max_{v}', df[v].max()); put(f'min_{v}', df[v].min())
R['season'] = {s: dict(n=int((df.season == s).sum()), mean=df[df.season == s].sales.mean(),
                       sd=df[df.season == s].sales.std(ddof=1))
               for s in ['Winter', 'Spring', 'Summer', 'Fall']}

def hacV(m, L=12, blocks=None, cal_index=None):
    """Newey-West, Bartlett kernel, maximum lag L.

    blocks     lag products only within a block (retained for comparison).
    cal_index  integer calendar-month index per observation. Lag products are
               formed at ACTUAL calendar distance, so every ordered pair whose
               true separation is l months contributes at weight 1 - l/(L+1),
               including pairs that straddle a gap in a filtered series.
    """
    u = m.resid[:, None] * m.X
    S = (u.T @ u) / m.n
    if cal_index is not None:
        d = np.asarray(cal_index)[:, None] - np.asarray(cal_index)[None, :]
        for l in range(1, L + 1):
            I, J = np.where(d == l)
            if len(I) == 0: continue
            G = (u[I].T @ u[J]) / m.n
            S += (1 - l / (L + 1)) * (G + G.T)
        return m.n * m.XtXi @ S @ m.XtXi
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        a, b = u[l:], u[:-l]
        if blocks is not None:
            keep = (blocks[l:] == blocks[:-l])
            a, b = a[keep], b[keep]
            if len(a) == 0: continue
        G = (a.T @ b) / m.n
        S += w * (G + G.T)
    return m.n * m.XtXi @ S @ m.XtXi

def wald(b, se, dof):
    z = b / se
    return dict(b=b, se=se, z=z, p_norm=2 * (1 - norm_cdf(abs(z))), p_t=t_p_two(z, dof),
                lo=b - Z975 * se, hi=b + Z975 * se)

h('1. Customer-count audit')
cov = df.dropna(subset=['customers']).sort_values(['year', 'month']).reset_index(drop=True)
seq = cov.year * 12 + cov.month
put('cust_contiguous', bool((seq.diff().dropna() == 1).all()))
cov['mom'] = cov.customers.pct_change() * 100
big = cov[cov.mom.abs() > 1.5]
R['cust_anomalies'] = [dict(year=int(r.year), month=int(r.month), customers=float(r.customers),
                            mom=float(r.mom)) for _, r in big.iterrows()]
put('cust_jump_pct', float(cov.loc[(cov.year == 2008) & (cov.month == 1), 'mom'].iloc[0]))
others = cov[~((cov.year == 2008) & (cov.month == 1))].mom.abs()
put('cust_other_max_pct', float(others.max()))
put('cust_n_over2', int((cov.mom.abs() > 2).sum()))
put('cust_excl_cluster_max', float(cov[~cov.index.isin(big.index)].mom.abs().max()))
print(f'  contiguous monthly series: {R["cust_contiguous"]}   n = {len(cov)}')
print(f'  Jan-2008 step {R["cust_jump_pct"]:+.2f}%')
print(f'  largest |change| EXCLUDING Jan-2008: {R["cust_other_max_pct"]:.2f}%')
print(f'  months with |change| > 2%: {R["cust_n_over2"]} — listed:')
for a in R['cust_anomalies']:
    print(f'      {a["year"]}-{a["month"]:02d}  {a["mom"]:+6.2f}%   {a["customers"]:>12,.0f}')
print(f'  largest |change| excluding Jan-2008 and the 2021-22 cluster: '
      f'{R["cust_excl_cluster_max"]:.2f}%')
c2 = cov[(cov.year * 100 + cov.month).between(202105, 202204)]
put('cluster_net_pct', float(100 * (c2.customers.iloc[-1] / c2.customers.iloc[0] - 1)))
print(f'  2021-05 -> 2022-04 NET change {R["cluster_net_pct"]:+.2f}% over 12 months: the cluster')
print('  oscillates around the trend rather than stepping to a new level.')
j = df[df.month == 1][['year', 'sales', 'customers']].copy()
j['yoy_s'] = j.sales.pct_change() * 100; j['yoy_c'] = j.customers.pct_change() * 100
r08 = j[j.year == 2008].iloc[0]
put('jan08_yoy_sales', float(r08.yoy_s)); put('jan08_yoy_cust', float(r08.yoy_c))
print(f'  January 2008 year-over-year: sales {r08.yoy_s:+.1f}%, customers {r08.yoy_c:+.1f}%')
print('  -> only the denominator moves, so sales-per-customer is discontinuous at that')
print('     point whatever the cause. The 2008 exclusion does not depend on diagnosing it.')

pc = cov[cov.year >= 2008].copy()
TBAR = pc.t.mean()
pc['tw'] = pc.t - TBAR
put('pc_tbar', TBAR); put('n_pc', len(pc)); put('n_pc_all', len(cov))
put('pc_y0', int(pc.year.iloc[0])); put('pc_m0', int(pc.month.iloc[0]))
put('pc_y1', int(pc.year.iloc[-1])); put('pc_m1', int(pc.month.iloc[-1]))
put('pc_span_years', (pc.t.max() - pc.t.min()))
put('cust_first', pc.customers.iloc[0]); put('cust_last', pc.customers.iloc[-1])
put('price_first', pc.price.iloc[0]); put('price_last', pc.price.iloc[-1])

h('2. Specification ladder')
models = {}
mfe = pd.get_dummies(df.month.astype(int), prefix='m', drop_first=True).astype(float).values
specs = {
    'M1': (C(df.cdd.values), ['Intercept', 'CDD'], 'Sales ~ CDD'),
    'M2': (C(df.cdd.values, df.hdd.values), ['Intercept', 'CDD', 'HDD'], 'Sales ~ CDD + HDD'),
    'M3': (C(df.cdd.values, df.hdd.values, df.t_c.values), ['Intercept', 'CDD', 'HDD', 'Year'],
           'Sales ~ CDD + HDD + linear year'),
    'M4': (np.column_stack([np.ones(N), df.cdd, df.hdd, df.t_c, mfe]),
           ['Intercept', 'CDD', 'HDD', 'Year'] + [f'M{i}' for i in range(2, 13)],
           'Sales ~ CDD + HDD + year + calendar-month effects'),
}
fits = {}
for k, (X, nm, lab) in specs.items():
    m = OLS(df.sales.values, X, nm, hac_lag=12); fits[k] = m
    V = hacV(m); hse = np.sqrt(np.diag(V))
    d = dict(label=lab, n=m.n, k=m.k, r2=m.r2, adj_r2=m.adj_r2, dw=m.dw, coef={})
    for i, v in enumerate(nm):
        w_ = wald(m.b[i], hse[i], m.dof)
        w_.update(ols_se=m.se[i], ols_p=m.p(i))
        d['coef'][v] = w_
    models[k] = d
    print(f'  {k:<3} R2={m.r2:.4f}  DW={m.dw:.3f}  ' +
          '  '.join(f'{v}={m.b[nm.index(v)]:,.0f}' for v in ['CDD', 'HDD', 'Year'] if v in nm))
cool = df[df.month.isin([5, 6, 7, 8, 9])].sort_values(['year', 'month']).reset_index(drop=True)
m5 = OLS(cool.sales.values, C(cool.cdd.values), ['Intercept', 'CDD'], hac_lag=12)
models['M5'] = dict(label='Cooling season (May-Sep): Sales ~ CDD', n=m5.n, r2=m5.r2,
                    dw=m5.dw, coef={})
R['models'] = models

h('3. Model 5 inference: naive HAC vs block-aware HAC')
cal5 = (cool.year * 12 + cool.month).values
V_naive = hacV(m5); V_block = hacV(m5, blocks=cool.year.values)
V_cal = hacV(m5, cal_index=cal5)
put('m5_hac_naive_se', float(np.sqrt(np.diag(V_naive))[1]))
put('m5_hac_block_se', float(np.sqrt(np.diag(V_block))[1]))
put('m5_hac_cal_se', float(np.sqrt(np.diag(V_cal))[1]))
put('m5_ols_se', float(m5.se[1])); put('m5_slope', float(m5.b[1])); put('m5_r2', float(m5.r2))
d5 = cal5[:, None] - cal5[None, :]
elig = (d5 >= 1) & (d5 <= 12)
same = cool.year.values[:, None] == cool.year.values[None, :]
put('m5_pairs_total', int(elig.sum()))
put('m5_pairs_cross', int((elig & ~same).sum()))
put('m5_pairs_within', int((elig & same).sum()))
models['M5']['coef']['CDD'] = wald(m5.b[1], R['m5_hac_cal_se'], m5.dof)
print(f'  slope {m5.b[1]:,.1f}  OLS SE {m5.se[1]:,.1f}')
print(f'  naive HAC SE {R["m5_hac_naive_se"]:,.2f}  <- treats consecutive filtered rows as '
      '1 month apart (invalid)')
print(f'  within-year block HAC SE {R["m5_hac_block_se"]:,.2f}  <- drops eligible cross-year '
      'pairs')
print(f'  calendar-distance HAC SE {R["m5_hac_cal_se"]:,.2f}  <- REPORTED; '
      f'{R["m5_pairs_total"]} eligible ordered pairs '
      f'({R["m5_pairs_cross"]} cross-year, {R["m5_pairs_within"]} within-year)')
res5 = m5.resid
adj = np.where((cool.month.diff() == 1) & (cool.year.diff() == 0))[0]
put('cool_lag1_within', float(np.corrcoef(res5[adj], res5[adj - 1])[0, 1]))
put('cool_lag1_naive', float(np.corrcoef(res5[1:], res5[:-1])[0, 1]))
put('cool_lag1_npairs', int(len(adj)))
print(f'  residual lag-1: within-block {R["cool_lag1_within"]:.3f} '
      f'({len(adj)} pairs) vs naive {R["cool_lag1_naive"]:.3f}')

h('4. Model-implied components')
def component(key):
    m = fits[key]; nm = specs[key][1]
    i, jx = nm.index('CDD'), nm.index('HDD')
    bc, bh = m.b[i], m.b[jx]
    Ec, Eh = bc * ANN_CDD, bh * ANN_HDD
    ratio = Eh / Ec
    V = hacV(m)
    g = np.zeros(m.k); g[i] = -Eh * ANN_CDD / Ec ** 2; g[jx] = ANN_HDD / Ec
    se = math.sqrt(float(g @ V @ g))
    return dict(b_cdd=bc, b_hdd=bh, slope_ratio=bc / bh, e_cool=Ec, e_heat=Eh, ratio=ratio,
                share_cool=Ec / ANN_SALES, share_heat=Eh / ANN_SALES,
                remainder=ANN_SALES - Ec - Eh, share_rem=(ANN_SALES - Ec - Eh) / ANN_SALES,
                ratio_se=se, lo=ratio - Z975 * se, hi=ratio + Z975 * se,
                corr=float(V[i, jx] / math.sqrt(V[i, i] * V[jx, jx]))), i, jx

def block_boot(key, i, jx, B=4000, L=12):
    """Moving-block bootstrap on (y, X) ROWS. Blocks of 12 consecutive observations are
    drawn with replacement and concatenated; the design matrix travels with its rows."""
    m = fits[key]; X, y = m.X, m.y
    nb = int(np.ceil(m.n / L)); starts = np.arange(m.n - L + 1)
    out = []
    for _ in range(B):
        s = RNG.choice(starts, nb, replace=True)
        idx = np.concatenate([np.arange(q, q + L) for q in s])[:m.n]
        try:
            b, *_ = np.linalg.lstsq(X[idx], y[idx], rcond=None)
        except np.linalg.LinAlgError:
            continue
        if b[i] <= 0: continue
        out.append((b[jx] * ANN_HDD) / (b[i] * ANN_CDD))
    return np.array(out)

comp = {}
for key in ['M3', 'M4']:
    c, i, jx = component(key)
    bs = block_boot(key, i, jx)
    c.update(boot_lo=float(np.percentile(bs, 2.5)), boot_hi=float(np.percentile(bs, 97.5)),
             boot_n=int(len(bs)), boot_B=4000, boot_L=12, boot_method='percentile',
             boot_scheme='moving block on (y, X) rows', seed=SEED)
    comp[key] = c
    print(f'  {key}: ratio {c["ratio"]:.5f}  HAC delta 95% CI [{c["lo"]:.4f}, {c["hi"]:.4f}]  '
          f'block boot [{c["boot_lo"]:.4f}, {c["boot_hi"]:.4f}]  corr(b) {c["corr"]:+.2f}')
R['comp'] = comp
print('  NOTE recorded: block resampling reorders blocks, so the deterministic trend')
print('  regressor is not preserved in calendar order. The bootstrap is reported as a')
print('  secondary check; the HAC delta-method interval is primary.')

sens = {}
t2 = df.t_c.values ** 2
for lab, X, nm in [
    ('quadratic_trend', C(df.cdd.values, df.hdd.values, df.t_c.values, t2),
     ['c', 'CDD', 'HDD', 'Y', 'Y2']),
    ('drop_last3', C(df.cdd.values[:-3], df.hdd.values[:-3], df.t_c.values[:-3]),
     ['c', 'CDD', 'HDD', 'Y'])]:
    y_ = df.sales.values if lab != 'drop_last3' else df.sales.values[:-3]
    mm = OLS(y_, X, nm, hac_lag=12)
    sens[lab] = dict(b_cdd=mm.b[1], b_hdd=mm.b[2], r2=mm.r2,
                     ratio=(mm.b[2] * ANN_HDD) / (mm.b[1] * ANN_CDD))
dd = df.copy()
dd['days'] = [calendar.monthrange(int(a), int(b)) [1] for a, b in zip(df.year, df.month)]
md = OLS((dd.sales / dd.days).values,
         C((dd.cdd / dd.days).values, (dd.hdd / dd.days).values, dd.t_c.values),
         ['c', 'CDD', 'HDD', 'Y'], hac_lag=12)
sens['per_day'] = dict(b_cdd=md.b[1], b_hdd=md.b[2], r2=md.r2,
                       ratio=(md.b[2] * ANN_HDD) / (md.b[1] * ANN_CDD))
R['sens'] = sens
for k, v in sens.items():
    print(f'  sensitivity {k:<16} ratio {v["ratio"]:.4f}')

h('5. Seasonal differences (pointwise HAC CIs; Bonferroni p values)')
order = ['Winter', 'Spring', 'Summer', 'Fall']
sd_ = pd.get_dummies(df.season, drop_first=False).astype(float)
Xs = np.column_stack([np.ones(N)] + [sd_[s].values for s in order[1:]])
ms = OLS(df.sales.values, Xs, ['Winter'] + order[1:], hac_lag=12)
Vs = hacV(ms)
seas = {}
for a, b in itertools.combinations(order, 2):
    ga, gb = df[df.season == a].sales.values, df[df.season == b].sales.values
    diff = ga.mean() - gb.mean()
    d = np.zeros(ms.k)
    if a == 'Winter': d[order[1:].index(b) + 1] = -1
    elif b == 'Winter': d[order[1:].index(a) + 1] = 1
    else: d[order[1:].index(a) + 1] = 1; d[order[1:].index(b) + 1] = -1
    se = math.sqrt(float(d @ Vs @ d))
    z = diff / se
    sa, sb = ga.var(ddof=1) / len(ga), gb.var(ddof=1) / len(gb)
    tw = diff / math.sqrt(sa + sb)
    dfw = (sa + sb) ** 2 / (sa ** 2 / (len(ga) - 1) + sb ** 2 / (len(gb) - 1))
    seas[f'{a}-{b}'] = dict(diff=diff, se=se, z=z,
                            p_raw=2 * (1 - norm_cdf(abs(z))),
                            p_bonf=min(1.0, 6 * 2 * (1 - norm_cdf(abs(z)))),
                            lo=diff - Z975 * se, hi=diff + Z975 * se,
                            p_welch_bonf=min(1.0, 6 * t_p_two(tw, dfw)))
    v = seas[f'{a}-{b}']
    print(f'  {a:<7}-{b:<7} {diff:>+11,.0f}  pointwise 95% CI '
          f'[{v["lo"]:>+11,.0f}, {v["hi"]:>+11,.0f}]  p_bonf={v["p_bonf"]:.4f}  '
          f'Welch p_bonf={v["p_welch_bonf"]:.4f}')
R['seas'] = seas
gm = df.sales.mean()
ssb = sum(R['season'][s]['n'] * (R['season'][s]['mean'] - gm) ** 2 for s in order)
put('eta2', ssb / ((df.sales.values - gm) ** 2).sum())
last = df[df.year == 2026]
put('last_year_months', int(len(last)))
put('last_year_seasons', ', '.join(sorted(set(last.season))))
bal = df.groupby('season').year.nunique().to_dict()
print(f'  last year contributes {len(last)} months ({R["last_year_seasons"]}), so Winter and')
print('  Spring each carry one more year than Summer and Fall; seasonal Ns are 110/110/108/108.')
dfc = df[df.year < 2026]
put('eta2_complete', float(sum((dfc.season == s).sum() * (dfc[dfc.season == s].sales.mean() - dfc.sales.mean()) ** 2
                               for s in order) / ((dfc.sales.values - dfc.sales.mean()) ** 2).sum()))
for s in order:
    put(f'season_mean_complete_{s}', float(dfc[dfc.season == s].sales.mean()))
put('winter_mean_shift_complete_years',
    R['season_mean_complete_Winter'] - R['season']['Winter']['mean'])
print(f'  restricting to complete years changes the Winter mean by '
      f'{R["season_mean_complete_Winter"] - R["season"]["Winter"]["mean"]:+,.0f} MWh')

h('6. July vs January')
jul = df[df.month == 7][['year', 'sales']].rename(columns={'sales': 'jul'})
jan = df[df.month == 1][['year', 'sales']].rename(columns={'sales': 'jan'})
pr = jul.merge(jan, on='year'); d_ = (pr.jul - pr.jan).values; n_ = len(d_)
sd = d_.std(ddof=1); sem = sd / math.sqrt(n_); dof = n_ - 1
for k, v in [('pair_n', n_), ('pair_jul', pr.jul.mean()), ('pair_jan', pr.jan.mean()),
             ('pair_diff', d_.mean()), ('pair_sd', sd), ('pair_t', d_.mean() / sem),
             ('pair_p2', t_p_two(d_.mean() / sem, dof)), ('pair_dz', d_.mean() / sd),
             ('pair_up', int((d_ > 0).sum())),
             ('pair_ci95_lo', d_.mean() - t_ppf(.975, dof) * sem),
             ('pair_ci95_hi', d_.mean() + t_ppf(.975, dof) * sem),
             ('pair_ci90_lo', d_.mean() - t_ppf(.95, dof) * sem),
             ('pair_ci90_hi', d_.mean() + t_ppf(.95, dof) * sem),
             ('pair_lag1', float(np.corrcoef(d_[1:], d_[:-1])[0, 1])),
             ('pair_dw', ((np.diff(d_)) ** 2).sum() / ((d_ - d_.mean()) ** 2).sum())]:
    put(k, v)
acf_d = [float(np.corrcoef(d_[k:], d_[:-k])[0, 1]) for k in range(1, 5)]
R['pair_acf'] = acf_d
put('pair_acf_max', max(abs(a) for a in acf_d))
put('pair_acf_bound', 1.96 / math.sqrt(n_))
print(f'  mean diff {d_.mean():,.0f}  SD {sd:,.0f}  t({dof}) = {R["pair_t"]:.3f}  '
      f'p = {R["pair_p2"]:.4f}')
print(f'  paired-difference autocorrelations at lags 1-4: '
      f'{", ".join(f"{a:+.3f}" for a in acf_d)}  (|bound| {R["pair_acf_bound"]:.3f})')
tost = {}
for delta in [0.3, 0.4, 0.5]:
    D = delta * sd
    pl = t_sf((d_.mean() + D) / sem, dof); pu = 1 - t_sf((d_.mean() - D) / sem, dof)
    tost[str(delta)] = dict(bound=D, pmax=max(pl, pu), established=bool(max(pl, pu) < .05),
                            ci90_inside=bool(R['pair_ci90_lo'] > -D and R['pair_ci90_hi'] < D),
                            ci95_inside=bool(R['pair_ci95_lo'] > -D and R['pair_ci95_hi'] < D))
    print(f'  +/-{delta} SD ({D:,.0f} MWh): pmax = {tost[str(delta)]["pmax"]:.4f}  '
          f'{"established" if tost[str(delta)]["established"] else "NOT established"}')
R['tost'] = tost

h('7. Per-customer trends and the proportional-trend contrast')
mfe_pc = pd.get_dummies(pc.month.astype(int), prefix='m', drop_first=True).astype(float).values
X7 = np.column_stack([np.ones(len(pc)), pc.cdd, pc.hdd, pc.tw, pc.cdd * pc.tw, pc.hdd * pc.tw])
nm7 = ['Intercept', 'CDD', 'HDD', 'Year', 'CDDxYear', 'HDDxYear']
X6 = np.column_stack([np.ones(len(pc)), pc.cdd, pc.hdd, pc.tw])
nm6 = ['Intercept', 'CDD', 'HDD', 'Year']
fits7 = {'M6': OLS(pc.spc.values, X6, nm6, hac_lag=12),
         'M7': OLS(pc.spc.values, X7, nm7, hac_lag=12),
         'M8': OLS(pc.spc.values, np.column_stack([X7, mfe_pc]),
                   nm7 + [f'M{i}' for i in range(2, 13)], hac_lag=12)}
LAB = {'M6': 'Per-customer sales ~ CDD + HDD + year (2008-2026)',
       'M7': 'Model 6 + CDD x year and HDD x year',
       'M8': 'Model 7 + calendar-month effects'}
for key, m in fits7.items():
    V = hacV(m); hse = np.sqrt(np.diag(V))
    d = dict(label=LAB[key], n=m.n, k=m.k, r2=m.r2, adj_r2=m.adj_r2, dw=m.dw, coef={})
    for i, v in enumerate(m.names):
        w_ = wald(m.b[i], hse[i], m.dof); w_.update(ols_se=m.se[i], ols_p=m.p(i))
        d['coef'][v] = w_
    if 'CDDxYear' not in m.names:
        models[key] = d
        print(f'  {key}: R2={m.r2:.4f}  CDD={m.b[m.names.index("CDD")]:.4e}  '
              f'HDD={m.b[m.names.index("HDD")]:.4e}  (no interaction terms)')
        continue
    i_c, i_h = m.names.index('CDD'), m.names.index('HDD')
    i_x, i_hx = m.names.index('CDDxYear'), m.names.index('HDDxYear')
    lo_t, hi_t = pc.tw.min(), pc.tw.max()
    d['pct_cdd'] = float((m.b[i_c] + m.b[i_x] * hi_t) / (m.b[i_c] + m.b[i_x] * lo_t) - 1)
    d['pct_hdd'] = float((m.b[i_h] + m.b[i_hx] * hi_t) / (m.b[i_h] + m.b[i_hx] * lo_t) - 1)
    bc, bh, bx, bhx = m.b[i_c], m.b[i_h], m.b[i_x], m.b[i_hx]
    g_ = bx / bc - bhx / bh
    gr = np.zeros(m.k); gr[i_c] = -bx / bc ** 2; gr[i_x] = 1 / bc
    gr[i_h] = bhx / bh ** 2; gr[i_hx] = -1 / bh
    se_ = math.sqrt(float(gr @ V @ gr))
    d['contrast'] = wald(g_, se_, m.dof); d['contrast']['dof'] = m.dof
    models[key] = d
    print(f'  {key}: R2={m.r2:.4f}  CDDxYear p(HAC,normal)={d["coef"]["CDDxYear"]["p_norm"]:.4f} '
          f'(OLS p={d["coef"]["CDDxYear"]["ols_p"]:.4f})  cooling {d["pct_cdd"]*100:+.1f}%  '
          f'heating {d["pct_hdd"]*100:+.1f}%')
    print(f'       contrast {g_:+.6f} SE {se_:.6f}  normal p={d["contrast"]["p_norm"]:.5f}  '
          f't({m.dof}) p={d["contrast"]["p_t"]:.5f}  CI [{d["contrast"]["lo"]:+.6f}, '
          f'{d["contrast"]["hi"]:+.6f}]')

bw = {}
for key, m in fits7.items():
    if 'CDDxYear' not in m.names: continue
    i_x = m.names.index('CDDxYear')
    bw[key] = {}
    for L in [0, 3, 6, 12, 18, 24]:
        V = hacV(m, L=max(L, 1)) if L else None
        se_ = m.se[i_x] if L == 0 else float(np.sqrt(np.diag(V))[i_x])
        z = m.b[i_x] / se_
        bw[key][str(L)] = dict(se=se_, p=2 * (1 - norm_cdf(abs(z))))
R['bw_interaction'] = bw
print('\n  Bandwidth sensitivity, CDD x year coefficient (L = 0 is OLS):')
for key in ['M7', 'M8']:
    print(f'    {key}  ' + '  '.join(f'L={L}: p={bw[key][str(L)]["p"]:.4f}'
                                     for L in [0, 3, 6, 12, 18, 24]))
bwm = {}
for key, m in fits7.items():
    if 'CDDxYear' not in m.names: continue
    i_c, i_h = m.names.index('CDD'), m.names.index('HDD')
    i_x, i_hx = m.names.index('CDDxYear'), m.names.index('HDDxYear')
    bc, bh, bx, bhx = m.b[i_c], m.b[i_h], m.b[i_x], m.b[i_hx]
    g_ = bx / bc - bhx / bh
    gr = np.zeros(m.k); gr[i_c] = -bx / bc ** 2; gr[i_x] = 1 / bc
    gr[i_h] = bhx / bh ** 2; gr[i_hx] = -1 / bh
    bwm[key] = {}
    for L in [3, 6, 12, 18, 24]:
        se_ = math.sqrt(float(gr @ hacV(m, L=L) @ gr))
        bwm[key][str(L)] = dict(se=se_, p=2 * (1 - norm_cdf(abs(g_ / se_))))
R['bw_contrast'] = bwm
print('  Bandwidth sensitivity, proportional-trend contrast:')
for key in ['M7', 'M8']:
    print(f'    {key}  ' + '  '.join(f'L={L}: p={bwm[key][str(L)]["p"]:.4f}'
                                     for L in [3, 6, 12, 18, 24]))

h('8. Exclusion sensitivity for the per-customer results')
anom = (cov.year * 100 + cov.month).isin([202106, 202111, 202112, 202201, 202202])
excl = {}
for lab, sub in [('2008-2026 (primary)', cov[cov.year >= 2008]),
                 ('2007-2026 (2007 retained)', cov),
                 ('2009-2026', cov[cov.year >= 2009]),
                 ('2008-2026 less 2021-22 anomalies', cov[(cov.year >= 2008) & (~anom)])]:
    out = {}
    for fe in [False, True]:
        s = sub.copy(); s['tw'] = s.t - s.t.mean()
        X = np.column_stack([np.ones(len(s)), s.cdd, s.hdd, s.tw, s.cdd * s.tw, s.hdd * s.tw])
        nmx = list(nm7)
        if fe:
            X = np.column_stack([X, pd.get_dummies(s.month.astype(int), prefix='m',
                                                   drop_first=True).astype(float).values])
            nmx = nmx + [f'M{i}' for i in range(2, 13)]
        m = OLS(s.spc.values, X, nmx, hac_lag=12); V = hacV(m)
        i_c, i_h = m.names.index('CDD'), m.names.index('HDD')
        i_x, i_hx = m.names.index('CDDxYear'), m.names.index('HDDxYear')
        bc, bh, bx, bhx = m.b[i_c], m.b[i_h], m.b[i_x], m.b[i_hx]
        g_ = bx / bc - bhx / bh
        gr = np.zeros(m.k); gr[i_c] = -bx / bc ** 2; gr[i_x] = 1 / bc
        gr[i_h] = bhx / bh ** 2; gr[i_hx] = -1 / bh
        se_ = math.sqrt(float(gr @ V @ gr))
        zx = bx / float(np.sqrt(np.diag(V))[i_x])
        lo_t, hi_t = s.tw.min(), s.tw.max()
        out['fe' if fe else 'nofe'] = dict(
            n=m.n, p_cddxyear=2 * (1 - norm_cdf(abs(zx))),
            pct_cdd=float((bc + bx * hi_t) / (bc + bx * lo_t) - 1),
            contrast=g_, p_contrast=2 * (1 - norm_cdf(abs(g_ / se_))))
    excl[lab] = out
    print(f'  {lab:<36} no-FE: CDDxYr p={out["nofe"]["p_cddxyear"]:.4f} '
          f'cool {out["nofe"]["pct_cdd"]*100:+.1f}% contrast p={out["nofe"]["p_contrast"]:.4f} '
          f'| FE: p={out["fe"]["p_cddxyear"]:.4f} cool {out["fe"]["pct_cdd"]*100:+.1f}% '
          f'contrast p={out["fe"]["p_contrast"]:.4f}')
R['exclusion'] = excl

h('9. Diagnostics (both Breusch-Pagan variants)')
bp = {}
for lab, key, Z, dfree in [
        ('M1, aux on CDD', 'M1', C(df.cdd.values), 1),
        ('M3, aux on CDD+HDD', 'M3', C(df.cdd.values, df.hdd.values), 2),
        ('M3, aux on CDD+HDD+trend', 'M3', C(df.cdd.values, df.hdd.values, df.t_c.values), 3)]:
    r2 = OLS(fits[key].resid ** 2, Z, ['c'] * Z.shape[1]).r2
    lm = N * r2
    bp[lab] = dict(lm=lm, df=dfree, p=chi2_sf(lm, dfree))
    print(f'  {lab:<28} LM = {lm:6.3f}  df = {dfree}  p = {bp[lab]["p"]:.5f}')
R['bp'] = bp
print('  NOTE: the chi-square reference for these LM statistics assumes independent errors;')
print('  it is NOT dependence-robust. Reported as an indication, not a decisive test.')
for key in ['M1', 'M3', 'M4']:
    r = fits[key].resid; rm = r - r.mean()
    put(f'acf1_{key}', float(np.corrcoef(r[1:], r[:-1])[0, 1]))
    put(f'acf12_{key}', float((rm[12:] * rm[:-12]).sum() / (rm ** 2).sum()))
print('  residual ACF  ' + '  '.join(
    f'{k}: lag1={R[f"acf1_{k}"]:.2f} lag12={R[f"acf12_{k}"]:.2f}' for k in ['M1', 'M3', 'M4']))
for k in ['M1', 'M3']:
    b, se, rho = gls_ar1(df.sales.values, specs[k][0])
    models[k]['gls'] = dict(b_cdd=b[1], se_cdd=se[1], rho=rho)
bwq = {}
for k in ['M1', 'M3', 'M4']:
    m = fits[k]
    bwq[k] = {'ols': float(m.se[1])}
    for L in [3, 6, 12, 18, 24]:
        bwq[k][str(L)] = float(np.sqrt(np.diag(hacV(m, L=L)))[1])
R['bw_sweep'] = bwq
put('pct_increase_m1_to_m3', 100 * (fits['M3'].b[1] / fits['M1'].b[1] - 1))
put('pct_m1_below_m3', 100 * (1 - fits['M1'].b[1] / fits['M3'].b[1]))
tv = df.t_c.values
def det(v):
    X = C(tv); b, *_ = np.linalg.lstsq(X, v, rcond=None); return v - X @ b
put('r_all', float(np.corrcoef(df.cdd, df.sales)[0, 1]))
put('r_detrend', float(np.corrcoef(det(df.cdd.values), det(df.sales.values))[0, 1]))
put('r_diff1', float(np.corrcoef(np.diff(df.cdd.values), np.diff(df.sales.values))[0, 1]))
put('r_diff12', float(np.corrcoef(df.cdd.values[12:] - df.cdd.values[:-12],
                                  df.sales.values[12:] - df.sales.values[:-12])[0, 1]))
put('match_total_r', float(np.corrcoef(pc.cdd, pc.sales)[0, 1]))
put('match_pc_r', float(np.corrcoef(pc.cdd, pc.spc)[0, 1]))
w_ = df[df.season == 'Winter']; s_ = df[df.season == 'Summer']
put('win_hdd_r', float(np.corrcoef(w_.hdd, w_.sales)[0, 1]))
put('sum_cdd_r', float(np.corrcoef(s_.cdd, s_.sales)[0, 1]))
apr = pc.groupby('year').price.mean().reset_index()

R['software'] = dict(python=sys.version.split()[0], platform=platform.platform(),
                     numpy=np.__version__, pandas=pd.__version__,
                     scipy='not installed', statsmodels='not installed', R='not installed',
                     note='Distribution tails come from statlib.py, validated against '
                          'published critical values by validate_statlib.py (40/40).')
R['heating'] = dict(nc_central_heat_pump_pct=38, sc=41, al=39, tn=35, fl=31,
                    nc_furnace_pct=50, nc_units_million=4.01,
                    source='EIA RECS 2020, Highlights for space heating in U.S. homes by '
                           'state (Form EIA-457A); main heating EQUIPMENT, not fuel',
                    note='Furnace fuel is not broken out; electric resistance heating is in '
                         'the not-shown "other equipment" category. A state electric-heating '
                         'share cannot be computed from this table.')
df.to_csv(ROOT / 'results' / 'analysis_panel.csv', index=False)
json.dump(R, open(ROOT / 'results' / 'results.json', 'w'),
          indent=1, default=float)
print(f'\nwrote results.json ({len(R)} keys) and analysis_panel.csv')
