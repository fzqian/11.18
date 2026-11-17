# -*- coding: utf-8 -*-
"""一次性：把现成两页的「非数据部分」抽成 spec/*.json，避免手抄文案出错。

抽什么：页面头（title/desc/css）、品牌、导航、hero（眉标/大标题/四张或三张卡/meta）、
口径折叠整块（原样 HTML）、小节标题、页脚、尾部脚本。
抽完 build.py 就只吃 spec + cases，页面随时可再生成。
"""
import io
import json
import re
import sys

STAGES = {
    "connect": [
        {"no": 1, "mark": "①", "name": "自我介绍", "chip": "①", "color": "#2563EB", "bandbg": "#E8EFFF", "legend": ""},
        {"no": 2, "mark": "②", "name": "称呼客户", "chip": "②", "color": "#7C3AED", "bandbg": "#F2EBFE", "legend": ""},
        {"no": 3, "mark": "③", "name": "说明来意", "chip": "③", "color": "#0E9F6E", "bandbg": "#E6F9F1", "legend": ""},
        {"no": 4, "mark": "④", "name": "客户回应", "chip": "④", "color": "#D97706", "bandbg": "#FFF4DF", "legend": ""},
    ],
    "value": [
        {"no": 1, "mark": "①", "name": "形态", "chip": "①形态", "color": "#2563EB", "bandbg": "#E8EFFF", "legend": "我买的是什么"},
        {"no": 2, "mark": "②", "name": "出口", "chip": "②出口", "color": "#0E9F6E", "bandbg": "#E6F9F1", "legend": "买完能得到什么"},
        {"no": 3, "mark": "③", "name": "落点", "chip": "③落点", "color": "#D97706", "bandbg": "#FFF4DF", "legend": "跟我有什么关系"},
    ],
}


def cards(page, cls):
    m = re.search(r'<div class="%s">(.*?)\n    </div>' % cls, page, re.S)
    if not m:
        m = re.search(r'<div class="%s">(.*?)</div>\s*<div class="hero-meta"' % cls, page, re.S)
    out = []
    for c in re.findall(r'<div class="st s\d">(.*?)</div>', m.group(1), re.S):
        g = lambda p: (re.search(p, c, re.S).group(1).strip() if re.search(p, c, re.S) else "")
        out.append({
            "no": g(r'<span class="stn">(.*?)</span>'),
            "name": g(r"<b>(.*?)</b>"),
            "kicker": g(r'<span class="stk">(.*?)</span>'),
            "lead": g(r"<p>(.*?)</p>"),
            "note": g(r'<span class="stq">(.*?)</span>'),
        })
    return out


def lift(path, kind, cases_file, out_file):
    page = io.open(path, encoding="utf-8").read()
    spec = {
        "说明": "这一页的『散文部分』。改文案改这里；聊天记录在 cases/*.json；两者都由 kit/build.py 拼成页面。",
        "kind": kind,
        "out": "",
        "title": re.search(r"<title>(.*?)</title>", page).group(1),
        "desc": re.search(r'<meta name="description" content="(.*?)">', page).group(1),
        "css": re.findall(r'<link rel="stylesheet" href="([^"]+)">', page),
        "brand": re.search(r'<span>(体德智训 · .*?)</span>', page).group(1),
        "hero": {
            "eyebrow": re.search(r'<div class="eyebrow">(.*?)</div>', page).group(1),
            "h1": [x.strip() for x in re.findall(r"<h1>(.*?)</h1>", page, re.S)[0].split("<br>")],
            "cards": cards(page, "stage4" if kind == "connect" else "stage3"),
            "meta": re.findall(r'<div class="hero-meta">(.*?)</div>', page, re.S)[0]
            .replace("<span>", "\n").replace("</span>", "").strip().split("\n"),
        },
        "stages": STAGES[kind],
        "sec": {
            "no": re.search(r'<div class="sec-no">(.*?)</div>', page).group(1),
            "h": re.search(r"<h2>(.*?)</h2>", page).group(1),
        },
        "footer": re.search(r"<footer class=\"foot\">(.*?)</footer>", page, re.S).group(1).strip(),
        "cases": cases_file,
    }
    if kind == "connect":
        fold = re.search(r'<details class="cc-fold rv" id="ccFold">.*?</details>', page, re.S)
        spec["fold_html"] = fold.group(0) if fold else ""
    # 尾部脚本（折叠自动展开）
    tail = re.search(r"<script>\s*\(function \(\) \{\s*var d = document.getElementById\('ccFold'\).*?</script>", page, re.S)
    spec["tail_script"] = tail.group(0) if tail else ""
    spec["out"] = out_file
    return spec


def main():
    base = "."
    s1 = lift("%s/接通建联(可用于案例分享).html" % base, "connect", "cases/01_接通建联.json", "接通建联(可用于案例分享).html")
    s3 = lift("%s/价值传递(可用于案例分享).html" % base, "value", "cases/03_价值传递.json", "价值传递(可用于案例分享).html")
    io.open("spec/01_接通建联.json", "w", encoding="utf-8", newline="\n").write(json.dumps(s1, ensure_ascii=False, indent=1))
    io.open("spec/03_价值传递.json", "w", encoding="utf-8", newline="\n").write(json.dumps(s3, ensure_ascii=False, indent=1))
    for f in ("spec/01_接通建联.json", "spec/03_价值传递.json"):
        d = json.load(io.open(f, encoding="utf-8"))
        print(f, "| css", len(d["css"]), "| 卡片", len(d["hero"]["cards"]), "| fold", len(d.get("fold_html", "")), "| meta", len(d["hero"]["meta"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
