import math

def _betacf(a, b, x, itmax=300, eps=3e-16):
    qab, qap, qam = a+b, a+1.0, a-1.0
    c = 1.0
    d = 1.0 - qab*x/qap
    if abs(d) < 1e-300: d = 1e-300
    d = 1.0/d
    h = d
    for m in range(1, itmax+1):
        m2 = 2*m
        aa = m*(b-m)*x/((qam+m2)*(a+m2))
        d = 1.0+aa*d
        if abs(d) < 1e-300: d = 1e-300
        c = 1.0+aa/c
        if abs(c) < 1e-300: c = 1e-300
        d = 1.0/d
        h *= d*c
        aa = -(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
        d = 1.0+aa*d
        if abs(d) < 1e-300: d = 1e-300
        c = 1.0+aa/c
        if abs(c) < 1e-300: c = 1e-300
        d = 1.0/d
        de = d*c
        h *= de
        if abs(de-1.0) < eps: break
    return h

def betai(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)
    bt = math.exp(lbeta + a*math.log(x) + b*math.log(1.0-x))
    if x < (a+1.0)/(a+b+2.0):
        return bt*_betacf(a, b, x)/a
    return 1.0 - bt*_betacf(b, a, 1.0-x)/b

def t_sf(t, df):
    x = df/(df+t*t)
    p_two = betai(df/2.0, 0.5, x)
    return p_two/2.0 if t > 0 else 1.0 - p_two/2.0

def t_cdf(t, df):
    return 1.0 - t_sf(t, df)

def t_p_two(t, df):
    x = df/(df+t*t)
    return betai(df/2.0, 0.5, x)

def f_sf(f, d1, d2):
    if f <= 0: return 1.0
    x = d2/(d2+d1*f)
    return betai(d2/2.0, d1/2.0, x)

def t_ppf(p, df, lo=-1e3, hi=1e3):
    for _ in range(300):
        mid = (lo+hi)/2
        if t_cdf(mid, df) < p: lo = mid
        else: hi = mid
    return (lo+hi)/2

def norm_cdf(z):
    return 0.5*(1.0+math.erf(z/math.sqrt(2.0)))

def norm_ppf(p, lo=-40.0, hi=40.0):
    for _ in range(200):
        mid = (lo+hi)/2
        if norm_cdf(mid) < p: lo = mid
        else: hi = mid
    return (lo+hi)/2
