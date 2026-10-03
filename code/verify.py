"""Check that every number in the manuscript traces to results.json."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

R = json.load(open(ROOT / 'results' / 'results.json'))
M, S, CP, B, EX, HT = R['models'], R['season'], R['comp'], R['bp'], R['exclusion'], R['heating']
RAW = open(ROOT / 'results' / 'paper.txt').read()
TXT = re.sub(r'\s+', ' ', RAW)

def cm(x): return f'{round(x):,}'
def nz(x, d=2):
    s = f'{x:.{d}f}'
    return s[1:] if s.startswith('0.') else ('-' + s[2:] if s.startswith('-0.') else s)
def num(x, d=2): return f'{x:.{d}f}'
SUP = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')
def sci(x, d=2):
    m_, e_ = f'{x:.{d}e}'.split('e'); e = int(e_)
    return f'{m_} × 10' + ('⁻' if e < 0 else '') + str(abs(e)).translate(SUP)

checks = []
def chk(lab, s): checks.append((lab, s, s in TXT))

chk('N', f'{int(R["N"])} months'); chk('complete yrs', f'{int(R["n_complete_years"])} complete calendar')
for k in ['ann_cdd', 'ann_hdd', 'mean_sales', 'sd_sales', 'min_sales', 'max_sales']:
    chk(k, cm(R[k]))
chk('hdd:cdd', num(R['hdd_cdd_ratio']))
for s_ in ['Winter', 'Spring', 'Summer', 'Fall']:
    chk(f'{s_} M', cm(S[s_]['mean'])); chk(f'{s_} SD', cm(S[s_]['sd']))
chk('cust jump', f'{R["cust_jump_pct"]:+.1f}%')
chk('cust other max', f'{R["cust_other_max_pct"]:.2f}%')
chk('cust excl cluster', f'{R["cust_excl_cluster_max"]:.2f}%')
chk('cluster net', f'{R["cluster_net_pct"]:+.2f}%')
chk('jan08 sales yoy', f'{R["jan08_yoy_sales"]:+.1f}%')
chk('jan08 cust yoy', f'{R["jan08_yoy_cust"]:+.1f}%')
for a in R['cust_anomalies']:
    chk(f'anom {a["year"]}-{a["month"]}', f'{a["mom"]:+.2f}%')
    chk(f'anomN {a["year"]}-{a["month"]}', cm(a['customers']))
chk('n_pc', f'{int(R["n_pc"])} months'); chk('n_pc_all', f'{int(R["n_pc_all"])} months')
chk('tbar', f'{R["pc_tbar"]:.3f}')
chk('cust first', cm(R['cust_first'])); chk('cust last', cm(R['cust_last']))
for k in ['M1', 'M2', 'M3', 'M4', 'M5']:
    chk(f'{k} R2', nz(M[k]['r2']))
for k in ['M1', 'M2', 'M3', 'M4']:
    chk(f'{k} CDD', cm(M[k]['coef']['CDD']['b']))
chk('M3 CDD CI', f'[{cm(M["M3"]["coef"]["CDD"]["lo"])}, {cm(M["M3"]["coef"]["CDD"]["hi"])}]')
chk('M3 HDD CI', f'[{cm(M["M3"]["coef"]["HDD"]["lo"])}, {cm(M["M3"]["coef"]["HDD"]["hi"])}]')
chk('pct above', f'{R["pct_increase_m1_to_m3"]:.0f}%')
chk('pct below', f'{R["pct_m1_below_m3"]:.0f}%')
chk('gls M1', cm(M['M1']['gls']['b_cdd'])); chk('gls M3', cm(M['M3']['gls']['b_cdd']))
for k in ['M1', 'M3']:
    for L in ['ols', '3', '12', '24']:
        if k == 'M1' and L == '24': continue
        chk(f'bw {k} {L}', f'{R["bw_sweep"][k][L]:.0f}')
for k in ['M3', 'M4']:
    c = CP[k]
    chk(f'{k} bc', cm(c['b_cdd'])); chk(f'{k} bh', cm(c['b_hdd']))
    chk(f'{k} slope ratio', num(c['slope_ratio'])); chk(f'{k} ratio', num(c['ratio']))
    chk(f'{k} CI', f'[{num(c["lo"])}, {num(c["hi"])}]')
    chk(f'{k} boot', f'[{num(c["boot_lo"])}, {num(c["boot_hi"])}]')
    chk(f'{k} corr', num(c['corr']))
    chk(f'{k} sc', f'{c["share_cool"]:.1%}'); chk(f'{k} sh', f'{c["share_heat"]:.1%}')
for k in ['quadratic_trend', 'per_day', 'drop_last3']:
    chk(f'sens {k}', num(R['sens'][k]['ratio']))
for k, v in R['seas'].items():
    chk(f'seas {k}', cm(v['diff']))
chk('WS CI', f'[{cm(R["seas"]["Winter-Summer"]["lo"])}, {cm(R["seas"]["Winter-Summer"]["hi"])}]')
chk('eta2', nz(R['eta2'])); chk('eta2c', nz(R['eta2_complete']))
for k in ['pair_jul', 'pair_jan', 'pair_diff', 'pair_sd']:
    chk(k, cm(R[k]))
chk('pair t', num(R['pair_t'])); chk('pair dz', num(R['pair_dz']))
chk('ci90', f'[{cm(R["pair_ci90_lo"])}, {cm(R["pair_ci90_hi"])}]')
chk('ci95', f'[{cm(R["pair_ci95_lo"])}, {cm(R["pair_ci95_hi"])}]')
for b in ['0.3', '0.4', '0.5']:
    chk(f'tost {b}', cm(R['tost'][b]['bound']))
for k in ['M7', 'M8']:
    for v in ['CDDxYear', 'HDDxYear']:
        chk(f'{k} {v}', sci(M[k]['coef'][v]['b']))
    chk(f'{k} pctc', f'{M[k]["pct_cdd"]*100:+.1f}%')
    chk(f'{k} pcth', f'{M[k]["pct_hdd"]*100:+.1f}%')
    chk(f'{k} R2', nz(M[k]['r2']))
    c = M[k]['contrast']
    chk(f'{k} contrast b', f'{c["b"]:+.5f}')
    chk(f'{k} contrast se', f'{c["se"]:.5f}')
    chk(f'{k} contrast CI', f'[{c["lo"]:+.5f}, {c["hi"]:+.5f}]')
chk('M6 CDD', sci(M['M6']['coef']['CDD']['b']))
chk('M6 R2', nz(M['M6']['r2']))
chk('M7 CDDxYear CI',
    f'[{sci(M["M7"]["coef"]["CDDxYear"]["lo"])}, {sci(M["M7"]["coef"]["CDDxYear"]["hi"])}]')
for lab, v in EX.items():
    chk(f'excl {lab} n', str(v['fe']['n']))
for k in ['r_all', 'r_detrend', 'r_diff1', 'r_diff12', 'match_total_r', 'match_pc_r',
          'win_hdd_r', 'sum_cdd_r', 'acf1_M1', 'acf12_M1', 'acf1_M3', 'acf12_M3', 'acf12_M4',
          'cool_lag1_within', 'cool_lag1_naive']:
    chk(k, nz(R[k]))
chk('m5 slope', cm(R['m5_slope']))
chk('m5 block', num(R['m5_hac_block_se'], 1)); chk('m5 ols', num(R['m5_ols_se'], 1))
chk('m5 calendar', num(R['m5_hac_cal_se'], 1))
chk('m5 naive1', num(R['m5_hac_naive_se'], 1))
chk('m5 pairs', str(int(R['m5_pairs_total'])))
chk('m5 cross', str(int(R['m5_pairs_cross'])))
chk('m5 within', str(int(R['m5_pairs_within'])))
for lab, v in B.items():
    chk(f'bp {lab}', num(v['lm']))
chk('heat nc', f'{HT["nc_central_heat_pump_pct"]}%')
chk('heat sc', f'{HT["sc"]}%'); chk('heat al', f'{HT["al"]}%')
chk('heat furnace', f'{HT["nc_furnace_pct"]}%')
chk('python', R['software']['python']); chk('numpy', R['software']['numpy'])
chk('pandas', R['software']['pandas'])

for k in ['M1', 'M2', 'M3', 'M4']:
    for v in ['CDD', 'HDD', 'Year']:
        c = M[k]['coef'].get(v)
        if c is None: continue
        chk(f'T4 {k} {v} OLS SE', f'({cm(c["ols_se"])})')
        chk(f'T4 {k} {v} HAC SE', f'[{cm(c["se"])}]')
chk('T4 M5 OLS SE', f'({cm(R["m5_ols_se"])})')
chk('T4 M5 HAC SE', f'[{cm(R["m5_hac_cal_se"])}]')
chk('intro 38%', '38% of')
chk('intro SC 41', 'South Carolina (41%)')
chk('intro AL 39', 'Alabama (39%)')
chk('intro equipment wording', 'main heating equipment')
chk('intro not-electric-share', 'is not the share of homes')
chk('customer break wording', 'Customer counts increased far more sharply than sales')
chk('m5 method calendar', 'actual calendar distance between the retained')
chk('m5 method cross-year', 'straddle the autumn-to-spring gap')

fails = [c for c in checks if not c[2]]
print(f'PART 1 — asserted claims: {len(checks)-len(fails)}/{len(checks)} present')
for lab, s, _ in fails:
    print(f'   FAIL  {lab:26} expected: {s!r}')

body = TXT.split('References')[0]
NUM = r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|-?\.\d+'
body_nodates = re.sub(r'\b(19|20)\d{2}-\d{2}\b', ' <DATE> ', body)
nums = set(re.findall(r'(?<![\w.,])(' + NUM + r')(?![\w])', body_nodates))
known = set()
def add(x):
    try: x = float(x)
    except Exception: return
    for f in (cm, nz, num, lambda v: nz(v, 1), lambda v: nz(v, 3), lambda v: nz(v, 4),
              lambda v: nz(v, 5), lambda v: num(v, 1), lambda v: num(v, 3),
              lambda v: num(v, 4), lambda v: num(v, 5),
              lambda v: f'{v:.0f}', lambda v: f'{v:.1f}', lambda v: f'{v:.2f}',
              lambda v: f'{v:.3f}', lambda v: f'{v:.4f}', lambda v: f'{v:.5f}',
              lambda v: f'{v:,.0f}', lambda v: f'{v:,.1f}', lambda v: str(int(round(v))),
              lambda v: '-' + cm(abs(v)) if v < 0 else cm(v),
              lambda v: '-' + num(abs(v)) if v < 0 else num(v),
              lambda v: f'{v:.2e}'.split('e')[0]):
        try: known.add(f(x))
        except Exception: pass
def walk(o):
    if isinstance(o, dict):
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
    elif isinstance(o, (int, float)):
        for m_ in (1, 100, 1000, 1e6, -1, -100): add(o * m_)
        for d_ in (1e6, 1e3): add(o / d_)
        add(abs(o)); add(abs(o) * 100); add(abs(o) / 1e6); add(o - 1)
walk(R)
for k in ['M3', 'M4']:
    add(abs(CP[k]['ratio'] - 1) * 100)
WHITE = {'1895','1974','1987','2002','2006','2007','2008','2009','2010','2015','2017','2018',
         '2020','2021','2022','2023','2024','2025','2026','2100','1990','861','65','12','3',
         '2','1','4','5','6','7','8','9','10','11','13','14','15','16','18','19','20','21',
         '22','23','24','36','38','39','41','44','67','93','95','90','100','1,000','9999',
         '031','26','25','02','1.0.0','20260604','4,000','.05','.001','.01','58','0','457',
         '2011',
         '2.5','97.5'
         }
orphans = sorted(n for n in nums if n not in known and n not in WHITE)
print(f'\nPART 2 — orphan scan: {len(nums)} distinct numbers, {len(orphans)} unmatched')
for o in orphans:
    m = re.search(r'.{60}' + re.escape(o) + r'.{60}', body)
    print(f'   ? {o:>14}  ...{m.group(0) if m else ""}...')

print('\nPART 3 — semantic checks')
sem = []
def sc(lab, ok, detail=''):
    sem.append((lab, ok, detail))

capt = {n: (re.search(r'Table ' + str(n) + r'\s+([A-Z][^\n]{8,90})', RAW) or [None, ''])[1]
        for n in range(1, 10)}
expect = {1: 'Customer', 2: 'Model Definitions', 3: 'Descriptive', 4: 'Regression Models',
          5: 'Model-Implied', 6: 'Seasonal', 7: 'Paired', 8: 'Per-Customer', 9: 'Sensitivity'}
for n, kw in expect.items():
    sc(f'Table {n} caption mentions "{kw}"', kw.lower() in capt[n].lower(), capt[n][:50])
for n in list(range(1, 13)):
    sc(f'Figure {n} caption present', len(re.findall(r'\nFigure ' + str(n) + r'\n', RAW)) == 1)
for n in ['A1', 'A2', 'A3', 'A4']:
    sc(f'Figure {n} caption present', len(re.findall(r'\nFigure ' + n + r'\n', RAW)) == 1)
for lab, pat in [
        ('no "bracket the quantity"', r'bracket the quantity'),
        ('no "biases the degree-day coefficients toward zero"', r'toward zero'),
        ('no blanket "not distinguishable from one another"', r'not statistically distinguishable from one another'),
        ('no "every other month-over-month change"', r'every other month-over-month'),
        ('no "a priori"', r'a priori'),
        ('no "understated by"', r'understated by'),
        ('no "meets the benchmark"', r'meets? the published benchmark'),
        ('no "remainder is weather-independent base load"', r'weather-independent base load'),
        ('no capacity inference', r'capacity planning (?:in the Carolinas )?should'),
        ('no 19-year window wording', r'19 years for which'),
        ('no "Only the denominator moves"', r'Only the denominator moves'),
        ('no 39% NC heat-pump claim', r'39% of its households'),
        ('no "matched by Alabama"', r'matched by Alabama'),
        ('no HDD-only-in-electric claim', r'only in homes that heat with electricity'),
        ('no stray equipment f-string', r'\{"equipment"\}'),
        ('no malformed ladder label', r'Sales ~ \d\. \+'),
        ('no block-aware-is-reported claim', r'block-aware figure is the one reported')]:
    sc(lab, re.search(pat, TXT, re.I) is None)
for lab, pat in [
        ('both contrast p values reported', r'Model 8.{0,400}?\.017|\.017.{0,400}?Model 8'),
        ('contrast described as specification-dependent',
         r'depends? on whether calendar-month effects are included'),
        ('equipment-not-fuel qualification', r'main heating equipment, not main heating fuel'),
        ('electric resistance acknowledged', r'electric resistance heating'),
        ('coverage change called suspected', r'suspected rather than'),
        ('reference distribution stated', r'standard normal (?:distribution|reference)'),
        ('both BP variants', r'2 degrees of freedom.{0,200}3 degrees of freedom'),
        ('Model 5 HAC at calendar distance', r'actual calendar distance'),
        ('bootstrap trend caveat', r'no longer in calendar order'),
        ('in-sample not forecast', r'in-sample fit to the months used for estimation'),
        ('MWh vs MW distinction', r'similar megawatt-hours can have very different peak megawatt'),
        ('exact window length', r'18 years and 4 months'),
        ('bandwidth not preregistered', r'not preregistered'),
        ('pointwise vs Bonferroni labelled', r'uncorrected for multiplicity|pointwise'),
        ('Table 3 holds descriptives ref', r'Table 3 reports the monthly variables'),
        ('Figure 6 scatter ref', r'Figure 6 shows why the fit is poor'),
        ('Table 4 OLS-vs-HAC ref', r'Table 4 also shows that HAC and ordinary'),
        ('Table 5 component-interval ref', r'Neither interval in Table 5'),
        ('Table 8 for Models 6-8', r'Models 6.8, which use sales per customer[^.]*Table 8'),
        ('Table 1 for anomalies', r'more than 2%\s+in absolute value \(Table 1\)'),
        ('combustion electricity acknowledged', r'blowers, pumps, and controls'),
        ('m5 calendar HAC reported', r'calendar-distance figure is the one reported in Table 4')]:
    sc(lab, re.search(pat, TXT, re.I) is not None)
bad = [x for x in sem if not x[1]]
for lab, ok, det in sem:
    if not ok: print(f'   FAIL  {lab}   {det}')
print(f'   {len(sem)-len(bad)}/{len(sem)} semantic checks passed')

print('\nRESULT:', 'PASS' if not fails and not orphans and not bad else 'REVIEW NEEDED')
