"""Build the manuscript (.docx) from results.json and the figures."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
import json, math, os, re
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

R = json.load(open(ROOT / 'results' / 'results.json'))
M, S, CP = R['models'], R['season'], R['comp']
FIG = str(ROOT / 'figures' / 'fig')
OLD = str(ROOT / 'figures')
B = R['bp']; EX = R['exclusion']; HT = R['heating']
OUT = str(ROOT / 'results' / 'Two Arms of One Curve.docx')


def p(x, d=3):
    if x < .001: return 'p < .001'
    return 'p = ' + f'{x:.{d}f}'.lstrip('0')
def nz(x, d=2):
    s = f'{x:.{d}f}'
    return s[1:] if s.startswith('0.') else ('-' + s[2:] if s.startswith('-0.') else s)
def num(x, d=2): return f'{x:.{d}f}'
def cm(x): return f'{round(x):,}'
def pv(x, d=3):
    return '< .001' if x < .001 else nz(x, d)
SUP = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')
def sci(x, d=2):
    m_, e_ = f'{x:.{d}e}'.split('e')
    e_i = int(e_)
    return f'{m_} × 10' + ('⁻' if e_i < 0 else '') + str(abs(e_i)).translate(SUP)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
for m_ in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
    setattr(sec, m_, Inches(1))
st = doc.styles['Normal']
st.font.name = 'Times New Roman'; st.font.size = Pt(12)
st.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')
st.paragraph_format.line_spacing = 2.0
st.paragraph_format.space_after = Pt(0); st.paragraph_format.space_before = Pt(0)
hp = sec.header.paragraphs[0]; hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
r_ = hp.add_run()
for kind, val in [('fldChar', 'begin'), ('instrText', 'PAGE'), ('fldChar', 'separate'),
                  ('t', '1'), ('fldChar', 'end')]:
    e = OxmlElement(f'w:{kind}')
    if kind == 'fldChar': e.set(qn('w:fldCharType'), val)
    else: e.text = val; e.set(qn('xml:space'), 'preserve')
    r_._r.append(e)
hp.runs[0].font.name = 'Times New Roman'; hp.runs[0].font.size = Pt(12)


def para(text='', *, bold=False, italic=False, align='left', indent=True,
         space_after=0, spacing=2.0, keep=False):
    q = doc.add_paragraph()
    q.paragraph_format.line_spacing = spacing
    q.paragraph_format.space_after = Pt(space_after)
    q.paragraph_format.keep_with_next = keep
    q.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER}[align]
    if indent: q.paragraph_format.first_line_indent = Inches(0.5)
    if text:
        rr = q.add_run(text); rr.bold, rr.italic = bold, italic
    return q
def rich(parts, *, indent=True, spacing=2.0, space_after=0):
    q = doc.add_paragraph()
    q.paragraph_format.line_spacing = spacing
    q.paragraph_format.space_after = Pt(space_after)
    if indent: q.paragraph_format.first_line_indent = Inches(0.5)
    for t, s in parts:
        rr = q.add_run(t); rr.bold = 'b' in s; rr.italic = 'i' in s
    return q
def h1(t): para(t, bold=True, align='center', indent=False, keep=True)
def h2(t): para(t, bold=True, indent=False, keep=True)
def pagebreak(): doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

def figure(n, title, path, note=None, width=6.0):
    para(f'Figure {n}', bold=True, indent=False, keep=True)
    para(title, italic=True, indent=False, keep=True)
    q = doc.add_paragraph(); q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    q.paragraph_format.line_spacing = 1.0
    q.paragraph_format.space_before = Pt(6); q.paragraph_format.space_after = Pt(6)
    q.add_run().add_picture(path, width=Inches(width))
    if note: rich([('Note. ', 'i'), (note, '')], indent=False, spacing=1.0, space_after=12)

def set_cell(cell, text, *, italic=False, align='left', size=10.5):
    cell.text = ''
    q = cell.paragraphs[0]
    q.paragraph_format.line_spacing = 1.0
    q.paragraph_format.space_after = Pt(3); q.paragraph_format.space_before = Pt(3)
    q.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER,
                   'right': WD_ALIGN_PARAGRAPH.RIGHT}[align]
    rr = q.add_run(text); rr.italic = italic
    rr.font.size = Pt(size); rr.font.name = 'Times New Roman'
def border(cell, edge, sz=6):
    tcPr = cell._tc.get_or_add_tcPr()
    bs = tcPr.find(qn('w:tcBorders'))
    if bs is None: bs = OxmlElement('w:tcBorders'); tcPr.append(bs)
    el = bs.find(qn(f'w:{edge}'))
    if el is None: el = OxmlElement(f'w:{edge}'); bs.append(el)
    el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), str(sz)); el.set(qn('w:color'), '000000')

def table(n, title, header, rows, note=None, widths=None, aligns=None):
    para(f'Table {n}', bold=True, indent=False, keep=True)
    para(title, italic=True, indent=False, keep=True)
    nc = len(header)
    widths = widths or [6.5 / nc] * nc
    t = doc.add_table(rows=1 + len(rows), cols=nc)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    _lay = OxmlElement('w:tblLayout'); _lay.set(qn('w:type'), 'fixed')
    t._tbl.tblPr.append(_lay)
    _grid = t._tbl.find(qn('w:tblGrid'))
    if _grid is not None:
        for _gc, _w in zip(_grid.findall(qn('w:gridCol')), widths):
            _gc.set(qn('w:w'), str(int(round(_w * 1440))))
    aligns = aligns or (['left'] + ['center'] * (nc - 1))
    for j, hh in enumerate(header):
        c = t.rows[0].cells[j]
        set_cell(c, hh, align=aligns[j] if j else 'left')
        border(c, 'top'); border(c, 'bottom')
    for i, row in enumerate(rows, 1):
        for j, v in enumerate(row):
            c = t.rows[i].cells[j]
            set_cell(c, v.lstrip('~'), italic=v.startswith('~'), align=aligns[j] if j else 'left')
            if i == len(rows): border(c, 'bottom')
    for row in t.rows:
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for j, c in enumerate(row.cells): c.width = Inches(widths[j])
    if note: rich([('Note. ', 'i'), (note, '')], indent=False, spacing=1.0, space_after=12)
    else: doc.add_paragraph().paragraph_format.space_after = Pt(12)

TITLE = ('Two Arms of One Curve: Cooling and Heating Degree Days and Monthly Residential '
         'Electricity Sales in North Carolina, 1990–2026')

for _ in range(4): para(indent=False)
para(TITLE, bold=True, align='center', indent=False)
para(indent=False)
para('Shubham Jalan', align='center', indent=False)
para('Independent Researcher', align='center', indent=False)
para('September 2026', align='center', indent=False)
pagebreak()

h1('Abstract')
para(
    'Utilities in the Southeast plan around summer cooling, yet North Carolina heats an unusually '
    'large share of its housing stock with electricity. This study estimated both arms of the '
    'temperature response function for monthly statewide residential electricity sales and asked '
    f'whether the cooling arm has been stable. The analysis used {int(R["N"])} months of public '
    'federal data (January 1990 to April 2026) from NOAA’s nClimDiv dataset and the U.S. Energy '
    'Information Administration’s Form EIA-861M. A cooling-degree-day-only regression explained '
    f'R² = {nz(M["M1"]["r2"])} of the variance in monthly sales. Adding heating degree days raised '
    f'R² to {nz(M["M2"]["r2"])}, and adding a linear time trend raised it to {nz(M["M3"]["r2"])}; '
    'the two additions contributed comparable increments. In the trend specification the cooling '
    f'slope was {cm(CP["M3"]["b_cdd"])} MWh per cooling degree day, 95% CI '
    f'[{cm(M["M3"]["coef"]["CDD"]["lo"])}, {cm(M["M3"]["coef"]["CDD"]["hi"])}], and the heating '
    f'slope {cm(CP["M3"]["b_hdd"])} MWh per heating degree day, 95% CI '
    f'[{cm(M["M3"]["coef"]["HDD"]["lo"])}, {cm(M["M3"]["coef"]["HDD"]["hi"])}], using '
    'heteroscedasticity- and autocorrelation-consistent standard errors throughout. Multiplying '
    'each slope by mean annual degree-day exposure gives model-implied heating and cooling '
    'components of comparable size, with heating the larger. That ordering held across '
    f'specifications, but its magnitude did not: the implied ratio was {num(CP["M3"]["ratio"])} '
    f'under a linear trend and {num(CP["M4"]["ratio"])} once calendar-month effects were added, so '
    'no single ratio is reported as a headline. July and January mean monthly sales were '
    'statistically equivalent within an exploratory, post hoc margin of ±0.4 standard deviations '
    f'of the paired difference, {p(R["tost"]["0.4"]["pmax"])}. Per-customer sensitivity to cooling '
    f'degree days declined over January 2008 to April 2026 in both pooled specifications, by '
    f'{abs(M["M7"]["pct_cdd"])*100:.0f}% and {abs(M["M8"]["pct_cdd"])*100:.0f}%. Whether that '
    'proportional decline exceeded the corresponding heating decline depended on the '
    f'specification: the contrast was {p(M["M7"]["contrast"]["p_norm"])} without calendar-month '
    f'effects and {p(M["M8"]["contrast"]["p_norm"])} with them. These results describe associations '
    'in monthly energy. They do not establish forecasting accuracy, and they carry no implication '
    'for peak power or generating capacity.', indent=False)
para()
rich([('Keywords: ', 'i'),
      ('temperature response function, cooling degree days, heating degree days, degree-day '
       'regression, North Carolina, residential electricity demand', '')], indent=False)
pagebreak()

para(TITLE, bold=True, align='center', indent=False)
para(
    'Residential electricity demand in the southeastern United States is rising, and air '
    'conditioning drives a substantial share of it. Nationally, air conditioning accounts for '
    'approximately 19% of residential electricity consumption (U.S. Energy Information '
    'Administration [EIA], 2024), and 93% of households in the South Census region use it (EIA, '
    '2022). Duke Energy projects that customer energy needs across the Carolinas will grow over the '
    'next 15 years at roughly eight times the rate of the previous 15 (Duke Energy, 2025).')
para(
    'The standard tool for relating temperature to demand is the degree day. A day’s cooling degree '
    'day (CDD) value equals the number of degrees by which its mean temperature exceeds a base of '
    '65 °F; heating degree days (HDD) count degrees below that base, and monthly totals sum the '
    'daily values (EIA, 2023b). Because demand rises as temperature moves away from the balance '
    'point in either direction, the temperature–demand relationship traces a curve with two arms, '
    'cooling on the right and heating on the left (Hu et al., 2024). Applied degree-day work in the '
    'Southeast has often concentrated on the cooling arm, which is a defensible simplification in '
    'Florida or Texas but a consequential modeling choice in a state that heats with electricity.')
para(
    'North Carolina is such a state. In the 2020 Residential Energy Consumption Survey, 38% of '
    'its housing units reported a central heat pump as their main heating equipment, a share '
    'below South Carolina (41%) and Alabama (39%) but among the higher ones nationally (EIA, '
    '2023a). That figure counts one category of equipment and is not the share of homes '
    'heating with electricity, which this source does not report. '
    'Meanwhile the state’s cooling degree days have trended upward and heating degree days downward '
    '(Kunkel et al., 2020), so the balance between the arms need not be fixed.')
para(
    'This study asks three questions. First, what changes in the estimated temperature response '
    'when heating degree days and temporal structure are included alongside cooling degree days? '
    'Second, how do the model-implied heating and cooling components of annual sales compare, and '
    'how sensitive is that comparison to specification? Third, has the per-customer response to '
    'degree days been stable over the period for which customer counts are available? The design is '
    'observational and uses statewide monthly aggregates, so the results describe associations '
    'rather than causal effects, and they concern monthly energy in megawatt-hours rather than peak '
    'power.')

h1('Background')
h2('Degree-Day Models of Electricity Demand')
para(
    'Temperature predicts electricity demand strongly, though the strength varies by region, '
    'season, and specification. Cawthorne et al. (2021) modeled seasonal demand across balancing '
    'authorities in Tennessee and Texas and reported that, after regional population growth '
    'accounted for variability at decadal time scales, temperature explained 44% to 67% of demand '
    'variability at seasonal time scales (Figure 1). That range describes temperature’s share of '
    'population-adjusted variability using population-weighted temperature, so it is not a '
    'transferable threshold against which a coefficient of determination from unadjusted state '
    'totals can be judged. Fache and Bhat (2024) applied the degree-day method to Florida within a '
    'regression that also included population, employment, gross domestic product, electricity '
    'price, and daylight hours, and found temperature among the strongest predictors of residential '
    'demand.')
figure(1, 'Residuals of Electricity Demand Versus Population-Weighted Average Temperature for '
          'Tennessee (A: Winter, B: Summer) and Texas (C: Winter, D: Summer)',
       f'{OLD}/fig01_cawthorne_2021.png',
       'From Cawthorne et al. (2021), Frontiers in Sustainable Cities, licensed under CC BY 4.0. '
       'The winter panels slope downward and the summer panels slope upward, illustrating the '
       'two-armed response.')
para(
    'The mechanism is the balance-point relationship: buildings require little temperature-driven '
    'energy near the balance point, and demand rises as temperature departs from it in either '
    'direction (EIA, 2023b). Hu et al. (2024) analyzed the dynamics of this temperature response '
    'function for 36 European countries, building scenario assumptions about thermal insulation, '
    'heating electrification, space-cooling penetration, and passive cooling into projections to '
    '2100. Their projections imply that rising space-cooling penetration raises cooling-season '
    'demand in cooling-dominated regions while passive-cooling measures and improved insulation '
    'offset part of that increase. Because that study is a forward-looking scenario analysis for '
    'Europe rather than an empirical estimate of historical change in the United States, it '
    'motivates the question of whether a response function is stable without supplying a result '
    'that a North Carolina estimate could confirm or contradict.')
figure(2, 'Illustrative Diagram of a Two-Armed Temperature Response Function',
       f'{FIG}02_conceptual.png',
       'Author-created schematic drawn from the balance-point concept (EIA, 2023b) and the '
       'temperature response function discussed by Hu et al. (2024). The curves are illustrative '
       'and are not fitted to data, are not a depiction of equipment behavior, and are not a '
       'finding of this study. A steeper and a flatter cooling arm are shown only to make the '
       'question of stability concrete.', width=5.7)
h2('Methodological Considerations')
para(
    'Three issues shape a defensible design. First, monthly energy series are strongly seasonal and '
    'autocorrelated, and Granger and Newbold (1974) showed that regressing one trending or cyclical '
    'series on another can produce correlations with inflated significance. Second, a cooling-only '
    'model omits the heating side of a two-armed relationship. Because the omitted arm is '
    'correlated with the included one through the annual cycle, the omission changes the surviving '
    'coefficient rather than merely narrowing the scope of the study. Third, unequal variability '
    'across months is common in monitored household load data (Li et al., 2018), which motivates '
    'variance-robust rather than pooled-variance comparisons; that study used 58 English households '
    'monitored from July to December 2011, so it establishes the general phenomenon rather than a '
    'North Carolina parameter.')
figure(3, 'Boxplots of Per-Household Mean Electrical Load (kW) for Monitored and Synthetic '
          'Households, July–December 2011', f'{OLD}/fig03_li_2018.png',
       'From Li et al. (2018), Energy and Buildings, licensed under CC BY 4.0.')
para(
    'Published evidence concentrates on Tennessee and Texas (Cawthorne et al., 2021), Florida '
    '(Fache & Bhat, 2024), and European systems (Colelli et al., 2023; Hu et al., 2024). Few '
    'analyses estimate both arms for North Carolina at the monthly statewide level or examine '
    'whether the arms have shifted. This study addresses that gap using public federal data.')

h1('Method')
h2('Data Sources')
para(
    'Statewide monthly degree days and mean temperature came from the National Oceanic and '
    'Atmospheric Administration’s nClimDiv dataset: the statewide cooling degree day '
    '(climdiv-cddcst), heating degree day (climdiv-hddcst), and mean temperature (climdiv-tmpcst) '
    'files, version 1.0.0 dated June 4, 2026, downloaded in June 2026 and filtered to state code '
    '031. Records carry a ten-character identifier in which characters 1–3 give the state, '
    'character 4 the division (0 for statewide), characters 5–6 the element, and characters 7–10 '
    'the year; the three files carry element codes 26, 25, and 02 respectively, consistent with '
    'their filenames. Values of −9999 denote missing data and were recoded. nClimDiv statewide '
    'values are area-weighted across climate divisions rather than population-weighted.')
para(
    'Monthly residential electricity sales, customer counts, and average revenue per kilowatt-hour '
    'came from the U.S. Energy Information Administration’s Form EIA-861M, in two extracts covering '
    'January 1990 through December 2009 and January 2010 onward, downloaded in June 2026 and '
    'filtered to North Carolina. Sales are in megawatt-hours and revenue in cents per kilowatt-hour. '
    'The two extracts share identical column headers, contain no overlapping year–month keys, and '
    'yielded no duplicate rows on concatenation.')
h2('Data Preparation and a Discontinuity in Customer Counts')
para(
    'The climate and sales series were joined on year and month. The join is one-to-one: the North '
    f'Carolina extract contains {int(R["N"])} unique year–month records, all of which matched, with '
    'no duplicate keys, no interior gaps in the monthly sequence, and no negative degree-day '
    f'values. The analysis sample is therefore {int(R["N"])} consecutive months, January 1990 '
    f'through April 2026. Annual quantities use only the {int(R["n_complete_years"])} complete '
    'calendar years, 1990 through 2025, because 2026 contributes four months.')
para(
    'Customer counts are reported from January 2007. Month-over-month percentage changes were '
    'computed after sorting by year and month and confirming that the customer series is '
    f'contiguous with no missing interior months. Six months show an absolute change above 2% (Table 1): a '
    f'step of {R["cust_jump_pct"]:+.1f}% at January 2008, and a cluster of five values between '
    f'June 2021 and February 2022 ranging from −2.79% to +3.22%. Excluding January 2008, '
    f'the largest absolute month-over-month change is {R["cust_other_max_pct"]:.2f}%; excluding '
    'January 2008 and the 2021–22 cluster as well, it falls to '
    f'{R["cust_excl_cluster_max"]:.2f}%.')
para(
    'The two anomalies differ in kind. The 2021–22 values oscillate in sign and net to '
    f'{R["cluster_net_pct"]:+.2f}% across the twelve months from May 2021 to April 2022, which is '
    'close to the surrounding annual growth rate; they move the series up and down rather than '
    'shifting its level. January 2008 is a one-way step that persists. Its size is difficult to '
    'reconcile with customer growth, and a change in survey coverage is the most obvious '
    'candidate, but no EIA documentation of a frame change in that period was retrieved for this '
    'study, so the cause is recorded as suspected rather than established.')
para(
    'The decision to exclude months before January 2008 does not rest on that diagnosis. In the '
    f'same month, January sales rose {R["jan08_yoy_sales"]:+.1f}% year over year while the customer '
    f'count rose {R["jan08_yoy_cust"]:+.1f}%. Customer counts increased far more sharply than '
    'sales, producing a discontinuity in sales per customer, so a per-customer trend estimated '
    f'across the break is not interpretable whatever produced the step. All per-customer analyses therefore use the '
    f'{int(R["n_pc"])} months from January 2008 onward rather than the {int(R["n_pc_all"])} months '
    'available from January 2007. The 2021–22 values are retained, because they are unusual but '
    'not evidently erroneous and they do not shift the level of the series; a sensitivity analysis '
    'removing them is reported in the Results. No observation was removed on the basis of its '
    'effect on any test statistic.')
table(1, 'Month-Over-Month Changes in Reported Residential Customer Counts Exceeding 2%',
      ['Month', 'Customers', 'Change from prior month'],
      [[f'{a["year"]}-{a["month"]:02d}', cm(a['customers']), f'{a["mom"]:+.2f}%']
       for a in R['cust_anomalies']],
      note='Computed on the contiguous January 2007 to April 2026 customer series after sorting '
           'by year and month. These are the only months whose absolute change exceeds 2%. '
           f'Excluding January 2008 the maximum absolute change is {R["cust_other_max_pct"]:.2f}%; '
           'excluding January 2008 and the 2021–22 cluster it is '
           f'{R["cust_excl_cluster_max"]:.2f}%.',
      widths=[1.3, 1.6, 2.2], aligns=['left', 'right', 'right'])
figure(4, 'Residential Customer Counts Reported in EIA-861M, January 2007 to April 2026',
       f'{FIG}04_customer_break.png',
       'The series steps up between December 2007 and January 2008 and does not return. The five '
       'values between June 2021 and February 2022 that also exceed 2% in absolute terms oscillate '
       'in sign and are retained. Months before January 2008, shaded, are excluded from all '
       'per-customer analyses.', width=6.1)
h2('Specifications')
para(
    'All tests used α = .05. The analysis proceeds through a specification ladder so that the '
    'consequences of the conventional cooling-only model can be measured rather than assumed. '
    'Table 2 defines every model in one place. Models 1 through 5 use monthly statewide sales as '
    'the outcome; Models 6 through 8 use sales per residential customer over the shorter window '
    'for which customer counts are usable.')
table(2, 'Model Definitions',
      ['Model', 'Outcome', 'Predictors', 'Sample'],
      [['1', 'Monthly sales', 'CDD', f'{int(R["N"])} months'],
       ['2', 'Monthly sales', 'CDD, HDD', f'{int(R["N"])} months'],
       ['3', 'Monthly sales', 'CDD, HDD, centred linear year', f'{int(R["N"])} months'],
       ['4', 'Monthly sales', 'CDD, HDD, centred linear year, 11 calendar-month indicators',
        f'{int(R["N"])} months'],
       ['5', 'Monthly sales', 'CDD', f'{M["M5"]["n"]} May–September months'],
       ['6', 'Sales per customer', 'CDD, HDD, centred linear year', f'{int(R["n_pc"])} months'],
       ['7', 'Sales per customer', 'Model 6 plus CDD × year and HDD × year',
        f'{int(R["n_pc"])} months'],
       ['8', 'Sales per customer', 'Model 7 plus 11 calendar-month indicators',
        f'{int(R["n_pc"])} months']],
      note='CDD and HDD are monthly degree-day totals relative to a 65 °F base. The linear year '
           'term is centred within each estimation sample: at the mean of the 1990–2026 window for '
           f'Models 1–5 and at {R["pc_tbar"]:.3f} for Models 6–8. Centring does not change fitted '
           'values or interaction coefficients, but it does change what the main effects '
           'represent, which matters for the proportional-trend contrast defined in the Results. '
           'Models 6–8 use the January 2008 to April 2026 window described above.',
      widths=[.7, 1.5, 2.85, 1.45], aligns=['center', 'left', 'left', 'left'])
para(
    'Models 3 and 4 are reported together throughout rather than one being designated correct, '
    'because they identify the degree-day coefficients from different variation. In Model 3 the '
    'coefficients are identified from all monthly variation, including the annual cycle, so any '
    'recurring seasonal influence on sales that co-moves with degree days — daylight hours, school '
    'and holiday calendars, seasonal occupancy — is available to be absorbed by the degree-day '
    'terms. In Model 4 the calendar-month indicators absorb everything common to a given month '
    'across years, so the degree-day coefficients are identified only from year-to-year deviations '
    'within each calendar month, after the trend. Interpreting Model 4’s coefficients as the '
    'weather response requires assuming that the within-calendar-month association is the '
    'quantity of interest and that the response does not differ systematically between the '
    'seasonal and the within-month margins.')
para(
    'The difference between the two sets of estimates therefore demonstrates sensitivity to how '
    'seasonality is handled. It does not establish that either model is unbiased, and the two '
    'estimates should not be read as lower and upper bounds on an underlying response: no result '
    'here identifies a true parameter, and coefficient heterogeneity or misspecification could '
    'place the quantity of interest outside the range they span. Both are reported, with the '
    'range described as a range across the specifications examined.')
h2('Inference')
para(
    'Ordinary least squares standard errors assume independent errors, which monthly energy data '
    'violate. Unless stated otherwise, every interval and p value reported for a time-series model '
    'in this paper uses Newey–West heteroscedasticity- and autocorrelation-consistent (HAC) '
    'standard errors with a Bartlett kernel, a maximum lag of 12 months, no prewhitening, and no '
    'finite-sample covariance multiplier, implemented directly from the sandwich formula (Newey & '
    'West, 1987). Robust Wald statistics are referred to the standard normal distribution; where '
    'the residual-degrees-of-freedom t reference would change a reported value it is given '
    'alongside. The covariance correction and the choice of reference distribution are separate '
    'decisions and are labelled separately. Ordinary standard errors appear beside the HAC ones in '
    'Table 4 so the two can be compared.')
para(
    'The 12-month maximum lag was fixed before the analyses reported here, on the ground that it '
    'spans one seasonal cycle of monthly data. It was not preregistered, and earlier drafts of '
    'this project examined bandwidth sensitivity, so results across maximum lags from 3 to 24 '
    'months are reported wherever a conclusion could plausibly turn on the choice. HAC estimation '
    'corrects the standard errors for serial correlation and heteroscedasticity of unknown form. '
    'It does not repair a misspecified conditional mean, does not make a model substantively '
    'correct, and does not license reading a robust standard error as evidence that the '
    'specification is right.')
para(
    'Serial correlation does not have a uniform effect on standard errors. For the cooling-only '
    'Model 1 the HAC standard error is smaller than the ordinary one at a 12-month lag and larger '
    'at shorter lags; for Models 3 and 4 it is larger at every lag examined. Both patterns are '
    'reported. An AR(1) feasible generalized least squares estimate is also reported for Models 1 '
    'and 3. Because that estimator imposes a different error structure as well as a different '
    'weighting, a difference between it and ordinary least squares indicates sensitivity to '
    'assumptions about the errors; it does not identify the source or direction of any bias.')
para(
    'Model 5 is estimated on the May-to-September months only. Because those rows are not '
    'contiguous in calendar time, forming lag products across consecutive rows of the filtered '
    'series would treat September and the following May as one month apart. Model 5 is therefore '
    'estimated with lag products formed at the actual calendar distance between the retained '
    'months: every ordered pair whose true separation is one to twelve months contributes at its '
    'Bartlett weight, including pairs that straddle the autumn-to-spring gap, such as September '
    'to the following May at a distance of eight months. Restricting products to pairs within a '
    'single May-to-September block would avoid treating that gap as one month but would discard '
    'those eligible cross-year pairs; both that variant and the naive calculation are reported in '
    'the Results so the differences are visible. Model 5 is retained as a descriptive comparison '
    'with earlier degree-day work rather than as a basis for any substantive claim.')
h2('Model-Implied Components')
para(
    'Multiplying a degree-day coefficient by mean annual degree-day exposure yields the portion of '
    'mean annual sales that the fitted model attributes to that term. These are additive '
    'regression components under the assumptions of the model, not metered end-use quantities. '
    'Degree-day exposures are treated as fixed historical totals, so the reported uncertainty '
    'reflects coefficient uncertainty only and excludes uncertainty about specification. The '
    'heating-to-cooling component ratio is a nonlinear function of two estimated coefficients, so '
    'its standard error was obtained by the delta method using the full joint covariance of the '
    'two coefficients, including their covariance, evaluated at the HAC covariance matrix.')
para(
    'Because a ratio can behave poorly under the delta method, a moving-block bootstrap is '
    'reported alongside it. The scheme resamples blocks of 12 consecutive observations of the '
    'paired outcome and design rows, with replacement, concatenating them to the original sample '
    'length; 4,000 resamples were drawn with a fixed random seed, and the interval runs between '
    'the 2.5 and 97.5 percentiles of the resampled ratio. Because blocks are reassembled in random order, the '
    'deterministic trend regressor is no longer in calendar order within a resample, so the '
    'procedure preserves short-range dependence but not the global trend structure. The bootstrap '
    'is therefore a secondary check on the delta-method interval rather than an independent '
    'estimate, and agreement between the two says nothing about specification uncertainty, which '
    'is the larger source of disagreement in these results.')
h2('Diagnostics and Robustness')
para(
    'Residual diagnostics for Models 1, 3, and 4 appear in Appendix Figures A1 through A3: '
    'residuals against fitted values, a residual histogram with a matched normal curve, a normal '
    'quantile–quantile plot, and the residual autocorrelation function. Robustness checks include a '
    'quadratic time trend, a per-calendar-day normalization of both sales and degree days, dropping '
    'the final three months of the series because EIA-861M reports recent months as preliminary and '
    'later revises them, correlations computed after removing a linear trend and on first and '
    'twelve-month differences, and a comparison of total and per-customer outcomes on a matched '
    'window.')

h1('Results')
h2('Descriptive Statistics')
para(
    f'The analysis sample contains {int(R["N"])} months from January 1990 through April 2026. Over '
    f'the {int(R["n_complete_years"])} complete calendar years, North Carolina averaged '
    f'{cm(R["ann_cdd"])} cooling degree days and {cm(R["ann_hdd"])} heating degree days per year, a '
    f'ratio of {num(R["hdd_cdd_ratio"])} heating to cooling degree days. Monthly residential sales '
    f'averaged {cm(R["mean_sales"])} MWh (SD = {cm(R["sd_sales"])}). Table 3 reports the monthly '
    'variables, and Figure 5 plots sales against mean monthly temperature. Both arms are visible in '
    'the raw data.')
table(3, 'Descriptive Statistics for Monthly Climate and Electricity Variables, January 1990–April 2026',
      ['Variable', 'n', 'M', 'SD', 'Min', 'Max'],
      [['Residential sales (MWh)', f'{int(R["N"])}', cm(R['mean_sales']), cm(R['sd_sales']),
        cm(R['min_sales']), cm(R['max_sales'])],
       ['Cooling degree days', f'{int(R["N"])}', f'{R["mean_cdd"]:.1f}', f'{R["sd_cdd"]:.1f}', '0',
        f'{int(R["max_cdd"])}'],
       ['Heating degree days', f'{int(R["N"])}', f'{R["mean_hdd"]:.1f}', f'{R["sd_hdd"]:.1f}', '0',
        f'{int(R["max_hdd"])}'],
       ['Mean temperature (°F)', f'{int(R["N"])}', f'{R["mean_tavg"]:.1f}', f'{R["sd_tavg"]:.1f}',
        f'{R["min_tavg"]:.1f}', f'{R["max_tavg"]:.1f}'],
       ['~Mean monthly sales by season', '', '', '', '', ''],
       ['~   Winter (Dec–Feb)', f'{S["Winter"]["n"]}', cm(S['Winter']['mean']), cm(S['Winter']['sd']), '', ''],
       ['~   Spring (Mar–May)', f'{S["Spring"]["n"]}', cm(S['Spring']['mean']), cm(S['Spring']['sd']), '', ''],
       ['~   Summer (Jun–Aug)', f'{S["Summer"]["n"]}', cm(S['Summer']['mean']), cm(S['Summer']['sd']), '', ''],
       ['~   Fall (Sep–Nov)', f'{S["Fall"]["n"]}', cm(S['Fall']['mean']), cm(S['Fall']['sd']), '', '']],
      note='Degree days are relative to a 65 °F base. Minimum and maximum are omitted for the '
           'seasonal rows. Seasonal standard deviations are the standard deviations of monthly '
           'sales within each season across the study window.',
      widths=[2.45, .5, 1.1, 1.0, .9, .85],
      aligns=['left', 'center', 'right', 'right', 'right', 'right'])
figure(5, 'Monthly Residential Electricity Sales Against Mean Monthly Temperature',
       f'{FIG}05_response_function.png',
       'Each point is one month, colored by meteorological season. The solid curve is a locally '
       'weighted regression fit, shown as a descriptive summary with no inferential interpretation. '
       'The dashed line marks the 65 °F degree-day base. Sales are plotted in gigawatt-hours '
       '(1 GWh = 1,000 MWh); statistics in the text are in megawatt-hours.')
h2('What Changes When Heating and Temporal Structure Are Added')
para(
    f'Monthly CDD alone (Model 1) explained R² = {nz(M["M1"]["r2"])} of the variance in monthly '
    f'sales, with a slope of {cm(M["M1"]["coef"]["CDD"]["b"])} MWh per cooling degree day, 95% CI '
    f'[{cm(M["M1"]["coef"]["CDD"]["lo"])}, {cm(M["M1"]["coef"]["CDD"]["hi"])}]. Figure 6 '
    f'shows why the fit is poor: the {int(R["zero_cdd_n"])} months recording zero cooling degree '
    'days span nearly the full range of the outcome, because a cooling variable cannot distinguish '
    'a mild November from a severe January.')
figure(6, 'Monthly Cooling Degree Days and Residential Electricity Sales',
       f'{FIG}06_cdd_scatter.png',
       'Points are colored by meteorological season. The line and shaded band show the Model 1 '
       'ordinary least squares fit and its 95% ordinary least squares confidence band; inference '
       'reported in the text uses HAC standard errors and does not correspond to this band.')
para(
    f'Adding heating degree days raised R² from {nz(M["M1"]["r2"])} to {nz(M["M2"]["r2"])}, and '
    f'adding a linear trend raised it to {nz(M["M3"]["r2"])}; calendar-month effects raised it '
    f'further to {nz(M["M4"]["r2"])} (Table 4). The cooling slope also moved substantially. Model '
    f'3 places it {R["pct_increase_m1_to_m3"]:.0f}% above the Model 1 value, which is equivalent to '
    f'saying that the Model 1 estimate lies {R["pct_m1_below_m3"]:.0f}% below the Model 3 estimate. '
    'The two figures describe the same gap from opposite directions and are easily confused. The '
    'movement is consistent with omitted-variable bias from excluding the heating arm, since '
    'zero-CDD months carry high heating loads and pull the fitted intercept upward at the expense '
    'of the slope, but the size of any bias relative to an unknown true parameter cannot be read '
    'off a comparison between two fitted models.')
para(
    'An AR(1) feasible generalized least squares fit of Model 1 gives a cooling slope of '
    f'{cm(M["M1"]["gls"]["b_cdd"])} MWh per cooling degree day against the ordinary least squares '
    f'value of {cm(M["M1"]["coef"]["CDD"]["b"])}, with an estimated autocorrelation parameter of '
    f'{num(M["M1"]["gls"]["rho"])}. Applied to Model 3 the same estimator gives '
    f'{cm(M["M3"]["gls"]["b_cdd"])} against {cm(M["M3"]["coef"]["CDD"]["b"])}, a much smaller '
    'change. The Model 1 estimate is therefore sensitive to the assumed error structure and the '
    'Model 3 estimate is comparatively stable, which is evidence about specification sensitivity '
    'rather than about the direction of bias in either estimate.')
LADDER = [('1', 'Sales ~ CDD', 'M1'),
          ('2', 'Sales ~ CDD + HDD', 'M2'),
          ('3', 'Sales ~ CDD + HDD + year', 'M3'),
          ('4', 'Sales ~ CDD + HDD + year + month effects', 'M4'),
          ('5', 'Cooling season: Sales ~ CDD', 'M5')]
def cell(k, v):
    c = M[k]['coef'].get(v)
    if c is None:
        return '—'
    if k == 'M5':
        return f"{cm(c['b'])}\n({cm(R['m5_ols_se'])})\n[{cm(R['m5_hac_cal_se'])}]"
    return f"{cm(c['b'])}\n({cm(c['ols_se'])})\n[{cm(c['se'])}]"
table(4, 'Regression Models Predicting Monthly Residential Electricity Sales',
      ['Model', 'Specification', 'CDD', 'HDD', 'Year', 'R²', 'DW'],
      [[num_, spec, cell(k, 'CDD'), cell(k, 'HDD'), cell(k, 'Year'),
        nz(M[k]['r2']), f'{M[k]["dw"]:.2f}']
       for num_, spec, k in LADDER],
      note=f'N = {int(R["N"])} months for Models 1–4 and {M["M5"]["n"]} May–September months '
           'for Model 5; full definitions in Table 2. Entries are unstandardized coefficients '
           'in MWh per degree day, or MWh per year for the trend, with ordinary least squares '
           'standard errors in parentheses and heteroscedasticity- and '
           'autocorrelation-consistent standard errors in brackets. HAC errors use a Bartlett '
           'kernel with a 12-month maximum lag; for Model 5 they are computed at actual calendar '
           'distance between the retained May–September months, as described in the Method. All '
           'coefficients shown are significant at p < .001 under both estimators. DW = '
           'Durbin–Watson statistic; values below 2 indicate positive residual autocorrelation. '
           'Models 6–8, which use sales per customer over a shorter window, are reported in '
           'Table 8.',
      widths=[.65, 2.15, .85, .8, .9, .53, .52],
      aligns=['center', 'left', 'center', 'center', 'center', 'center', 'center'])
para(
    'Table 4 also shows that the HAC and ordinary standard errors do not stand in a fixed '
    'relationship. For Model 1 the HAC standard error on the cooling slope is smaller than the '
    f'ordinary one at the 12-month bandwidth, {R["bw_sweep"]["M1"]["12"]:.0f} against '
    f'{R["bw_sweep"]["M1"]["ols"]:.0f}, and larger at shorter bandwidths, reaching '
    f'{R["bw_sweep"]["M1"]["3"]:.0f} at three months. For Model 3 the HAC standard error exceeds '
    f'the ordinary one at every bandwidth examined, rising from {R["bw_sweep"]["M3"]["3"]:.0f} at '
    f'three months to {R["bw_sweep"]["M3"]["24"]:.0f} at 24 months against an ordinary value of '
    f'{R["bw_sweep"]["M3"]["ols"]:.0f}. The direction of the correction is therefore a property of the '
    'model and bandwidth rather than a general consequence of autocorrelation.')
figure(7, 'Added-Variable Plots for the Cooling and Heating Terms of Model 3',
       f'{FIG}07_two_arms.png',
       'Each panel plots residualized sales against one residualized degree-day variable, holding '
       'the other degree-day variable and the linear trend constant. Lines and shaded bands are '
       'ordinary least squares fits with 95% ordinary least squares bands; the coefficient '
       'intervals printed in each panel are HAC intervals and are the ones reported in the text.',
       width=6.2)
h2('Model-Implied Heating and Cooling Components')
para(
    f'In Model 3 each cooling degree day is associated with {cm(CP["M3"]["b_cdd"])} MWh of monthly '
    f'sales, 95% CI [{cm(M["M3"]["coef"]["CDD"]["lo"])}, {cm(M["M3"]["coef"]["CDD"]["hi"])}], '
    f'and each heating degree day with {cm(CP["M3"]["b_hdd"])} MWh, 95% CI '
    f'[{cm(M["M3"]["coef"]["HDD"]["lo"])}, {cm(M["M3"]["coef"]["HDD"]["hi"])}], a slope '
    f'ratio of {num(CP["M3"]["slope_ratio"])}. In Model 4 the same slopes are '
    f'{cm(CP["M4"]["b_cdd"])} and {cm(CP["M4"]["b_hdd"])}, a ratio of '
    f'{num(CP["M4"]["slope_ratio"])}. Multiplying each slope by mean annual degree-day exposure '
    'converts these into model-implied components of mean annual sales (Table 5, Figure 8).')
table(5, 'Model-Implied Annual Components of Residential Sales Under Two Specifications',
      ['Quantity', 'Model 3', 'Model 4'],
      [['Cooling slope (MWh per CDD)', cm(CP['M3']['b_cdd']), cm(CP['M4']['b_cdd'])],
       ['Heating slope (MWh per HDD)', cm(CP['M3']['b_hdd']), cm(CP['M4']['b_hdd'])],
       ['Slope ratio (cooling ÷ heating)', num(CP['M3']['slope_ratio']), num(CP['M4']['slope_ratio'])],
       ['Cooling component (million MWh)', f'{CP["M3"]["e_cool"]/1e6:.1f}', f'{CP["M4"]["e_cool"]/1e6:.1f}'],
       ['Heating component (million MWh)', f'{CP["M3"]["e_heat"]/1e6:.1f}', f'{CP["M4"]["e_heat"]/1e6:.1f}'],
       ['Cooling share of annual sales', f'{CP["M3"]["share_cool"]:.1%}', f'{CP["M4"]["share_cool"]:.1%}'],
       ['Heating share of annual sales', f'{CP["M3"]["share_heat"]:.1%}', f'{CP["M4"]["share_heat"]:.1%}'],
       ['~Heating ÷ cooling component', f'~{num(CP["M3"]["ratio"])}', f'~{num(CP["M4"]["ratio"])}'],
       ['   HAC delta-method 95% CI',
        f'[{num(CP["M3"]["lo"])}, {num(CP["M3"]["hi"])}]',
        f'[{num(CP["M4"]["lo"])}, {num(CP["M4"]["hi"])}]'],
       ['   Moving-block bootstrap 95% CI',
        f'[{num(CP["M3"]["boot_lo"])}, {num(CP["M3"]["boot_hi"])}]',
        f'[{num(CP["M4"]["boot_lo"])}, {num(CP["M4"]["boot_hi"])}]']],
      note=f'Components are the fitted coefficient multiplied by mean annual exposure over the '
           f'{int(R["n_complete_years"])} complete calendar years ({cm(R["ann_cdd"])} CDD and '
           f'{cm(R["ann_hdd"])} HDD), against mean annual sales of {cm(R["ann_sales"])} MWh. These '
           'are additive regression components under each model’s assumptions, not metered end-use '
           'quantities. Degree-day exposures are treated as fixed historical totals, so intervals '
           'reflect coefficient uncertainty only and exclude uncertainty about specification. The '
           'delta-method interval uses the full joint HAC covariance of the two coefficients, '
           'including their covariance, which is substantial (HAC correlation '
           f'{num(CP["M3"]["corr"])} in Model 3 and {num(CP["M4"]["corr"])} in Model 4). '
           'The bootstrap uses 12-month moving blocks and 4,000 resamples.',
      widths=[2.9, 1.8, 1.8], aligns=['left', 'right', 'right'])
figure(8, 'Model-Implied Decomposition of Mean Annual Residential Sales Under Two Specifications',
       f'{FIG}08_decomposition.png',
       'Cooling and heating components are the fitted degree-day coefficients multiplied by mean '
       'annual degree-day exposure. The remainder is the balance of mean annual sales not '
       'attributed to either degree-day term by that model; it is a modelling residual and is not a '
       'measurement of weather-independent appliance consumption.', width=6.3)
para(
    'Both specifications place the heating component above the cooling component, so the ordering '
    'is stable. Its magnitude is not: the implied ratio is '
    f'{num(CP["M3"]["ratio"])} under Model 3, a gap of about {abs(CP["M3"]["ratio"]-1)*100:.0f}%, '
    f'and {num(CP["M4"]["ratio"])} under Model 4, a gap of about '
    f'{abs(CP["M4"]["ratio"]-1)*100:.0f}%. Neither interval in Table 5 conveys that spread, because '
    'each describes coefficient uncertainty within one model. For that reason no single ratio is '
    'reported as a headline result. The defensible statement is that the two components are of '
    'broadly comparable size, with the heating component at least as large as the cooling '
    'component, across the specifications examined. Three further checks left the Model 3 ratio '
    f'essentially unchanged: a quadratic trend gave {num(R["sens"]["quadratic_trend"]["ratio"])}, '
    f'normalizing both series per calendar day gave {num(R["sens"]["per_day"]["ratio"])}, and '
    'dropping the final three months, which EIA reports as preliminary, gave '
    f'{num(R["sens"]["drop_last3"]["ratio"])}. The spread between Models 3 and 4 is thus specific '
    'to the treatment of calendar-month effects and is not an artifact of trend form, month length, '
    'or provisional data.')
h2('Seasonal Structure')
para(
    'Table 6 reports differences between seasonal mean monthly sales with HAC intervals, obtained '
    'by regressing sales on season indicators and applying the same 12-month Bartlett kernel. This '
    'replaces the Welch procedure used in earlier versions of this analysis. Welch tests relax the '
    'equal-variance assumption but still treat observations as independent, which monthly sales are '
    'not, and the choice of procedure changes one conclusion: the Spring–Fall difference is not '
    f'distinguishable from zero under a Welch test, {p(R["seas"]["Spring-Fall"]["p_welch_bonf"])}, but is '
    f'distinguishable under HAC inference, {p(R["seas"]["Spring-Fall"]["p_bonf"])}. The Winter–Summer '
    'difference remains indistinguishable from zero under both, with a HAC interval of '
    f'[{cm(R["seas"]["Winter-Summer"]["lo"])}, {cm(R["seas"]["Winter-Summer"]["hi"])}] MWh.')
table(6, 'Differences Between Seasonal Mean Monthly Sales, With Dependence-Robust Intervals',
      ['Comparison', 'M difference (MWh)', 'HAC 95% CI', 'p (HAC)', 'p (Welch)'],
      [[k.replace('-', ' − '), cm(v['diff']),
        f'[{cm(v["lo"])}, {cm(v["hi"])}]',
        ('1.00' if v['p_bonf'] > .995 else (nz(v['p_bonf'], 3) if v['p_bonf'] >= .001 else '< .001')),
        ('1.00' if v['p_welch_bonf'] > .995 else (nz(v['p_welch_bonf'], 3) if v['p_welch_bonf'] >= .001 else '< .001'))]
       for k, v in R['seas'].items()],
      note='Differences are between mean monthly sales within each season across the study window. '
           'HAC intervals and p values come from a regression of monthly sales on season indicators '
           'with Newey–West standard errors (Bartlett kernel, 12-month bandwidth); Welch p values '
           'are from pairwise unequal-variance t tests treating months as independent. Both sets of '
           'p values are Bonferroni-corrected for six comparisons. The between-season share of '
           f'total variance in monthly sales is {nz(R["eta2"])}, reported as a descriptive '
           'proportion computed from the classical sums of squares; it is not an effect size '
           'attached to either test and carries no dependence-robust interpretation.',
      widths=[1.5, 1.2, 2.15, .8, .8],
      aligns=['left', 'right', 'center', 'right', 'right'])
figure(9, 'Seasonal Distributions of Monthly Residential Sales and Pairwise Differences',
       f'{FIG}09_seasonal.png',
       'Left: boxes span the interquartile range, horizontal lines mark medians, and diamonds mark '
       'seasonal means. Right: points are differences in seasonal mean monthly sales with '
       'Newey–West 95% intervals, uncorrected for multiplicity; the Bonferroni-corrected p values '
       'appear in Table 6.', width=6.3)
para(
    f'Across {int(R["pair_n"])} matched years, mean July sales ({cm(R["pair_jul"])} MWh) exceeded '
    f'mean January sales ({cm(R["pair_jan"])} MWh) by {cm(R["pair_diff"])} MWh '
    f'(SD = {cm(R["pair_sd"])}), which is not distinguishable from zero, '
    f't({int(R["pair_n"])-1}) = {num(R["pair_t"])}, {p(R["pair_p2"])} (two-sided), 95% CI '
    f'[{cm(R["pair_ci95_lo"])}, {cm(R["pair_ci95_hi"])}]. The annual differences show no material '
    f'serial dependence (lag-1 r = {num(R["pair_lag1"])}, Durbin–Watson = {num(R["pair_dw"])}), so '
    'treating the 36 paired differences as independent is defensible even though the underlying '
    'monthly series is not.')
para(
    'A failure to reject is not evidence of equality, so equivalence was tested directly with two '
    'one-sided tests (Lakens, 2017). Equivalence was established against a margin of ±0.4 standard '
    f'deviations of the paired difference, {p(R["tost"]["0.4"]["pmax"])}, and against ±0.5 standard '
    f'deviations, {p(R["tost"]["0.5"]["pmax"])}; equivalence was not established against ±0.3 '
    f'standard deviations, {p(R["tost"]["0.3"]["pmax"])}. At α = .05 these conclusions correspond '
    'to the 90% confidence interval on the mean difference, '
    f'[{cm(R["pair_ci90_lo"])}, {cm(R["pair_ci90_hi"])}] MWh, lying inside the stated bounds; the '
    f'95% interval, [{cm(R["pair_ci95_lo"])}, {cm(R["pair_ci95_hi"])}] MWh, also falls inside the '
    '±0.4 and ±0.5 bounds, which is a separate and slightly stronger statement (Figure 10, Table 7). '
    'The margins were not specified in advance. They describe how large a difference these data can '
    'rule out rather than testing a threshold justified on planning or engineering grounds, and '
    'they should be read as exploratory. None of this establishes that the two months are exactly '
    'equal, and all of it concerns mean monthly energy for two specific calendar months, not '
    'seasonal maxima, peak power, or any other pair of months.')
table(7, 'Paired Comparison and Equivalence Tests, July Versus January Monthly Sales',
      ['Test', 'Bound (MWh)', 'p', 'Conclusion'],
      [[f'Paired t test, t({int(R["pair_n"])-1}) = {num(R["pair_t"])}', '—',
        nz(R['pair_p2'], 3), 'Fail to reject the null'],
       ['Equivalence test, ±0.3 SD', f'±{cm(R["tost"]["0.3"]["bound"])}',
        nz(R['tost']['0.3']['pmax'], 3), 'Equivalence not established'],
       ['Equivalence test, ±0.4 SD', f'±{cm(R["tost"]["0.4"]["bound"])}',
        nz(R['tost']['0.4']['pmax'], 3), 'Equivalence established'],
       ['Equivalence test, ±0.5 SD', f'±{cm(R["tost"]["0.5"]["bound"])}',
        nz(R['tost']['0.5']['pmax'], 3), 'Equivalence established']],
      note=f'n = {int(R["pair_n"])} matched years, 1990–2025. Mean difference = '
           f'{cm(R["pair_diff"])} MWh, 95% CI [{cm(R["pair_ci95_lo"])}, {cm(R["pair_ci95_hi"])}], '
           f'standardized mean difference = {num(R["pair_dz"])}. Equivalence bounds are multiples '
           'of the standard deviation of the paired difference, converted to megawatt-hours; they '
           'were chosen after seeing the data and are exploratory. For equivalence rows p is the '
           'larger of the two one-sided test p values.',
      widths=[2.6, 1.2, .75, 1.85], aligns=['left', 'right', 'right', 'left'])
figure(10, 'July Versus January Sales, Paired by Year, With Equivalence Bounds',
       f'{FIG}10_paired_equivalence.png',
       'Left: each line connects one year’s January and July values; color indicates which month '
       'was higher, and diamonds mark the two means. Right: the mean paired difference with its 90% '
       'and 95% confidence intervals against the three equivalence margins. At α = .05 equivalence '
       'corresponds to the 90% interval lying inside a margin.', width=6.3)
h2('Stability of the Per-Customer Response')
para(
    'The remaining question is whether the response itself has changed. Because customer counts '
    'begin in 2007 and carry the discontinuity described in the Method, this analysis uses the '
    f'{int(R["n_pc"])} months from January 2008 to April 2026, a span of 18 years and 4 months, '
    'with sales per customer as the outcome. The primary estimates come from pooled models '
    'interacting both degree-day terms with the centred trend (Models 7 and 8 in Table 2); Model 6 '
    'without interactions is reported alongside. Annual slopes fitted separately within each '
    'calendar year appear in Figure 11 as a visualization and an influence check, not as the '
    'primary estimate, because each rests on 12 observations.')
para(
    'Cooling sensitivity declined in both pooled specifications. The CDD-by-trend interaction was '
    f'{sci(M["M7"]["coef"]["CDDxYear"]["b"])} per year in Model 7, 95% CI '
    f'[{sci(M["M7"]["coef"]["CDDxYear"]["lo"])}, {sci(M["M7"]["coef"]["CDDxYear"]["hi"])}], '
    f'{p(M["M7"]["coef"]["CDDxYear"]["p_norm"])}, and {sci(M["M8"]["coef"]["CDDxYear"]["b"])} per '
    f'year in Model 8, {p(M["M8"]["coef"]["CDDxYear"]["p_norm"])}. Evaluated at the first and last '
    f'observations these imply declines of {abs(M["M7"]["pct_cdd"])*100:.0f}% and '
    f'{abs(M["M8"]["pct_cdd"])*100:.0f}%. These are estimates from two specifications, not '
    'endpoints of a confidence interval. Ordinary and HAC inference diverge for Model 7, where the '
    f'ordinary p value is {nz(M["M7"]["coef"]["CDDxYear"]["ols_p"], 3)} and the HAC p value is '
    f'{nz(M["M7"]["coef"]["CDDxYear"]["p_norm"], 4)}; both appear in Table 8. Across maximum lags '
    'from 3 to 24 months the HAC p value for this coefficient stays at or below '
    f'{max(v["p"] for k, v in R["bw_interaction"]["M7"].items() if k != "0"):.3f} in Model 7 and '
    'below .001 in Model 8, so the cooling decline does not turn on the lag choice.')
para(
    'The heating interaction was also negative in both models, '
    f'{sci(M["M7"]["coef"]["HDDxYear"]["b"])} per year in Model 7, '
    f'{p(M["M7"]["coef"]["HDDxYear"]["p_norm"])}, and {sci(M["M8"]["coef"]["HDDxYear"]["b"])} in '
    f'Model 8, {p(M["M8"]["coef"]["HDDxYear"]["p_norm"])}. The Model 7 interval includes zero and '
    'the Model 8 interval does not. A nonsignificant heating interaction is not evidence that '
    'heating sensitivity was constant: the estimate is negative in both models and its interval '
    'spans declines of practical size.')
para(
    'Whether the cooling decline was proportionally larger than the heating decline is a third '
    'question, separate from either trend on its own, and it is the one that depends on '
    'specification. The two trends were contrasted on a common proportional scale, comparing each '
    'interaction coefficient with its own main effect, g = β(CDD × year) ÷ β(CDD) − β(HDD × year) '
    '÷ β(HDD), with the standard error from the delta method using the full joint HAC covariance. '
    'Because the main effects enter the denominators, the contrast is evaluated where the trend '
    'term is zero. The trend is centred at the mean of the estimation window, '
    f'{R["pc_tbar"]:.3f}, so the comparison is made at the midpoint of the period rather than at '
    'either endpoint. Centring elsewhere leaves the interaction coefficients unchanged but shifts '
    'the main effects and therefore the contrast, so the reference point is stated rather than '
    'left implicit.')
para(
    f'In Model 7 the contrast was {M["M7"]["contrast"]["b"]:+.5f} per year, HAC SE '
    f'{M["M7"]["contrast"]["se"]:.5f}, 95% CI [{M["M7"]["contrast"]["lo"]:+.5f}, '
    f'{M["M7"]["contrast"]["hi"]:+.5f}], {p(M["M7"]["contrast"]["p_norm"])} against a standard '
    f'normal reference and {p(M["M7"]["contrast"]["p_t"])} against a t reference with '
    f'{M["M7"]["contrast"]["dof"]} residual degrees of freedom. In Model 8 it was '
    f'{M["M8"]["contrast"]["b"]:+.5f} per year, HAC SE {M["M8"]["contrast"]["se"]:.5f}, 95% CI '
    f'[{M["M8"]["contrast"]["lo"]:+.5f}, {M["M8"]["contrast"]["hi"]:+.5f}], '
    f'{p(M["M8"]["contrast"]["p_norm"])} and {p(M["M8"]["contrast"]["p_t"])}. The difference '
    'between the two is not an artifact of the lag choice: across maximum lags from 3 to 24 months '
    f'the Model 7 contrast p value ranges from '
    f'{min(v["p"] for v in R["bw_contrast"]["M7"].values()):.3f} to '
    f'{max(v["p"] for v in R["bw_contrast"]["M7"].values()):.3f}, and the Model 8 contrast from '
    f'{min(v["p"] for v in R["bw_contrast"]["M8"].values()):.3f} to '
    f'{max(v["p"] for v in R["bw_contrast"]["M8"].values()):.3f}. Evidence that the cooling '
    'decline exceeded the heating decline depends on whether calendar-month effects are included, '
    'and this paper does not treat the difference as established.')
table(8, 'Per-Customer Degree-Day Models and the Proportional-Trend Contrast',
      ['Estimate', 'Model 6', 'Model 7', 'Model 8'],
      [['CDD main effect', sci(M['M6']['coef']['CDD']['b']), sci(M['M7']['coef']['CDD']['b']),
        sci(M['M8']['coef']['CDD']['b'])],
       ['HDD main effect', sci(M['M6']['coef']['HDD']['b']), sci(M['M7']['coef']['HDD']['b']),
        sci(M['M8']['coef']['HDD']['b'])],
       ['CDD × year', '—', sci(M['M7']['coef']['CDDxYear']['b']),
        sci(M['M8']['coef']['CDDxYear']['b'])],
       ['   OLS p', '—', pv(M['M7']['coef']['CDDxYear']['ols_p']),
        pv(M['M8']['coef']['CDDxYear']['ols_p'])],
       ['   HAC p (normal reference)', '—', pv(M['M7']['coef']['CDDxYear']['p_norm']), '< .001'],
       ['   Implied change over window', '—', f'{M["M7"]["pct_cdd"]*100:+.1f}%',
        f'{M["M8"]["pct_cdd"]*100:+.1f}%'],
       ['HDD × year', '—', sci(M['M7']['coef']['HDDxYear']['b']),
        sci(M['M8']['coef']['HDDxYear']['b'])],
       ['   OLS p', '—', pv(M['M7']['coef']['HDDxYear']['ols_p']),
        pv(M['M8']['coef']['HDDxYear']['ols_p'])],
       ['   HAC p (normal reference)', '—', pv(M['M7']['coef']['HDDxYear']['p_norm']),
        pv(M['M8']['coef']['HDDxYear']['p_norm'])],
       ['   Implied change over window', '—', f'{M["M7"]["pct_hdd"]*100:+.1f}%',
        f'{M["M8"]["pct_hdd"]*100:+.1f}%'],
       ['~Proportional-trend contrast g', '~—', f'~{M["M7"]["contrast"]["b"]:+.5f}',
        f'~{M["M8"]["contrast"]["b"]:+.5f}'],
       ['   HAC SE', '—', f'{M["M7"]["contrast"]["se"]:.5f}', f'{M["M8"]["contrast"]["se"]:.5f}'],
       ['   95% CI (normal reference)', '—',
        f'[{M["M7"]["contrast"]["lo"]:+.5f}, {M["M7"]["contrast"]["hi"]:+.5f}]',
        f'[{M["M8"]["contrast"]["lo"]:+.5f}, {M["M8"]["contrast"]["hi"]:+.5f}]'],
       ['   p (normal / t reference)', '—',
        f'{pv(M["M7"]["contrast"]["p_norm"])} / {pv(M["M7"]["contrast"]["p_t"])}',
        f'{pv(M["M8"]["contrast"]["p_norm"])} / {pv(M["M8"]["contrast"]["p_t"])}'],
       ['Model R²', nz(M['M6']['r2']), nz(M['M7']['r2']), nz(M['M8']['r2'])],
       ['Durbin–Watson', f'{M["M6"]["dw"]:.2f}', f'{M["M7"]["dw"]:.2f}', f'{M["M8"]["dw"]:.2f}']],
      note=f'n = {int(R["n_pc"])} months, January 2008 to April 2026. The outcome is sales per '
           'residential customer in MWh; main effects are MWh per customer per degree day and '
           'interactions are MWh per customer per degree day per year. The trend is centred at '
           f'{R["pc_tbar"]:.3f}, so main effects and the contrast are evaluated at the midpoint of '
           'the window. Implied change evaluates the fitted slope at the first and last '
           'observations. HAC standard errors use a Bartlett kernel with a 12-month maximum lag.',
      widths=[2.15, 1.3, 1.5, 1.55], aligns=['left', 'right', 'right', 'right'])
figure(11, 'Annual Per-Customer Response Slopes and the Proportional-Trend Contrast',
       f'{FIG}11_stability.png',
       'Left and centre: each point is a slope from a separate regression of sales per customer on '
       'cooling and heating degree days fitted within one calendar year, with 95% ordinary least '
       'squares error bars reflecting that year’s 12 observations; lines and shaded bands are '
       'ordinary least squares trends through the annual slopes. Right: the proportional-trend '
       'contrast from each pooled model with its Newey–West 95% interval and normal-reference p '
       'value. The annual fits support the figure; the estimates in the text come from the pooled '
       'models in Table 8.', width=6.4)
para(
    'Table 9 reports how these results respond to the estimation window. Excluding the five '
    '2021–22 months identified in Table 1 leaves everything essentially unchanged, with the Model '
    f'8 contrast at {p(EX["2008-2026 less 2021-22 anomalies"]["fe"]["p_contrast"])} and the Model 7 '
    f'contrast at {p(EX["2008-2026 less 2021-22 anomalies"]["nofe"]["p_contrast"])}. Beginning in '
    'January 2009 leaves the cooling decline significant in both models and weakens the Model 8 '
    f'contrast to {p(EX["2009-2026"]["fe"]["p_contrast"])}. Retaining 2007, which the Method '
    'rejects, makes the apparent cooling decline larger but moves both contrasts well away from '
    f'significance, {p(EX["2007-2026 (2007 retained)"]["fe"]["p_contrast"])} with calendar-month '
    'effects. The cooling decline is present in every window examined; the contrast is significant '
    'only with calendar-month effects, and then only for windows beginning in 2008.')
table(9, 'Sensitivity of the Per-Customer Results to the Estimation Window',
      ['Window', 'n', 'CDD × year p', 'Implied cooling change', 'Contrast p'],
      [[lab, str(v['fe']['n']),
        f'{pv(v["nofe"]["p_cddxyear"])} / {pv(v["fe"]["p_cddxyear"])}',
        f'{v["nofe"]["pct_cdd"]*100:+.1f}% / {v["fe"]["pct_cdd"]*100:+.1f}%',
        f'{pv(v["nofe"]["p_contrast"])} / {pv(v["fe"]["p_contrast"])}']
       for lab, v in EX.items()],
      note='Each cell reports the value without calendar-month effects (Model 7 form) and then '
           'with them (Model 8 form). All p values are HAC with a 12-month maximum lag against a '
           'standard normal reference. The first row is the specification used throughout. No '
           'window was chosen on the basis of its results.',
      widths=[2.0, .45, 1.25, 1.55, 1.2],
      aligns=['left', 'center', 'right', 'right', 'right'])
h2('Robustness')
para(
    'Removing a linear time trend from both series raised the CDD–sales correlation from '
    f'{nz(R["r_all"])} to {nz(R["r_detrend"])}; the correlation on first differences was '
    f'{nz(R["r_diff1"])} and on twelve-month differences {nz(R["r_diff12"])}. Each transformation '
    'removes a shared linear or seasonal component and the association persists under all three, '
    'which is evidence against a purely spurious relationship of the kind Granger and Newbold '
    '(1974) described. It does not establish that no shared influence remains: each transformation '
    'removes only the component it targets, and inference on transformed series carries its own '
    'assumptions.')
para(
    'On the matched January 2008 to April 2026 window the CDD correlation was '
    f'{nz(R["match_total_r"])} for total sales and {nz(R["match_pc_r"])} for sales per customer, so '
    'per-customer normalization does not by itself change the strength of the association. '
    'Comparing a per-customer correlation on a short window against a total-sales correlation on '
    'the full window would confound normalization with the change of period. Heating degree days '
    f'correlated with winter sales at {nz(R["win_hdd_r"])} and cooling degree days with summer '
    f'sales at {nz(R["sum_cdd_r"])}; these are computed on different months with different '
    'predictor distributions and cannot rank the sensitivity of the two arms, which is why the '
    'arms are compared through the joint models instead.')
para(
    'Restricting Model 1 to cooling-season months raised R² to '
    f'{nz(M["M5"]["r2"])} with a slope of {cm(R["m5_slope"])} MWh per cooling degree day. '
    'Subsetting does not restore independence. Residual autocorrelation between genuinely adjacent '
    f'months within the May-to-September blocks, computed across the {int(R["cool_lag1_npairs"])} '
    f'within-block pairs, was {nz(R["cool_lag1_within"])}. The same quantity computed naively '
    f'across consecutive rows of the filtered series is {nz(R["cool_lag1_naive"])}, a different '
    'number arrived at by treating September and the following May as one month apart. The same '
    'error affects HAC estimation on filtered data. A naive Newey–West standard error for the '
    f'Model 5 slope is {num(R["m5_hac_naive_se"], 1)}. Forming lag products only within a single '
    f'May-to-September block gives {num(R["m5_hac_block_se"], 1)}, which avoids that error but '
    'discards pairs lying genuinely within twelve months of each other across a year boundary. '
    'Using the actual calendar distance between the retained months, so that all '
    f'{int(R["m5_pairs_total"])} eligible ordered pairs contribute at their Bartlett weights '
    f'({int(R["m5_pairs_cross"])} of them cross-year and {int(R["m5_pairs_within"])} within-year), '
    f'gives {num(R["m5_hac_cal_se"], 1)}, against an ordinary standard error of '
    f'{num(R["m5_ols_se"], 1)}. The calendar-distance figure is the one reported in Table 4. '
    'Model 5 remains a descriptive comparison with earlier degree-day work and carries no '
    'substantive claim in this paper.')
para(
    'Residual diagnostics appear in Appendix Figures A1 through A3. Model 1 residuals are strongly '
    f'autocorrelated (lag-1 {nz(R["acf1_M1"])}, lag-12 {nz(R["acf12_M1"])}, Durbin–Watson '
    f'{num(M["M1"]["dw"])}). Model 3 reduces the lag-1 value to {nz(R["acf1_M3"])} but retains a '
    f'seasonal component of {nz(R["acf12_M3"])} at lag 12; Model 4 reduces the lag-12 value to '
    f'{nz(R["acf12_M4"])}. Seasonal dependence therefore persists in every specification, which is '
    'why HAC standard errors are used throughout and why no claim here rests on ordinary '
    'inference.')
para(
    'Breusch–Pagan statistics depend on which regressors enter the auxiliary variance regression, '
    'so both variants are reported rather than one. For Model 1, regressing squared residuals on '
    f'CDD gives LM = {num(B["M1, aux on CDD"]["lm"])} on 1 degree of freedom, '
    f'{p(B["M1, aux on CDD"]["p"], 2)}. For Model 3, regressing squared residuals on CDD and HDD '
    f'gives LM = {num(B["M3, aux on CDD+HDD"]["lm"])} on 2 degrees of freedom, '
    f'{p(B["M3, aux on CDD+HDD"]["p"])}, while including the trend as well gives LM = '
    f'{num(B["M3, aux on CDD+HDD+trend"]["lm"])} on 3 degrees of freedom, '
    f'{p(B["M3, aux on CDD+HDD+trend"]["p"])}. The variant including all three regressors is the '
    'one that matches the fitted model and is the more appropriate of the two. A nonsignificant '
    'result would not establish constant variance in any case, and misspecification of the '
    'conditional mean and non-constant variance can coexist. These chi-square references assume '
    'independent errors and are therefore not dependence-robust; they are reported as an '
    'indication rather than a decisive test, and the HAC estimator used throughout is robust to '
    'both problems.')
figure(12, 'Monthly Residential Electricity Sales, January 1990 to April 2026',
       f'{FIG}12_timeseries.png',
       'The curve is a locally weighted smoothing trend shown for description only. Two peaks '
       'appear each year, in winter and in summer, against long-run growth in the level of sales.',
       width=6.4)

h1('Discussion')
para(
    'A cooling-only degree-day model describes residential electricity demand in North Carolina '
    'poorly, and the reason is that it omits one arm of a two-armed relationship rather than that '
    'the cooling relationship is weak. Adding heating degree days raised explained variance from '
    f'{nz(M["M1"]["r2"])} to {nz(M["M2"]["r2"])}; adding a linear trend raised it further to '
    f'{nz(M["M3"]["r2"])}. The two additions contribute comparable increments, and the second is '
    'attributable to the time trend rather than to weather. The cooling coefficient also moves '
    f'substantially: the Model 3 estimate lies {R["pct_increase_m1_to_m3"]:.0f}% above the Model 1 '
    f'estimate, which is the same gap as saying the Model 1 estimate lies '
    f'{R["pct_m1_below_m3"]:.0f}% below it. In a state where a large share of households heat with '
    'electricity, the heating term is not a scope limitation that leaves the cooling coefficient '
    'intact.')
para(
    'The comparison of model-implied components is the result most sensitive to specification. '
    'Under a linear trend the heating component exceeds the cooling component by about '
    f'{abs(CP["M3"]["ratio"]-1)*100:.0f}%; once calendar-month effects absorb what is common to a '
    f'given month across years, the gap widens to about {abs(CP["M4"]["ratio"]-1)*100:.0f}%. Both '
    'specifications are defensible and they identify the coefficients from different variation, so '
    'the summary is an ordering together with a range across the specifications examined, not a '
    'point estimate and not a bound. What survives is that weather-driven heating and cooling are '
    'of comparable magnitude in this state, each accounting for roughly a sixth to a quarter of '
    'annual residential sales depending on specification, with heating the larger of the two.')
para(
    'The slope ratio should not be read thermodynamically. An air conditioner and a heat pump both '
    'move heat through a vapour-compression cycle and both deliver more thermal energy than the '
    'electrical energy they consume, so no contrast between a purely electric load and a heat pump '
    'explains why a cooling degree day is associated with more electricity than a heating degree '
    'day. A compositional explanation is plausible in principle, because a heating degree day '
    'reaches the electric load most strongly in homes heated by electricity, while nearly all '
    'homes in the South cool with electricity (EIA, 2022). It is not confined to them: homes '
    'heated by combustion still draw electricity for blowers, pumps, and controls. The '
    'explanation cannot be quantified from the sources used here. The 2020 Residential Energy Consumption Survey reports main heating '
    f'equipment, not main heating fuel: {HT["nc_central_heat_pump_pct"]}% of North Carolina '
    f'housing units use a central heat pump and {HT["nc_furnace_pct"]}% use a furnace, but the '
    'survey table does not break furnaces down by fuel, and homes using electric resistance '
    'heating fall into an equipment category the table does not show separately (EIA, 2023a). The '
    'share of North Carolina homes heating with electricity is therefore larger than the '
    'heat-pump share by an amount these data do not determine, and homes heated by combustion '
    'still draw electricity for blowers and controls. No numerical account of the slope ratio is '
    'offered. Other unquantified contributors point the same way: the 65 °F base may not match the '
    'effective balance point for either mode, latent cooling loads in a humid climate are not '
    'captured by dry-bulb degree days, and heat pumps lose efficiency and engage resistance backup '
    'at low outdoor temperatures. This study estimates an aggregate association and identifies '
    'none of these mechanisms.')
para(
    'For context on where the state sits, the same survey puts North Carolina’s central heat-pump '
    f'share ({HT["nc_central_heat_pump_pct"]}%) below South Carolina ({HT["sc"]}%) and Alabama '
    f'({HT["al"]}%) and above Tennessee ({HT["tn"]}%) and Florida ({HT["fl"]}%), among the higher '
    'shares nationally. Differences between states of this size may not be statistically '
    'significant in the survey, and the figures describe equipment rather than fuel.')
para(
    'The seasonal results support a two-peaked description of the annual cycle without supporting '
    'stronger claims. July and January mean monthly sales are statistically equivalent within an '
    'exploratory margin of ±0.4 standard deviations, and winter and summer seasonal means are not '
    'distinguishable. These are statements about mean monthly energy for particular months. They '
    'do not concern seasonal maxima, hourly peak demand, or generating capacity, and nothing in '
    'this design ranks the two seasons on those quantities: two months with comparable '
    'megawatt-hours can impose very different maximum megawatt demands. Statewide residential '
    'sales also do not measure the whole-system demand of any particular utility across both '
    'Carolinas.')
para(
    'Three distinct claims should be separated in reading the stability results. First, '
    'per-customer cooling sensitivity declined over January 2008 to April 2026; this held in both '
    'pooled specifications, at every maximum lag examined, and in every estimation window tried. '
    'Second, per-customer heating sensitivity also declined; the point estimate is negative in '
    'both models, significantly so once calendar-month effects are included. Third, whether the '
    'cooling decline was proportionally larger than the heating decline is not settled: the '
    'contrast is significant with calendar-month effects and not without them, and the choice '
    'between those specifications is a modelling judgement rather than something the data resolve. '
    'The paper therefore reports a general decline in per-customer weather sensitivity as '
    'supported and the asymmetry between the two arms as specification-dependent.')
para(
    'A fourth claim, an explanation for any of these declines, is not attempted. Several '
    'mechanisms could produce them: turnover of heating and cooling equipment under tightening '
    'federal minimum efficiency standards, which rose for central air conditioners in 2006, again '
    'for southern states in 2015, and again under the SEER2 test procedure in 2023 '
    '(Air-Conditioning, Heating, and Refrigeration Institute, 2023); improvements to building '
    'shells; changes in household size, dwelling size, or occupancy; behavioural response to '
    'rising prices; and compositional change in the customer base as the state grows. This design '
    'measures none of them. A South-wide air conditioning prevalence statistic does not establish '
    'North Carolina’s own adoption history, which would be needed to argue that saturation rather '
    'than efficiency explains the pattern. Average revenue per kilowatt-hour, the only price-like '
    'variable available here, is total revenue divided by total sales, so it mixes rate changes '
    'with shifts in the composition of consumption and is mechanically related to the outcome; '
    'adding it does not remove price-related confounding.')
para(
    'A declining per-customer coefficient also does not mean falling electricity use. The '
    'coefficient describes response per degree day for the average customer, while the customer '
    f'base grew from {cm(R["cust_first"])} in January 2008 to {cm(R["cust_last"])} in April 2026. '
    'Total weather-driven consumption can rise while per-customer sensitivity falls.')

h1('Conclusion')
para(
    'Cooling degree days are positively associated with monthly residential electricity sales in '
    'North Carolina, but a model built on them alone answers a narrower question than it appears '
    'to. Adding heating degree days raises explained variance from '
    f'{nz(M["M1"]["r2"])} to {nz(M["M2"]["r2"])}, and adding a linear time trend raises it to '
    f'{nz(M["M3"]["r2"])}; the second increment reflects long-run growth rather than weather, and '
    'the cooling coefficient changes substantially across the two steps. The model-implied heating '
    'and cooling components of annual sales are of comparable magnitude, with heating the larger '
    'in every specification examined, though the size of the gap ranges from about '
    f'{abs(CP["M3"]["ratio"]-1)*100:.0f}% to about {abs(CP["M4"]["ratio"]-1)*100:.0f}% depending '
    'on how calendar-month variation is handled. July and January mean monthly sales are '
    'statistically equivalent within an exploratory margin. Per-customer sensitivity to degree '
    'days declined between January 2008 and April 2026, clearly for cooling and less certainly for '
    'heating, and whether the cooling decline was proportionally the larger of the two depends on '
    'the specification. All of these are associations estimated in sample from statewide monthly '
    'energy totals. They are not forecasts, and they do not speak to peak power or capacity '
    'requirements.')
h2('Limitations')
para(
    'The design is observational and uses statewide aggregates, so county-level variation in '
    'climate, housing stock, and rates is invisible and no causal effect is identified. nClimDiv '
    'statewide degree days are area-weighted rather than population-weighted, so the predictor '
    'differs from the demand-relevant exposure. This is a form of measurement error, but its '
    'direction is not established here: the discrepancy is systematic rather than classical, no '
    'error model has been fitted, and it should not be assumed to attenuate the slopes.')
para(
    'Residual seasonal dependence persists in every specification. HAC standard errors address '
    'inference under that dependence; they do not repair a misspecified conditional mean, and no '
    'dynamic model of the residual structure was estimated. The linear trend in Model 3 is a crude '
    'proxy for customer growth, income, prices, appliance efficiency, and building stock, none of '
    'which is separately identified. The per-customer analyses cover January 2008 onward and '
    'cannot say how the arms behaved before then; the 2007 observations were excluded because the '
    'sales-per-customer ratio is discontinuous at January 2008, and the cause of that '
    'discontinuity is suspected rather than documented. The 2021–22 months whose customer counts '
    'move by more than 2% are retained and do not materially affect the results, but they are '
    'unexplained.')
para(
    'EIA-861M reports recent months as preliminary and revises them; the final months of this '
    'extract could not be compared against a later vintage, though dropping the last three months '
    f'leaves the Model 3 component ratio at {num(R["sens"]["drop_last3"]["ratio"])}. The '
    'identification of state code 031 as North Carolina follows from the file layout and the '
    'internal consistency of the three element codes, and was not confirmed against an '
    'independently retrieved NCEI state-code table. Seasonal means use all available months, so '
    'Winter and Spring each draw on one more year than Summer and Fall; restricting to complete '
    'calendar years shifts the Winter mean by '
    f'{R["season_mean_complete_Winter"] - R["season"]["Winter"]["mean"]:+,.0f} MWh and leaves the '
    'between-season variance share at '
    f'{nz(R["eta2_complete"])} against {nz(R["eta2"])}.')
para(
    'Every coefficient of determination reported here is an in-sample fit to the months used for '
    'estimation. The paper makes no forecasting claim. Establishing forecasting accuracy would '
    'require chronological validation on held-out later months, ideally with rolling-origin '
    'evaluation, comparison against a seasonal-naïve baseline and a calendar-and-trend model '
    'carrying no weather information, and a distinction between predictions built on observed '
    'degree days and forecasts built on forecast degree days.')
h2('Future Research')
para(
    'Four extensions follow directly. A regression with seasonal autoregressive errors would model '
    'the residual dependence rather than correcting inference after the fact, and would test '
    'whether the component estimates are sensitive to that structure. County-level or '
    'balancing-authority data would recover spatial variation and permit population-weighted '
    'degree days. Hourly or daily load data would allow the peak-power questions this monthly '
    'design cannot address. Repeating the stability analysis across southern states with differing '
    'electric-heating shares and equipment histories, using heating-fuel rather than '
    'heating-equipment data, would help distinguish the mechanisms this study can only list.')

h2('Data and Code Availability')
para(
    'All data are public. Degree days and mean temperature come from the NOAA nClimDiv statewide '
    'files climdiv-cddcst, climdiv-hddcst, and climdiv-tmpcst, version 1.0.0 dated June 4, 2026, '
    'downloaded June 2026 and filtered to state code 031, with −9999 recoded as missing. '
    'Electricity sales, customer counts, and average revenue per kilowatt-hour come from EIA Form '
    'EIA-861M extracts for January 1990 through December 2009 and January 2010 onward, downloaded '
    'June 2026 and filtered to North Carolina, residential sector.')
para(
    f'The merge is a one-to-one inner join on year and month yielding {int(R["N"])} consecutive '
    'months with no duplicate keys, no interior gaps, and no negative degree-day values. Customer '
    f'counts are present for {int(R["n_pc_all"])} months from January 2007, of which the '
    f'{int(R["n_pc"])} months from January 2008 are used. Annual quantities use the '
    f'{int(R["n_complete_years"])} complete calendar years.')
para(
    f'The analyses reported here were executed in Python {R["software"]["python"]} with NumPy '
    f'{R["software"]["numpy"]} and pandas {R["software"]["pandas"]}. SciPy and statsmodels were '
    'not available in the analysis environment, so tail probabilities for the t, F, and '
    'chi-square distributions come from routines written for this project; those routines are '
    'checked against published critical values by an accompanying validation script, which passes '
    'forty comparisons. An R implementation of the same workflow accompanies the manuscript but '
    'has not been executed and is offered as a convenience rather than as a replication. The '
    'supplementary materials comprise the analysis scripts, the validation script, the '
    'analysis-ready monthly panel, the annual-slope table, a machine-readable results file, '
    'execution logs, and a verification report.')
pagebreak()
h1('References')
refs = [
 'Air-Conditioning, Heating, and Refrigeration Institute. (2023). <i>2023 energy efficiency '
 'standards.</i> https://www.ahrinet.org/2023-energy-efficiency-standards',
 'Cawthorne, D., de Queiroz, A. R., Eshraghi, H., Sankarasubramanian, A., & DeCarolis, J. F. '
 '(2021). The role of temperature variability on seasonal electricity demand in the Southern US. '
 '<i>Frontiers in Sustainable Cities, 3</i>, Article 644789. '
 'https://doi.org/10.3389/frsc.2021.644789',
 'Colelli, F. P., Wing, I. S., & De Cian, E. (2023). Air-conditioning adoption and electricity '
 'demand highlight climate change mitigation–adaptation tradeoffs. <i>Scientific Reports, 13</i>(1), '
 'Article 4413. https://doi.org/10.1038/s41598-023-31469-z',
 'Duke Energy. (2025, October 1). <i>Duke Energy files 2025 Carolinas Resource Plan, continues '
 'modernizing energy infrastructure to support future growth</i> [Press release]. '
 'https://news.duke-energy.com/releases/duke-energy-files-2025-carolinas-resource-plan-continues-'
 'modernizing-energy-infrastructure-to-support-future-growth',
 'Fache, A., & Bhat, M. G. (2024). Temperature sensitive electricity demand and policy implications '
 'for energy transition: A case study of Florida, USA. <i>Frontiers in Sustainable Energy Policy, '
 '2</i>, Article 1271035. https://doi.org/10.3389/fsuep.2023.1271035',
 'Granger, C. W. J., & Newbold, P. (1974). Spurious regressions in econometrics. <i>Journal of '
 'Econometrics, 2</i>(2), 111–120. https://doi.org/10.1016/0304-4076(74)90034-7',
 'Hu, W., Scholz, Y., Yeligeti, M., Deng, Y., & Jochem, P. (2024). Future electricity demand for '
 'Europe: Unraveling the dynamics of the Temperature Response Function. <i>Applied Energy, 368</i>, '
 'Article 123387. https://doi.org/10.1016/j.apenergy.2024.123387',
 'Kunkel, K. E., Easterling, D. R., Ballinger, A., Bililign, S., Champion, S. M., Corbett, D. R., '
 'Dello, K. D., Dissen, J., Lackmann, G. M., Luettich, R. A., Jr., Perry, L. B., Robinson, W. A., '
 'Stevens, L. E., Stewart, B. C., & Terando, A. J. (2020). <i>North Carolina climate science '
 'report.</i> North Carolina Institute for Climate Studies. https://ncics.org/nccsr',
 'Lakens, D. (2017). Equivalence tests: A practical primer for t tests, correlations, and '
 'meta-analyses. <i>Social Psychological and Personality Science, 8</i>(4), 355–362. '
 'https://doi.org/10.1177/1948550617697177',
 'Li, M., Allinson, D., & He, M. (2018). Seasonal variation in household electricity demand: A '
 'comparison of monitored and synthetic daily load profiles. <i>Energy and Buildings, 179</i>, '
 '292–300. https://doi.org/10.1016/j.enbuild.2018.09.030',
 'National Oceanic and Atmospheric Administration. (2026). <i>nClimDiv statewide cooling degree '
 'days, heating degree days, and average temperature</i> (Version 1.0.0, 2026-06-04) [Data set]. '
 'National Centers for Environmental Information. https://www.ncei.noaa.gov/pub/data/cirs/climdiv/',
 'Newey, W. K., & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and '
 'autocorrelation consistent covariance matrix. <i>Econometrica, 55</i>(3), 703–708. '
 'https://doi.org/10.2307/1913610',
 'U.S. Energy Information Administration. (2018, July 23). Air conditioning accounts for about 12% '
 'of U.S. home energy expenditures. <i>Today in Energy.</i> '
 'https://www.eia.gov/todayinenergy/detail.php?id=36692',
 'U.S. Energy Information Administration. (2022, May 31). Nearly 90% of U.S. households used air '
 'conditioning in 2020. <i>Today in Energy.</i> https://www.eia.gov/todayinenergy/detail.php?id=52558',
 'U.S. Energy Information Administration. (2023a). <i>Highlights for space heating in U.S. homes by '
 'state, 2020</i> [Data tables]. Residential Energy Consumption Survey. '
 'https://www.eia.gov/consumption/residential/data/2020/state/pdf/State%20Space%20Heating.pdf',
 'U.S. Energy Information Administration. (2023b). <i>Units and calculators explained: Degree '
 'days.</i> https://www.eia.gov/energyexplained/units-and-calculators/degree-days.php',
 'U.S. Energy Information Administration. (2024, March 15). <i>How much electricity is used for air '
 'conditioning in the United States?</i> Frequently Asked Questions. '
 'https://www.eia.gov/tools/faqs/faq.php?id=1174&t=1',
 'U.S. Energy Information Administration. (2026). <i>Form EIA-861M: Monthly electric power industry '
 'report</i> [Data set]. https://www.eia.gov/electricity/data/eia861m/',
]
for ref in refs:
    q = doc.add_paragraph()
    q.paragraph_format.line_spacing = 2.0
    q.paragraph_format.left_indent = Inches(0.5)
    q.paragraph_format.first_line_indent = Inches(-0.5)
    q.paragraph_format.space_after = Pt(0)
    for chunk in re.split(r'(<i>.*?</i>)', ref):
        if not chunk: continue
        if chunk.startswith('<i>'): q.add_run(chunk[3:-4]).italic = True
        else: q.add_run(chunk)

pagebreak()
h1('Appendix')
para('Residual Diagnostics', bold=True, indent=False)
para(
    'This appendix presents residual diagnostics for the cooling-only baseline (Model 1) and for '
    'the two specifications that carry the substantive results (Models 3 and 4), together with a '
    'normality check for the paired comparison.')
for n, key, path, extra in [
        ('A1', 'Model 1 (Cooling Degree Days Only)', f'{FIG}A1_diag_m1.png',
         f'The lag-1 residual autocorrelation is {nz(R["acf1_M1"])} and the seasonal value at lag 12 '
         f'is {nz(R["acf12_M1"])}. The dense column in Panel A contains the zero-CDD months, which the '
         'model maps to a single fitted value.'),
        ('A2', 'Model 3 (Cooling and Heating Degree Days With a Linear Trend)', f'{FIG}A2_diag_m3.png',
         f'The lag-1 value falls to {nz(R["acf1_M3"])} and Durbin–Watson rises to '
         f'{num(M["M3"]["dw"])}, but a seasonal component of {nz(R["acf12_M3"])} remains at lag 12.'),
        ('A3', 'Model 4 (Model 3 Plus Calendar-Month Fixed Effects)', f'{FIG}A3_diag_m4.png',
         f'Calendar-month effects reduce the lag-12 value to {nz(R["acf12_M4"])}. Residual '
         'dependence is reduced but not eliminated in any specification.')]:
    figure(n, f'Residual Diagnostics for {key}', path,
           'Panel A plots residuals against fitted values; Panel B the residual distribution with a '
           'matched normal curve; Panel C the normal quantile–quantile plot; Panel D the residual '
           'autocorrelation function with 95% bounds for white noise. ' + extra, width=6.2)
figure('A4', 'Normal Q–Q Plot of the July–January Paired Differences', f'{FIG}A4_paired_qq.png',
       'The line marks agreement with a normal distribution, fitted through the first and third '
       'quartiles. No marked departure is evident, supporting the normality assumption of the '
       'paired t test and the equivalence tests. This plot assesses the distribution of the '
       'differences, not their independence, which is addressed in the text.', width=4.3)

doc.save(OUT)
print('saved:', OUT, os.path.getsize(OUT), 'bytes')
