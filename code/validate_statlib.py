"""Check the distribution functions in statlib.py against published reference values
(NIST e-Handbook, Abramowitz and Stegun)."""
import sys, math
from statlib import t_ppf, t_sf, t_p_two, f_sf, norm_cdf, norm_ppf, betai

TOL = 5e-6
rows, bad = [], 0

def chk(name, got, want, tol=TOL):
    global bad
    ok = abs(got - want) <= tol
    if not ok: bad += 1
    rows.append((name, got, want, abs(got - want), ok))

chk('Phi(1.959963985)      ', norm_cdf(1.959963985), 0.975)
chk('Phi(1.644853627)      ', norm_cdf(1.644853627), 0.95)
chk('Phi(2.575829304)      ', norm_cdf(2.575829304), 0.995)
chk('Phi(0)                ', norm_cdf(0.0), 0.5)
chk('norm_ppf(0.975)       ', norm_ppf(0.975), 1.959963985)
chk('norm_ppf(0.95)        ', norm_ppf(0.95), 1.644853627)

for df, want in [(1, 12.706205), (2, 4.302653), (5, 2.570582), (10, 2.228139),
                 (20, 2.085963), (30, 2.042272), (60, 2.000298), (100, 1.983972),
                 (220, 1.970806)]:
    chk(f't_ppf(.975, {df:<4})      ', t_ppf(0.975, df), want, 2e-5)
for df, want in [(10, 1.812461), (20, 1.724718), (35, 1.689572), (100, 1.660234)]:
    chk(f't_ppf(.95,  {df:<4})      ', t_ppf(0.95, df), want, 2e-5)

_z = 1.959963985
for df in [100, 220, 434]:
    _a = _z + (_z**3 + _z)/(4*df) + (5*_z**5 + 16*_z**3 + 3*_z)/(96*df**2)
    chk(f't_ppf(.975,{df:<4}) vs A&S  ', t_ppf(0.975, df), _a, 3e-6)

chk('t_sf(2.228139, 10)    ', t_sf(2.228139, 10), 0.025, 1e-6)
chk('t_p_two(2.228139, 10) ', t_p_two(2.228139, 10), 0.05, 1e-6)
chk('t_sf(0, 7)            ', t_sf(0.0, 7), 0.5)
chk('t_p_two(1.0, 1)       ', t_p_two(1.0, 1), 0.5)
chk('t_sf(-2.228139, 10)   ', t_sf(-2.228139, 10), 0.975, 1e-6)

for d1, d2, want in [(1, 10, 4.964603), (2, 10, 4.102821), (3, 20, 3.098391),
                     (1, 434, 3.862900), (3, 236, 2.642000)]:
    chk(f'f_sf(F.05 {d1},{d2:<4})     ', f_sf(want, d1, d2), 0.05, 6e-4)
for df in [5, 20, 100]:
    chk(f'F(1,{df}) == t^2 tail   ', f_sf(2.5 ** 2, 1, df), t_p_two(2.5, df), 1e-9)

chk('betai(1,1,0.37)       ', betai(1, 1, 0.37), 0.37, 1e-12)
chk('betai(2,3,0.5)        ', betai(2, 3, 0.5), 0.6875, 1e-12)
chk('betai(a,b,x)+betai(b,a,1-x)', betai(3.5, 2.5, 0.42) + betai(2.5, 3.5, 0.58), 1.0, 1e-12)

chk('chi2_1 tail at 3.841459', 2 * (1 - norm_cdf(math.sqrt(3.841459))), 0.05, 1e-6)
chk('chi2_2 tail at 5.991465', math.exp(-5.991465 / 2), 0.05, 1e-6)

print(f'{"check":<32} {"computed":>14} {"reference":>14} {"|diff|":>11}   ok')
print('-' * 78)
for n, g, w, d, ok in rows:
    print(f'{n:<32} {g:>14.9f} {w:>14.9f} {d:>11.2e}   {"PASS" if ok else "**FAIL**"}')
print('-' * 78)
print(f'{len(rows) - bad}/{len(rows)} passed')
if bad:
    print('statlib is NOT validated; do not rely on it.')
    sys.exit(1)
print('statlib validated against published reference values at the tolerances shown.')
print('NOTE: chi-square with 3 df is NOT available in closed form here; the Breusch-Pagan')
print('      variant needing it is computed with an explicit series (see analysis.py)')
print('      and separately checked against its own reference value.')
