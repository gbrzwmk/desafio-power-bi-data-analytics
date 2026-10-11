"""Desafio 6 — parte de um projeto PBIP exportado do sales_report.pbix e:
 - adiciona medidas DAX ao modelo (financials.tmdl)
 - cria a página 'Detalhes' (TOP3 produtos, países, dispersão, agrupamentos, compartimentação, ranking)
 - cria menus de navegação com estados (padrão / focalizar / pressionar) nas três páginas
Uso: python3 build6.py <pbip_orig> <pbip_out>"""
import json, os, sys, shutil, random, re

_rng = random.Random(6)
hex10 = lambda: "%020x" % _rng.getrandbits(80)
src, out = sys.argv[1], sys.argv[2]
if os.path.exists(out):
    shutil.rmtree(out)
shutil.copytree(src, out, ignore=shutil.ignore_patterns(".pbi"))
J = lambda o: json.dumps(o, ensure_ascii=False, indent=2)
rep = os.path.join(out, "sales_report.Report", "definition")
sm = os.path.join(out, "sales_report.SemanticModel", "definition")

HOME, PRINCIPAL, DETALHES = "ReportSection3ee2a4126027e0713e1d", "ReportSection", "ReportSection5e4ef9ee0e160b92ecde"
PAGES = [(HOME, "Home"), (PRINCIPAL, "Principal"), (DETALHES, "Detalhes")]

# ------------------------------------------------------------------ 1. medidas DAX
MEASURES = [
    ("Total Profit", "SUM(financials[Profit])", "#,0.00"),
    ("Total Discounts", "SUM(financials[Discounts])", "#,0.00"),
    ("Margem de Lucro", "DIVIDE([Total Profit], [total sales])", "0.0%"),
    ("Ticket Médio", "DIVIDE([total sales], COUNTROWS(financials))", "#,0.00"),
    ("Qtd Países", "DISTINCTCOUNT(financials[Country])", "0"),
    ("Ranking Produto", "RANKX(ALL(financials[Product]), [total sales])", "0"),
    ("Vendas TOP3 (%)", "DIVIDE(CALCULATE([total sales], TOPN(3, ALL(financials[Product]), [total sales])), CALCULATE([total sales], ALL(financials[Product])))", "0.0%"),
    ("Unidades Médias por Mês", "AVERAGEX(VALUES(financials[Month Name]), [total de vendidos])", "#,0"),
]
tmdl_path = os.path.join(sm, "tables", "financials.tmdl")
tmdl = open(tmdl_path, encoding="utf-8").read()
block = ""
for name, expr, fmt in MEASURES:
    block += f"\tmeasure '{name}' = {expr}\n\t\tformatString: {fmt}\n\t\tlineageTag: {hex10()[:8]}-{hex10()[:4]}-4{hex10()[:3]}-a{hex10()[:3]}-{hex10()[:12]}\n\n"
tmdl = tmdl.replace("\tcolumn Segment\n", block + "\tcolumn Segment\n", 1)
open(tmdl_path, "w", encoding="utf-8", newline="\n").write(tmdl)

# ------------------------------------------------------------------ helpers PBIR
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"
lit = lambda v: {"expr": {"Literal": {"Value": v}}}
hexc = lambda h: {"solid": {"color": lit(f"'{h}'")}}
theme = lambda cid, pct=0: {"solid": {"color": {"expr": {"ThemeDataColor": {"ColorId": cid, "Percent": pct}}}}}
WHITE = theme(0, 0)
F = "financials"

def col(prop, entity=F):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
def agg(prop, fn=0):
    return {"Aggregation": {"Expression": col(prop), "Function": fn}}
def mea(prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": F}}, "Property": prop}}

def field(f):
    prop, kind, disp = f
    if kind == "M":
        p = {"field": mea(prop), "queryRef": f"{F}.{prop}", "active": True}
    elif kind == "Sum":
        p = {"field": agg(prop, 0), "queryRef": f"Sum({F}.{prop})", "active": True}
    elif kind == "Count":
        p = {"field": agg(prop, 2), "queryRef": f"Count({F}.{prop})", "active": True}
    else:
        p = {"field": col(prop), "queryRef": f"{F}.{prop}", "active": True}
    if disp:
        p["displayName"] = disp
    return p

def container(x, y, w, h, z, visual, name=None, extra=None):
    j = {"$schema": VC_SCHEMA, "name": name or hex10(),
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}, "visual": visual}
    if extra:
        j.update(extra)
    return j

def title(text, size=14):
    return {"title": [{"properties": {"show": lit("true"), "text": lit("'" + text + "'"), "fontSize": lit(f"{size}D"),
                                      "fontColor": WHITE, "fontFamily": lit("'Segoe UI Semibold'")}}],
            "background": [{"properties": {"show": lit("false")}}],
            "border": [{"properties": {"show": lit("false")}}]}

NO_BG = {"background": [{"properties": {"show": lit("false")}}], "border": [{"properties": {"show": lit("false")}}]}

def visual(vt, roles, objects=None, ttl=None, sort=None):
    qs = {role: {"projections": [field(f) for f in fields]} for role, fields in roles.items()}
    v = {"visualType": vt, "query": {"queryState": qs}, "drillFilterOtherVisuals": True}
    if sort:
        f, direction = sort
        v["query"]["sortDefinition"] = {"sort": [{"field": field(f)["field"], "direction": direction}], "isDefaultSort": True}
    if objects:
        v["objects"] = objects
    v["visualContainerObjects"] = ttl if ttl else NO_BG
    return v

AXIS_WHITE = {"categoryAxis": [{"properties": {"labelColor": WHITE, "titleColor": WHITE, "showAxisTitle": lit("false"), "fontSize": lit("10D")}}],
              "valueAxis": [{"properties": {"labelColor": WHITE, "titleColor": WHITE, "showAxisTitle": lit("false"), "gridlineColor": hexc("#8E5BBF"), "fontSize": lit("9D")}}],
              "legend": [{"properties": {"labelColor": WHITE, "fontSize": lit("10D"), "position": lit("'Top'"), "showTitle": lit("false")}}],
              "labels": [{"properties": {"show": lit("true"), "color": WHITE, "fontSize": lit("9D")}}]}

def bars(category, values, ttl_text, colors, vt="clusteredBarChart", sort=None, legend=None):
    roles = {"Category": [category], "Y": values}
    if legend:
        roles["Series"] = [legend]
    objs = dict(AXIS_WHITE)
    objs["dataPoint"] = [{"properties": {"fill": hexc(colors[0])}}] + [
        {"properties": {"fill": hexc(c)}, "selector": {"metadata": field(v)["queryRef"]}} for v, c in zip(values, colors)]
    return visual(vt, roles, objects=objs, ttl=title(ttl_text), sort=sort or (values[0], "Descending"))

def card(f, label, color="#FFFFFF"):
    return visual("card", {"Values": [(f[0], f[1], label)]},
                  objects={"labels": [{"properties": {"fontSize": lit("26D"), "color": hexc(color)}}],
                           "categoryLabels": [{"properties": {"fontSize": lit("11D"), "color": WHITE}}]})

def shape(x, y, w, h, z, pct=0.4, transp=36):
    return container(x, y, w, h, z, {
        "visualType": "shape",
        "objects": {"shape": [{"properties": {"tileShape": lit("'rectangle'"), "roundEdge": lit("15L")}}],
                    "rotation": [{"properties": {"shapeAngle": lit("0L")}}],
                    "fill": [{"properties": {"fillColor": theme(5, pct), "transparency": lit(f"{transp}D")}, "selector": {"id": "default"}}],
                    "outline": [{"properties": {"show": lit("false")}}],
                    "shadow": [{"properties": {"show": lit("false")}}]},
        "drillFilterOtherVisuals": True})

def textbox(x, y, w, h, z, runs):
    return container(x, y, w, h, z, {
        "visualType": "textbox",
        "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": v, "textStyle": st} for v, st in runs]}]}}]},
        "visualContainerObjects": {"background": [{"properties": {"show": lit("false")}}]},
        "drillFilterOtherVisuals": True})

def image(x, y, w, h, z, item, name=None):
    return container(x, y, w, h, z, {
        "visualType": "image",
        "objects": {"general": [{"properties": {"imageUrl": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": item}}}}}]},
        "visualContainerObjects": {"title": [{"properties": {"text": lit("'fundo_purple'")}}]},
        "drillFilterOtherVisuals": True}, name=name)

# ------------------------------------------------------------------ botões de navegação com estados
NAV = {"default": {"fill": "#3B1660", "text": "#FFFFFF", "line": "#B98BE0", "weight": 1, "transp": 15},
       "hover":   {"fill": "#C13C8C", "text": "#FFFFFF", "line": "#FFFFFF", "weight": 2, "transp": 0},
       "selected": {"fill": "#FF4FA3", "text": "#2A0A45", "line": "#FFFFFF", "weight": 2, "transp": 0},
       "current": {"fill": "#E044A7", "text": "#FFFFFF", "line": "#FFFFFF", "weight": 2, "transp": 0}}

def nav_button(x, y, w, h, z, text, target, current=False, size=10):
    st = dict(NAV)
    dflt = NAV["current"] if current else NAV["default"]
    def fill(s):
        return {"properties": {"fillColor": hexc(s["fill"]), "transparency": lit(f"{s['transp']}D")}}
    def txt(s, bold):
        return {"properties": {"text": lit("'" + text + "'"), "fontColor": hexc(s["text"]), "fontSize": lit(f"{size}D"),
                               "fontFamily": lit("'Segoe UI Semibold'" if bold else "'Segoe UI'"), "alignment": lit("'center'")}}
    def outline(s):
        return {"properties": {"lineColor": hexc(s["line"]), "weight": lit(f"{s['weight']}D")}}
    v = {"visualType": "actionButton",
         "objects": {
             "icon": [{"properties": {"shapeType": lit("'blank'")}, "selector": {"id": "default"}}],
             "text": [{"properties": {"show": lit("true")}},
                      dict(txt(dflt, current), selector={"id": "default"}),
                      dict(txt(st["hover"], True), selector={"id": "hover"}),
                      dict(txt(st["selected"], True), selector={"id": "selected"})],
             "fill": [{"properties": {"show": lit("true")}},
                      dict(fill(dflt), selector={"id": "default"}),
                      dict(fill(st["hover"]), selector={"id": "hover"}),
                      dict(fill(st["selected"]), selector={"id": "selected"})],
             "outline": [{"properties": {"show": lit("true")}},
                         dict(outline(dflt), selector={"id": "default"}),
                         dict(outline(st["hover"]), selector={"id": "hover"}),
                         dict(outline(st["selected"]), selector={"id": "selected"})],
             "shape": [{"properties": {"roundEdge": lit("10L")}, "selector": {"id": "default"}}]},
         "visualContainerObjects": {
             "visualLink": [{"properties": {"show": lit("true"), "type": lit("'PageNavigation'"), "navigationSection": lit("'" + target + "'")}}],
             "title": [{"properties": {"text": lit("'Menu - " + text + "'")}}],
             "visualTooltip": [{"properties": {"show": lit("true"), "type": lit("'Default'")}}]},
         "drillFilterOtherVisuals": True}
    return container(x, y, w, h, z, v)

def rail(page_id, x=14, y=160, w=72, h=40, gap=10, z0=20000):
    """menu vertical: Home / Principal / Detalhes; o botão da página atual fica destacado"""
    out = []
    for i, (pid, label) in enumerate(PAGES):
        out.append(nav_button(x, y + i * (h + gap), w, h, z0 + i * 10, label, pid, current=(pid == page_id)))
    return out

def write_visual(page_id, vc):
    d = os.path.join(rep, "pages", page_id, "visuals", vc["name"])
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "visual.json"), "w", encoding="utf-8", newline="\n").write(J(vc))

# ------------------------------------------------------------------ 2. página Home: menu horizontal sob o botão principal
for i, (pid, label) in enumerate(PAGES[1:]):
    write_visual(HOME, nav_button(88 + i * 150, 662, 138, 40, 20000 + i * 10, label, pid, size=11))

# ------------------------------------------------------------------ 3. página Principal: remove a seta 'Next' e adiciona o menu lateral
# a antiga seta 'Next' (08267e95...) vira o primeiro botão do menu (mesmo nome, para não deixar visual órfão)
for i, vc in enumerate(rail(PRINCIPAL)):
    if i == 0:
        vc["name"] = "08267e9539ad8f50f5c5"
    write_visual(PRINCIPAL, vc)

# ------------------------------------------------------------------ 4. página Detalhes
os.makedirs(os.path.join(rep, "pages", DETALHES, "visuals"))
page_json = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
             "name": DETALHES, "displayName": "Detalhes", "displayOption": "FitToPage", "height": 720, "width": 1280}
open(os.path.join(rep, "pages", DETALHES, "page.json"), "w", encoding="utf-8", newline="\n").write(J(page_json))
V = []
V.append(image(0, 0, 1280, 720, 0, "fundo11252593036709269.png"))
V += rail(DETALHES)
V.append(textbox(100, 14, 700, 60, 100, [("Detalhes de vendas", {"fontWeight": "bold", "fontSize": "24pt", "color": "#FFFFFF"})]))
V.append(textbox(100, 62, 830, 36, 101, [("TOP 3 produtos, principais países, dispersão mensal, agrupamentos (Continentes e Segmentos) e compartimentação (faixas de unidades)", {"fontSize": "10pt", "color": "#E8D9F5"})]))
# segmentador de ano (horizontal)
V.append(shape(940, 18, 325, 78, 150, pct=0.4, transp=36))
V.append(container(948, 20, 310, 74, 200, visual(
    "slicer", {"Values": [("Semestres", None, "Semestre (agrupamento)")]},
    objects={"data": [{"properties": {"mode": lit("'Basic'")}}],
             "general": [{"properties": {"orientation": lit("1D")}}],
             "header": [{"properties": {"fontColor": WHITE, "textSize": lit("10D")}}],
             "items": [{"properties": {"fontColor": WHITE, "background": hexc("#4A1F78")}}]})))
# cartões
CARDS = [("Total Profit", "M", "Lucro total", "#F2C14E"), ("Margem de Lucro", "M", "Margem de lucro", "#8BD3FF"),
         ("Ticket Médio", "M", "Ticket médio por venda", "#FFFFFF"), ("Total Discounts", "M", "Total de descontos", "#FF7AB6")]
V.append(shape(100, 100, 1165, 96, 300, pct=0.4, transp=36))
for i, (m, k, lab, color) in enumerate(CARDS):
    V.append(container(112 + i * 290, 104, 270, 88, 400 + i, card((m, k), lab, color)))
# linha 2
V.append(shape(100, 212, 380, 232, 1000))
V.append(container(108, 216, 364, 224, 1100, bars(("Product", None, "Produto"), [("TOP3 PRODUCT", "M", "Vendas")], "TOP 3 produtos em vendas", ["#F2C14E"])))
V.append(shape(492, 212, 390, 232, 1200))
V.append(container(500, 216, 374, 224, 1300, bars(("Country", None, "País"), [("total sales", "M", "Vendas"), ("Total Profit", "M", "Lucro")],
                                                   "Principais países: vendas e lucro", ["#8BD3FF", "#FF7AB6"])))
V.append(shape(894, 212, 371, 232, 1400))
donut = visual("donutChart", {"Category": [("Continentes", None, "Continente")], "Y": [("Total Profit", "M", "Lucro")]},
               objects={"legend": [{"properties": {"labelColor": WHITE, "position": lit("'BottomCenter'"), "showTitle": lit("false"), "fontSize": lit("10D")}}],
                        "labels": [{"properties": {"show": lit("true"), "color": WHITE, "labelStyle": lit("'Percent of total'"), "fontSize": lit("9D")}}],
                        "dataPoint": [{"properties": {"fill": hexc("#F2C14E")}, "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col("Continentes"), "Right": {"Literal": {"Value": "'America do Norte'"}}}}}]}},
                                      {"properties": {"fill": hexc("#8BD3FF")}, "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col("Continentes"), "Right": {"Literal": {"Value": "'Europa'"}}}}}]}},
                                      {"properties": {"fill": hexc("#FF7AB6")}, "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col("Continentes"), "Right": {"Literal": {"Value": "'Outro'"}}}}}]}}]},
               ttl=title("Lucro por continente (agrupamento)"))
V.append(container(902, 216, 355, 224, 1500, donut))
# linha 3
V.append(shape(100, 458, 500, 250, 2000))
scatter = visual("scatterChart", {"Category": [("Month Name", None, "Mês")], "Series": [("Semestres", None, "Semestre")],
                                  "X": [("Units Sold", "Sum", "Unidades vendidas")], "Y": [("total sales", "M", "Vendas")], "Size": [("Total Profit", "M", "Lucro")]},
                 objects={"categoryAxis": [{"properties": {"labelColor": WHITE, "titleColor": WHITE, "showAxisTitle": lit("true"), "fontSize": lit("9D")}}],
                          "valueAxis": [{"properties": {"labelColor": WHITE, "titleColor": WHITE, "showAxisTitle": lit("true"), "gridlineColor": hexc("#8E5BBF"), "fontSize": lit("9D")}}],
                          "legend": [{"properties": {"labelColor": WHITE, "position": lit("'Top'"), "showTitle": lit("false"), "fontSize": lit("9D")}}],
                          "categoryLabels": [{"properties": {"show": lit("true"), "color": WHITE, "fontSize": lit("8D")}}],
                          "dataPoint": [{"properties": {"fill": hexc("#F2C14E")}, "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col("Semestres"), "Right": {"Literal": {"Value": "'Primeiro Semestre '"}}}}}]}},
                                        {"properties": {"fill": hexc("#8BD3FF")}, "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col("Semestres"), "Right": {"Literal": {"Value": "'Segundo Semestre'"}}}}}]}}]},
                 ttl=title("Dispersão: unidades vendidas x vendas por mês"))
V.append(container(108, 462, 484, 242, 2100, scatter))
V.append(shape(612, 458, 320, 250, 2200))
V.append(container(620, 462, 304, 242, 2300, bars(("Buckets", None, "Faixa de unidades (bin)"), [("total de vendidos", "M", "Unidades")],
                                                   "Compartimentação: unidades por faixa", ["#B5A1FF"], vt="clusteredColumnChart", sort=(("Buckets", None, None), "Ascending"))))
V.append(shape(944, 458, 321, 250, 2400))
rank = visual("tableEx", {"Values": [("Ranking Produto", "M", "#"), ("Product", None, "Produto"), ("total sales", "M", "Vendas"), ("Margem de Lucro", "M", "Margem")]},
              objects={"columnHeaders": [{"properties": {"fontColor": WHITE, "backColor": hexc("#4A1F78"), "fontSize": lit("10D")}}],
                       "values": [{"properties": {"fontColorPrimary": WHITE, "fontColorSecondary": WHITE, "backColorPrimary": hexc("#3B1660"), "backColorSecondary": hexc("#4A1F78"), "fontSize": lit("10D")}}],
                       "grid": [{"properties": {"rowPadding": lit("4D"), "gridVertical": lit("false"), "gridHorizontal": lit("false")}}],
                       "total": [{"properties": {"totals": lit("false")}}]},
              ttl=title("Ranking de produtos"), sort=(("Ranking Produto", "M", None), "Ascending"))
V.append(container(952, 462, 305, 242, 2500, rank))
for vc in V:
    write_visual(DETALHES, vc)

# ------------------------------------------------------------------ 5. pages.json
pages = json.load(open(os.path.join(rep, "pages", "pages.json"), encoding="utf-8"))
pages["pageOrder"] = [HOME, PRINCIPAL, DETALHES]
open(os.path.join(rep, "pages", "pages.json"), "w", encoding="utf-8", newline="\n").write(J(pages))
print("ok", len(V), "visuais em Detalhes")
