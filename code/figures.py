import sys, math, json, calendar
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from core import ROOT, load, OLS, t_ppf
from statlib import norm_ppf

OUT = str(ROOT / 'figures' / 'fig')
R = json.load(open(ROOT / 'results' / 'results.json'))
df = load(); df['t_c'] = df.t - df.t.mean(); df['ls'] = np.log(df.sales)
A = pd.read_csv(ROOT / 'results' / 'annual_slopes.csv')
M = R['models']; G = 1000.0

SEAS = {'Winter': '#3b6ea5', 'Spring': '#5aa469', 'Summer': '#c3423f', 'Fall': '#e0902f'}
GREY = '#4a4a4a'
plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Lato', 'DejaVu Sans'],
    'font.size': 10, 'axes.labelsize': 10.5, 'axes.edgecolor': '#8a8a8a',
    'axes.linewidth': .8, 'axes.grid': True, 'grid.color': '#e2e2e2',
    'grid.linewidth': .7, 'axes.axisbelow': True, 'xtick.color': GREY,
    'ytick.color': GREY, 'axes.labelcolor': '#1a1a1a', 'legend.frameon': False,
    'figure.dpi': 300, 'savefig.dpi': 300, 'savefig.bbox': 'tight',
    'savefig.pad_inches': .05})
def clean(ax):
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
def save(fig, n):
    fig.savefig(f'{OUT}{n}.png'); plt.close(fig); print('  wrote', n)
def C(*c): return np.column_stack([np.ones(len(c[0]))] + list(c))

def lowess(x, y, frac=.35, grid=200):
    x = np.asarray(x, float); y = np.asarray(y, float)
    o = np.argsort(x); x, y = x[o], y[o]
    gx = np.linspace(x.min(), x.max(), grid); gy = np.empty(grid)
    h = max(int(frac * len(x)), 3)
    for i, x0 in enumerate(gx):
        d = np.abs(x - x0); idx = np.argsort(d)[:h]
        dm = d[idx].max() or 1.0
        w = (1 - (d[idx] / dm) ** 3) ** 3
        X = np.column_stack([np.ones(h), x[idx] - x0]); W = np.diag(w)
        try:
            gy[i] = np.linalg.solve(X.T @ W @ X, X.T @ W @ y[idx])[0]
        except np.linalg.LinAlgError:
            gy[i] = np.average(y[idx], weights=w)
    return gx, gy

def fitband(ax, x, y, color='#1a1a1a', lw=1.6, band=True):
    x = np.asarray(x, float); y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b; s2 = (r @ r) / (len(x) - 2); XtXi = np.linalg.inv(X.T @ X)
    gx = np.linspace(x.min(), x.max(), 120); Gm = np.column_stack([np.ones(120), gx])
    fit = Gm @ b
    if band:
        se = np.sqrt(np.einsum('ij,jk,ik->i', Gm, XtXi, Gm) * s2)
        ax.fill_between(gx, fit - t_ppf(.975, len(x) - 2) * se,
                        fit + t_ppf(.975, len(x) - 2) * se, color=color, alpha=.15, lw=0, zorder=2)
    ax.plot(gx, fit, color=color, lw=lw, zorder=3)
    return b

fig, ax = plt.subplots(figsize=(6.6, 3.8))
t = np.linspace(20, 100, 400)
def arm(t, k_c=1.0, sat=28.0):
    return 40 + np.clip(65 - t, 0, None) + k_c * sat * (1 - np.exp(-np.clip(t - 65, 0, None) / sat)) * 1.9
ax.plot(t, arm(t), color='#2b5d8a', lw=2.3, zorder=4, label='Reference response')
ax.plot(t, arm(t, 1.35), color=SEAS['Summer'], lw=1.6, ls=(0, (5, 3)), zorder=3,
        label='Steeper cooling arm')
ax.plot(t, arm(t, .68), color='#7a8b99', lw=1.6, ls=(0, (2, 2.5)), zorder=3,
        label='Flatter cooling arm')
ax.axvline(65, color=GREY, ls=(0, (5, 4)), lw=1.1, zorder=1)
ax.annotate('balance point (65 °F)', xy=(65, 46), xytext=(43, 52), fontsize=9, color=GREY,
            arrowprops=dict(arrowstyle='->', color=GREY, lw=.8))
ax.annotate('curvature at\ntemperature extremes', xy=(95, arm(np.array([95.0]))[0]),
            xytext=(75, 62), fontsize=8.8, color=GREY,
            arrowprops=dict(arrowstyle='->', color=GREY, lw=.8, connectionstyle='arc3,rad=-.25'))
ax.annotate('heating arm', xy=(28, 78), fontsize=9.5, color=SEAS['Winter'], style='italic')
ax.annotate('cooling arm', xy=(84, 42), fontsize=9.5, color=SEAS['Summer'], style='italic')
ax.set_xlabel('Mean outdoor temperature (°F)')
ax.set_ylabel('Electricity demand\n(illustrative units)')
ax.set_yticks([]); ax.set_ylim(30, 95)
ax.legend(loc='upper center', fontsize=8.5, handlelength=2.6, labelspacing=.3)
clean(ax); save(fig, '02_conceptual')

fig, ax = plt.subplots(figsize=(7.0, 4.4))
for s, c in SEAS.items():
    d = df[df.season == s]
    ax.scatter(d.tavg, d.sales / G, s=16, color=c, alpha=.72, lw=0, label=s, zorder=3)
gx, gy = lowess(df.tavg, df.sales / G, .35)
ax.plot(gx, gy, color='#1a1a1a', lw=2.0, zorder=4)
ax.axvline(65, color=GREY, ls=(0, (5, 4)), lw=1.1, zorder=1)
ax.annotate('65 °F', xy=(65, 7400), xytext=(66.3, 7350), fontsize=9, color=GREY)
ax.set_xlabel('Mean monthly temperature (°F)'); ax.set_ylabel('Residential sales (GWh)')
ax.legend(loc='lower center', ncol=4, bbox_to_anchor=(.5, 1.0), handletextpad=.2,
          columnspacing=1.4)
clean(ax); save(fig, '05_response_function')

fig, ax = plt.subplots(figsize=(7.0, 4.4))
for s, c in SEAS.items():
    d = df[df.season == s]
    ax.scatter(d.cdd, d.sales / G, s=16, color=c, alpha=.72, lw=0, label=s, zorder=3)
b1 = M['M1']['coef']; gx = np.linspace(0, df.cdd.max(), 200)
ax.plot(gx, np.exp(b1['Intercept']['b'] + b1['CDD']['b'] * gx) / G, color='#1a1a1a', lw=1.6, zorder=4)
z = df[df.cdd == 0]
ax.annotate(f'{R["zero_cdd_n"]} zero-CDD months span\n{z.sales.min()/G:,.0f}–{z.sales.max()/G:,.0f} GWh',
            xy=(6, 7250), xytext=(62, 7100), fontsize=8.8, color=GREY,
            arrowprops=dict(arrowstyle='->', color=GREY, lw=.8, shrinkA=0))
ax.text(.975, .04, f"Model 1: $R^2$ = {M['M1']['r2']:.2f}", transform=ax.transAxes,
        ha='right', va='bottom', fontsize=9.5,
        bbox=dict(boxstyle='round,pad=.4', fc='white', ec='#cccccc', lw=.7))
ax.set_xlabel('Cooling degree days'); ax.set_ylabel('Residential sales (GWh)')
ax.legend(loc='lower center', ncol=4, bbox_to_anchor=(.5, 1.0), handletextpad=.2,
          columnspacing=1.4)
clean(ax); save(fig, '06_cdd_scatter')

fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.5))
tv = df.t_c.values
def partial(focus, others):
    X0 = np.column_stack([np.ones(len(df))] + others)
    ry = df.ls.values - X0 @ np.linalg.lstsq(X0, df.ls.values, rcond=None)[0]
    rx = focus - X0 @ np.linalg.lstsq(X0, focus, rcond=None)[0]
    return rx, ry
for ax, (lab, foc, oth, col, key) in zip(axes, [
        ('Cooling degree days', df.cdd.values, [df.hdd.values, tv], SEAS['Summer'], 'CDD'),
        ('Heating degree days', df.hdd.values, [df.cdd.values, tv], SEAS['Winter'], 'HDD')]):
    rx, ry = partial(foc, oth)
    ax.scatter(rx, ry * 100, s=12, color=col, alpha=.55, lw=0, zorder=3)
    fitband(ax, rx, ry * 100, lw=1.5)
    c = M['M3']['coef'][key]
    ax.text(.04, .95, f"{c['pct100']:.1f}% per 100 degree days\n95% CI [{c['pct100_lo']:.1f}, {c['pct100_hi']:.1f}]",
            transform=ax.transAxes, va='top', fontsize=8.6, linespacing=1.5)
    ax.set_xlabel(f'{lab} | other predictors'); clean(ax)
axes[0].set_ylabel('Log sales × 100\n| other predictors')
save(fig, '07_two_arms')

fig, ax = plt.subplots(figsize=(7.0, 3.1))
rows = [('Model 4\n(+ month effects)', R['comp']['M4']), ('Model 3\n(linear trend)', R['comp']['M3'])]
for yi, (lab, c) in enumerate(rows):
    parts = [('Rest of sales', c['remainder'] / 1e6, '#b9b9b9'),
             ('Cooling component', c['e_cool'] / 1e6, SEAS['Summer']),
             ('Heating component', c['e_heat'] / 1e6, SEAS['Winter'])]
    left = 0
    for nm, v, col in parts:
        ax.barh(yi, v, left=left, color=col, height=.45, edgecolor='white', lw=1.2)
        ax.text(left + v / 2, yi, f'{v:.1f}\n({v/(R["ann_sales"]/1e6):.0%})', ha='center',
                va='center', fontsize=8.6, fontweight='bold',
                color='white' if col != '#b9b9b9' else '#333333')
        left += v
    ax.text(left + .6, yi, f'heating/cooling = {c["ratio"]:.2f}', va='center', fontsize=9,
            color=GREY)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], fontsize=9)
ax.set_xlim(0, R['ann_sales'] / 1e6 * 1.20); ax.set_ylim(-.55, len(rows) - .3)
ax.grid(False); ax.set_xlabel('Mean annual residential sales (million MWh)')
for sp in ['top', 'right', 'left']: ax.spines[sp].set_visible(False)
ax.legend(handles=[Patch(facecolor=c, label=l) for l, c in
                   [('Rest of sales', '#b9b9b9'),
                    ('Cooling component', SEAS['Summer']),
                    ('Heating component', SEAS['Winter'])]],
          loc='lower center', ncol=3, bbox_to_anchor=(.5, .99), fontsize=8.5)
save(fig, '08_decomposition')

fig, axes = plt.subplots(1, 3, figsize=(8.0, 3.3), gridspec_kw={'width_ratios': [1, 1, .78]})
for ax, (col, se_col, lab, c, key) in zip(axes[:2], [
        ('b_cdd', 'se_cdd', 'Cooling response\n(kWh per customer per CDD)', SEAS['Summer'], 'b_cdd'),
        ('b_hdd', 'se_hdd', 'Heating response\n(kWh per customer per HDD)', SEAS['Winter'], 'b_hdd')]):
    v = A[col].values * 1000; e = A[se_col].values * 1000
    ax.errorbar(A.year, v, yerr=1.96 * e, fmt='o', ms=4, color=c, ecolor=c,
                elinewidth=1, capsize=2.5, alpha=.85, zorder=3)
    fitband(ax, A.year.values, v, lw=1.4)
    ax.set_ylabel(lab, fontsize=8.8); ax.set_xlabel('Year'); clean(ax)
    ax.tick_params(labelsize=8.5)
ax = axes[2]
P = R['pmods']
labels = ['MWh,\nno month\neffects', 'MWh,\nmonth\neffects', 'Percent,\nno month\neffects', 'Percent,\nmonth\neffects']
for i, key in enumerate(['M5', 'M6', 'M7', 'M8']):
    y0 = 3 - i
    ax.scatter(P[key]['pct_cdd'], y0 + .12, s=34, color=SEAS['Summer'], zorder=4)
    ax.scatter(P[key]['pct_hdd'], y0 - .12, s=34, color=SEAS['Winter'], marker='s', zorder=4)
ax.axvline(0, color=GREY, ls=(0, (4, 3)), lw=1)
ax.set_yticks([3, 2, 1, 0]); ax.set_yticklabels(labels, fontsize=7.4)
ax.set_xlabel('Change in response,\n2008 to 2026 (%)', fontsize=8.8)
ax.set_ylim(-.6, 3.6); ax.tick_params(labelsize=8.3)
ax.legend(handles=[Line2D([], [], marker='o', ls='', color=SEAS['Summer'], label='Cooling'),
                   Line2D([], [], marker='s', ls='', color=SEAS['Winter'], label='Heating')],
          loc='lower center', bbox_to_anchor=(.5, 1.0), ncol=2, fontsize=8, handletextpad=.1)
clean(ax)
fig.tight_layout(w_pad=1.8)
save(fig, '09_stability')

fig, ax = plt.subplots(figsize=(8.2, 3.3))
ax.plot(df.t, df.sales / G, color='#2b5d8a', lw=.7, alpha=.9, zorder=2)
gx, gy = lowess(df.t, df.sales / G, .18)
ax.plot(gx, gy, color=SEAS['Summer'], lw=1.9, zorder=3)
ax.set_xlabel('Year'); ax.set_ylabel('Residential sales (GWh)')
clean(ax); save(fig, '04_timeseries')

cov = df.dropna(subset=['customers'])
fig, ax = plt.subplots(figsize=(7.0, 3.2))
ax.plot(cov.t, cov.customers / 1e6, color='#2b5d8a', lw=1.5, zorder=3)
ax.axvline(2008.0, color=SEAS['Summer'], ls=(0, (5, 3)), lw=1.3, zorder=2)
ax.annotate(f'+{R["cust_jump_pct"]:.0f}% step at January 2008',
            xy=(2008.0, 3.6), xytext=(2010.4, 3.15), fontsize=8.8, color=GREY,
            arrowprops=dict(arrowstyle='->', color=GREY, lw=.9))
ax.axvspan(cov.t.min(), 2008.0, color='#c3423f', alpha=.07, zorder=1)
ax.text(2007.4, 5.1, 'excluded', fontsize=8.4, color=SEAS['Summer'], ha='center')
ax.set_xlabel('Year'); ax.set_ylabel('Residential customers\n(millions)')
clean(ax); save(fig, '03_customer_break')

def diag(key, Xspec, name):
    m = OLS(df.ls.values, Xspec, ['c'] + ['x'] * (Xspec.shape[1] - 1))
    fig, ax = plt.subplots(2, 2, figsize=(7.2, 5.4))
    r = m.resid; f = m.X @ m.b
    ax[0, 0].scatter(f, r, s=10, color=GREY, alpha=.45, lw=0)
    ax[0, 0].axhline(0, color=SEAS['Summer'], ls=(0, (4, 3)), lw=1.1)
    ax[0, 0].set_xlabel('Fitted log sales'); ax[0, 0].set_ylabel('Residual')
    ax[0, 1].hist(r, bins=32, density=True, color='#2b5d8a', alpha=.85)
    xs = np.linspace(r.min(), r.max(), 200)
    ax[0, 1].plot(xs, np.exp(-.5 * ((xs - r.mean()) / r.std()) ** 2) /
                  (r.std() * math.sqrt(2 * math.pi)), color=SEAS['Summer'], lw=1.5)
    ax[0, 1].set_xlabel('Residual'); ax[0, 1].set_ylabel('Density')
    q = np.sort(r); n = len(q); th = np.array([norm_ppf((i + .5) / n) for i in range(n)])
    ax[1, 0].scatter(th, q, s=10, color=GREY, alpha=.45, lw=0)
    lo, hi = np.percentile(q, [25, 75]); tlo, thi = np.percentile(th, [25, 75])
    sl = (hi - lo) / (thi - tlo)
    ax[1, 0].plot(th, sl * th + (lo - sl * tlo), color=SEAS['Summer'], lw=1.3)
    ax[1, 0].set_xlabel('Theoretical quantiles'); ax[1, 0].set_ylabel('Sample quantiles')
    rm = m.resid - m.resid.mean(); den = (rm ** 2).sum()
    lags = np.arange(1, 25); acf = [float((rm[k:] * rm[:-k]).sum() / den) for k in lags]
    ax[1, 1].bar(lags, acf, color='#2b5d8a', width=.75)
    b95 = 1.96 / math.sqrt(m.n)
    for s_ in (b95, -b95):
        ax[1, 1].axhline(s_, color=SEAS['Summer'], ls=(0, (4, 3)), lw=1)
    ax[1, 1].set_xlabel('Lag (months)'); ax[1, 1].set_ylabel('Residual ACF')
    ax[1, 1].set_ylim(min(-.15, min(acf) * 1.15), max(.35, max(acf) * 1.15))
    for a in ax.ravel(): clean(a)
    for a, t_ in zip(ax.ravel(), ['A', 'B', 'C', 'D']):
        a.text(-.17, 1.06, t_, transform=a.transAxes, fontsize=11, fontweight='bold')
    fig.tight_layout(); save(fig, name)

mfe = pd.get_dummies(df.month.astype(int), prefix='m', drop_first=True).astype(float).values
diag('M1', C(df.cdd.values), 'A1_diag_m1')
diag('M3', C(df.cdd.values, df.hdd.values, df.t_c.values), 'A2_diag_m3')
diag('M4', np.column_stack([np.ones(len(df)), df.cdd, df.hdd, df.t_c, mfe]), 'A3_diag_m4')

print('done')
