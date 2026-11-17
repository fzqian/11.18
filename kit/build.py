# -*- coding: utf-8 -*-
"""把「这一页讲什么」（spec/*.json）+ 「聊天记录」（cases/*.json）拼成成品页面。

设计要点：
  1 会重复出错的东西一律由脚本算，不手写 —— 条数、tab 数字、要点版、
    客户原话锚点、复制头、图例、色条、标签。
  2 散文（标题、卡片、口径折叠、页脚）放 spec，改文案不用碰代码。
  3 客户真名不出现：cases 里写 {"real":"🐈","label":"客户A"}，
     正文里凡是出现 real 的地方，生成时一律换成 label。

用法：
  python kit/build.py                      # 全部重生成
  python kit/build.py --only 03_价值传递    # 只重生成一页
  python kit/build.py --dry                # 只报告，不写文件
"""
import argparse
import glob
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def attr(s):
    return esc(s).replace('"', "&quot;").replace("\n", "&#10;")


# ─────────────────────────── 导航 ───────────────────────────

def nav_html(nav, current_key, brand):
    out = ['<nav class="nav">', '  <div class="nav-in">',
           '    <div class="nav-brand"><i></i><span>%s</span></div>' % esc(brand),
           '    <div class="nav-links">']
    for it in nav["items"]:
        if it.get("off"):
            out.append('      <span class="nav-off" aria-disabled="true">%s<em>暂不开放</em></span>' % esc(it["label"]))
        else:
            on = ' class="on"' if it.get("key") == current_key else ""
            out.append('      <a href="%s"%s>%s</a>' % (attr(it["href"]), on, esc(it["label"])))
    out += ['    </div>', '  </div>', '  <div class="nav-progress"></div>', '</nav>']
    return "\n".join(out)


# ─────────────────────────── 单条消息 ───────────────────────────

def bar_style(ks, stages):
    if not ks:
        return "transparent"
    if len(ks) == 1:
        return stages[ks[0] - 1]["color"]
    return "linear-gradient(%s 0 50%%,%s 50%% 100%%)" % (
        stages[ks[0] - 1]["color"], stages[ks[1] - 1]["color"])


def chips_html(ks, stages):
    return '<div class="cl-chips">%s</div>' % "".join(
        '<span class="cl-chip" style="background:%s">%s</span>'
        % (stages[k - 1]["color"], esc(stages[k - 1]["chip"])) for k in ks)


def msg_html(it, i, prev_who, prev_k, stages, label_s, label_c, anchor=False):
    who = it["who"]
    name = label_s if who == "s" else label_c
    ks = it.get("k") or []
    nm = "" if prev_who == who else '<div class="cl-nm">%s</div>' % esc(name)
    chips = "" if (not ks or prev_k == ks) else chips_html(ks, stages)
    a = ' data-who="%s" data-k="%s" data-i="%d"' % (attr(name), "".join(str(x) for x in ks), i)
    if anchor:
        a += ' data-anchor="1"'
    return ('<div class="cl-msg %s"%s>%s%s<div class="cl-bub"><i class="cl-bar" style="background:%s"></i>'
            '<span class="cl-txt">%s</span></div></div>'
            % (who, a, chips, nm, bar_style(ks, stages), esc(it["x"])))


# ─────────────────────────── 消息序列 ───────────────────────────

def anchors_for(items):
    """要点版要补哪些客户原话：每一段要点的第一条之前，补最近的那句客户原话。
    同一句只补一次；几条连续要点共用一句时只留一遍。"""
    keyed_stages = set()
    for it in items:
        if it["t"] == "msg" and it.get("k"):
            keyed_stages.update(it["k"])
    out = []            # [(下标, 是否锚点)]
    last_k = None
    used = set()
    for idx, it in enumerate(items):
        if it["t"] != "msg" or not it.get("k"):
            continue
        if it["k"] != last_k:
            # 这一段的第一条如果是客户自己说的话，它本身就是锚点，不用再从上面借一句
            if it["who"] == "c":
                out.append((idx, False))
                last_k = it["k"]
                continue
            for j in range(idx - 1, -1, -1):
                p = items[j]
                if p["t"] == "msg" and p["who"] == "c" and j not in used:
                    out.append((j, True))
                    used.add(j)
                    break
        out.append((idx, False))
        last_k = it["k"]
    return out, keyed_stages


def body_html(items, stages, label_s, label_c, plain=False):
    lines = []
    prev_who, prev_k = None, None
    if plain:
        picks, keyed = anchors_for(items)
        for idx, is_anchor in picks:
            it = items[idx]
            lines.append(msg_html(it, idx, prev_who, prev_k, stages, label_s, label_c, anchor=is_anchor))
            prev_who, prev_k = it["who"], it.get("k")
        return "\n".join(lines)
    for idx, it in enumerate(items):
        if it["t"] == "time":
            lines.append('<div class="cl-time"><span>%s</span></div>' % esc(it["x"]))
        elif it["t"] == "band":
            st = stages[it["k"] - 1]
            lines.append('<div class="cl-band" style="background:%s;border-left-color:%s;color:%s">%s %s</div>'
                         % (st["bandbg"], st["color"], st["color"], st["mark"], esc(it["x"])))
        else:
            lines.append(msg_html(it, idx, prev_who, prev_k, stages, label_s, label_c))
            prev_who, prev_k = it["who"], it.get("k")
    return "\n".join(lines)


def body_html_plain(items, stages, label_s, label_c):
    """要点版：只留要点的消息 + 每段开头补一句客户原话，再保留这一段的色带。"""
    picks, keyed = anchors_for(items)
    keep = {i for i, _ in picks}
    anchors = {i for i, a in picks if a}
    lines = []
    prev_who, prev_k = None, None
    last_band_k = None
    for idx, it in enumerate(items):
        if it["t"] == "band":
            if it["k"] in keyed:
                st = stages[it["k"] - 1]
                lines.append('<div class="cl-band" style="background:%s;border-left-color:%s;color:%s">%s %s</div>'
                             % (st["bandbg"], st["color"], st["color"], st["mark"], esc(it["x"])))
            continue
        if idx not in keep:
            continue
        lines.append(msg_html(it, idx, prev_who, prev_k, stages, label_s, label_c, anchor=idx in anchors))
        prev_who, prev_k = it["who"], it.get("k")
    return "\n".join(lines)


# ─────────────────────────── 图例 ───────────────────────────

def legend_html(stages):
    sp = []
    for st in stages:
        em = "<em>%s</em>" % esc(st["legend"]) if st.get("legend") else ""
        sp.append('<span class="cl-lg"><i style="background:%s"></i><b style="color:%s">%s%s</b>%s</span>'
                  % (st["color"], st["color"], st["mark"], esc(st["name"]), em))
    return '<div class="cl-legend">%s</div>' % "".join(sp)


# ─────────────────────────── 案例卡 ───────────────────────────

def note_html(case):
    """案例末尾那句【结论】。没有就不出。"""
    n = (case.get("note") or "").strip()
    return '<div class="cl-note">%s</div>\n' % esc(n) if n else ""


def case_html(case, spec, idx):
    stages = spec["stages"]
    items = case["items"]
    label_c = case["customer"]["label"]
    label_s = case["sales"]
    total = case.get("total") or sum(1 for it in items if it["t"] == "msg")
    n_full = sum(1 for it in items if it["t"] == "msg")
    n_key = sum(1 for it in items if it["t"] == "msg" and it.get("k"))
    seg = case.get("seg", "整段")
    marks = "①②③④"[:len(stages)]
    stage_names = "／".join(st["name"] for st in stages)
    plain = body_html_plain(items, stages, label_s, label_c)
    n_plain = plain.count('class="cl-msg')
    n_anchor = plain.count('data-anchor="1"')
    full = body_html(items, stages, label_s, label_c)

    if spec["kind"] == "value":
        tabs = ('<div class="cl-tabs">'
                '<button type="button" class="cl-tab on" data-clgrp="%d" data-pane="chat%dk">要点版<b>%d</b>条</button>'
                '<button type="button" class="cl-tab" data-clgrp="%d" data-pane="chat%d">完整版<b>%d</b>条</button></div>'
                % (idx, idx, n_plain, idx, idx, n_full))
        head_p = "%s × %s｜%s · 要点版（%d 条要点 + %d 句客户原话）" % (label_s, label_c, spec["nav_name"], n_key, n_anchor)
        head_f = "%s × %s｜%s · 第 0-%d 条（%d 条原文）\n〔%s = %s〕" % (
            label_s, label_c, spec["nav_name"], total - 1, n_full, marks, stage_names)
        pane_p = ('<div class="cl-chat cl-pane" id="chat%dk" data-clgrp="%d" data-cc-plain="1" data-cc-head="%s">\n'
                  '<div class="cl-title">客户「%s」｜%s｜只看要点 · %d 条</div>\n'
                  '<div class="cl-sub">要点 %d 条（带色条）；要点前面的白气泡是客户原话，告诉你这句在回什么'
                  '（几条共用一句时只留一次）。每段开头那一行是这一段在做什么，其余对话省掉；需要看全的点上面「完整版」。</div>\n'
                  '%s\n<div class="cl-body">\n%s\n</div>\n</div>'
                  % (idx, idx, attr(head_p), esc(label_c), esc(label_s), n_plain, n_key,
                     legend_html(stages), plain))
        pane_f = ('<div class="cl-chat cl-pane" id="chat%d" data-clgrp="%d" data-cc-head="%s" hidden>\n'
                  '<div class="cl-title">客户「%s」｜%s｜%s %d 条 · %s</div>\n'
                  '<div class="cl-sub">这一段共 %d 条，图片与表情消息 %d 条略过，其余逐条排下来。'
                  '色条与标签只标一件事：这句话在完成哪一项。</div>\n'
                  '%s\n<div class="cl-body">\n%s\n</div>\n%s</div>'
                  % (idx, idx, attr(head_f), esc(label_c), esc(label_s), seg, total,
                     spec.get("tag_label", "三段标注"), total, total - n_full, legend_html(stages), full,
                     note_html(case)))
        panes = '<div class="cl-wrap"><div class="shotwin">\n%s\n%s\n%s\n</div></div>' % (tabs, pane_p, pane_f)
        art_id, art_cls = "m%d" % idx, "qcard p1 mcase rv"
        tools = ('<button type="button" class="lcb lcb1" data-lc="chat%d" data-lcgrp="%d" '
                 'data-lbl-slim="复制要点" data-lbl-full="复制全文">复制要点</button>'
                 '<button type="button" class="lcb" data-lcsel="chat%d" data-lcgrp="%d">全选</button>'
                 % (idx, idx, idx, idx))
    else:
        head_f = "%s × %s｜%s · 第 0-%d 条（%d 条原文）\n〔%s = %s〕" % (
            label_s, label_c, spec["nav_name"], total - 1, n_full, marks, stage_names)
        pane_f = ('<div class="cl-chat" id="chat%d" data-cc-head="%s">\n'
                  '<div class="cl-title">客户「%s」｜%s｜%s · 第 0-%d 条</div>\n'
                  '<div class="cl-sub">这一段共 %d 条，图片与表情消息 %d 条略过，其余逐条排下来。'
                  '色条与标签只标一件事：这句话在完成哪一项。</div>\n'
                  '%s\n<div class="cl-body">\n%s\n</div>\n%s</div>'
                  % (idx, attr(head_f), esc(label_c), esc(label_s), spec["nav_name"], total - 1,
                     total, total - n_full, legend_html(stages), full, note_html(case)))
        panes = '<div class="cl-wrap"><div class="shotwin">%s</div></div>' % pane_f
        art_id, art_cls = "c%d" % idx, "qcard cc-case rv"
        tools = ('<button type="button" class="lcb lcb1" data-lc="chat%d">复制全文</button>'
                 '<button type="button" class="lcb" data-lcsel="chat%d">全选</button>' % (idx, idx))

    return ('<article id="%s" class="%s">\n\n<figure class="mcase-shot cclive" id="live%d">\n'
            '<input type="checkbox" id="sw%d" class="swchk">\n'
            '<div class="shotbar"><span class="sbt">原文 · 整段聊天记录</span><span class="sbd">%s</span>\n'
            '<div class="cl-tools">%s'
            '<label class="swtoggle" for="sw%d"><span class="t1">展开全部 ↓</span><span class="t2">收起 ↑</span></label>\n'
            '</div></div>\n%s\n</figure>\n</article>'
            % (art_id, art_cls, idx, idx, esc(case["shot"]["hint"]), tools, idx, panes))


# ─────────────────────────── 整页 ───────────────────────────

def build(spec, nav, cases):
    h = spec["hero"]
    cards_cls = "stage4" if spec["kind"] == "connect" else "stage3"
    hero_cls = "hero hero-c" if spec["kind"] == "connect" else "hero"

    out = ['<!DOCTYPE html>', '<html lang="zh-CN">', '<head>', '<meta charset="UTF-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           "<title>%s</title>" % esc(spec["title"]),
           '<meta name="description" content="%s">' % attr(spec["desc"])]
    for c in spec["css"] + ["assets/kit.css?v=1"]:
        out.append('<link rel="stylesheet" href="%s">' % c)
    out += ["</head>", "<body>", ""]
    out.append(nav_html(nav, spec.get("key", ""), spec["brand"]))
    out.append("")
    out.append('<header class="%s">' % hero_cls)
    out.append('  <div class="hero-in">')
    out.append('    <div class="eyebrow">%s</div>' % esc(h["eyebrow"]))
    out.append("    <h1>%s</h1>" % "<br>".join(h["h1"]))
    out.append('    <div class="%s">' % cards_cls)
    for i, c in enumerate(h["cards"], start=1):
        out.append('      <div class="st s%d"><span class="stn">%s</span><b>%s</b>' % (i, c["no"], esc(c["name"])))
        out.append('        <span class="stk">%s</span><p>%s</p>' % (esc(c["kicker"]), esc(c["lead"])))
        out.append('        <span class="stq">%s</span></div>' % esc(c["note"]))
    out.append("    </div>")
    out.append('    <div class="hero-meta">%s</div>'
               % "".join("<span>%s</span>" % esc(x) for x in h["meta"]))
    out += ["  </div>", "</header>", ""]

    if spec.get("fold_html"):
        out.append('<section class="sec" id="c-rule">')
        out.append(spec["fold_html"])
        out += ["</section>", ""]

    out.append('<section class="sec" id="%s">' % ("c-good" if spec["kind"] == "connect" else "m-good"))
    out.append('<div class="sec-head rv"><div class="sec-no">%s</div>' % esc(spec["sec"]["no"]))
    out.append("<h2>%s</h2></div>" % esc(spec["sec"]["h"]))
    out.append("")
    for i, c in enumerate(cases, start=1):
        out.append(case_html(c, spec, i))
        out.append("")
    out += ["</section>", ""]
    out.append('<footer class="foot">')
    out.append("  " + spec["footer"])
    out += ["</footer>", ""]
    out.append('<script src="assets/livechat.js?v=5"></script>')
    if spec.get("tail_script"):
        out.append(spec["tail_script"])
    out += ["</body>", "</html>", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    nav = json.load(io.open(os.path.join(ROOT, "kit/nav.json"), encoding="utf-8"))
    specs = sorted(glob.glob(os.path.join(ROOT, "spec/*.json")))
    if not specs:
        print("spec/ 里没有 JSON，先跑 kit/_lift.py")
        return 1
    for sp in specs:
        name = os.path.basename(sp)[:-5]
        if a.only and a.only not in name:
            continue
        spec = json.load(io.open(sp, encoding="utf-8"))
        doc = json.load(io.open(os.path.join(ROOT, spec["cases"]), encoding="utf-8"))
        for c in doc["cases"]:
            real, label = c["customer"]["real"], c["customer"]["label"]
            if real and label and real != label:
                for it in c["items"]:
                    if it.get("x"):
                        it["x"] = it["x"].replace(real, label)
                for k in ("note", "sub", "title"):
                    if c.get(k):
                        c[k] = c[k].replace(real, label)
        html = build(spec, nav, doc["cases"])
        out = os.path.join(ROOT, spec["out"])
        if a.dry:
            print("  （--dry）%s  %d 字节" % (spec["out"], len(html.encode("utf-8"))))
        else:
            io.open(out, "w", encoding="utf-8", newline="\n").write(html)
            print("  写出 %s（%d 字节）" % (spec["out"], len(html.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
