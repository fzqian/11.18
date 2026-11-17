# -*- coding: utf-8 -*-
"""
案例页生成器.py —— 单文件版 v1.0
===============================================================================
一句话：一份 JSON 描述「这一页讲什么」+「聊天记录怎么标」，脚本拼成一页 HTML。
       样式、脚本、两个已完成阶段的完整真实数据，全部内嵌在这一个文件里。
       不依赖 assets/ 目录，不装任何第三方库，双击能跑，拷到哪都能跑。

--------------------------------------------------------------------------
一、这套页面固定由五块组成（每页都一样，别自己发明第六块）
--------------------------------------------------------------------------
  1 顶部导航   六阶段主干（接通建联 / 定级探需 / 价值传递 / 方案报价 / 异议处理 / 逼单收口）
               当前页深色高亮；还没做的阶段是灰字带「暂不开放」小标，点不动
  2 首屏 hero  1 行小标 + 2 行大标题（第二行斜体强调）+ 判据卡 + 1 行 meta
               判据卡 3 张 = 三列（stage3）／4 张 = 四列（stage4），按张数自动选
  3 折叠口径   配置里给了 fold_html 才出：<details> 默认折着，落到 #c-rule 自动展开
                （接通建联是这版；价值传递没有）
  4 案例区     每案一张卡：工具栏（原文说明 + 复制按钮 + 展开全部）＋ 聊天记录
  5 页脚

--------------------------------------------------------------------------
二、层级＝颜色，这是全部重点
--------------------------------------------------------------------------
  cfg.stages[] 定义层级：每层一个颜色、一个圆圈标（①②③④）、一个色带底色。
    {"no":1,"mark":"①","name":"形态","chip":"①形态","color":"#2563EB",
     "bandbg":"#E8EFFF","legend":"我买的是什么"}

  cfg.cases[].items[] 是聊天记录，逐条排，三种：
    {"t":"time","x":"9月29日 11:44"}                  时间条
    {"t":"band","k":1,"x":"这一段在做什么"}             色带（同一层级的消息共用一个色带）
    {"t":"msg","who":"s","k":[1],"x":"原文"}           who: s=招生老师／c=客户
                                                     k 为空 = 不标 = 灰条

  两个版本（kind=dual）：
    完整版  全部消息按时间排；标了的挂左侧色条 + 右侧标签；色带插在每段开头
    要点版  只留标了的消息；每段第一条之前，自动补最近一句客户原话（灰条，
            打 data-anchor）—— 这就是「锚点」，防止要点版看起来像自说自话。
            同一句客户原话只补一次；几条要点共用一句时只留一遍。

  复制（页面上那两个按钮）：
    拼成「招生老师：正文　〔②〕」，一句话一行，客户原话锚点也一起带出去；
    要点版是给销售照着念的，不带〔〕。走 clipboard API，file:// 下自动退
    textarea + execCommand，再不行就自动全选提示 Ctrl+C。

--------------------------------------------------------------------------
三、新对话里怎么用（照这五步，别自己改结构）
--------------------------------------------------------------------------
  1) python 案例页生成器.py schema
        打印数据结构 + 硬规则，先看一遍
  2) python 案例页生成器.py new --kind dual --out 配置_方案报价.json
        出一份带 TODO 的骨架
  3) 把聊天记录逐条填进 cases[0].items，标好 k（这一句在完成哪一项）
     把文案填进 hero / stages / sec / footer
  4) python 案例页生成器.py build 配置_方案报价.json --out 方案报价.html
  5) python 案例页生成器.py check 配置_方案报价.json 方案报价.html
        二十多项断言；不过不许交付

  其他：
    python 案例页生成器.py demo              重新生成「接通建联 / 价值传递」两页（内嵌真实数据）
    python 案例页生成器.py demo --out 目录   指定输出目录
    python 案例页生成器.py selftest          造两页 + 全量自检，一条命令验全套
    python 案例页生成器.py build x.json --link   不内联样式，改引 assets/（和桌面现有两页一致）

--------------------------------------------------------------------------
四、几条不会变的口径
--------------------------------------------------------------------------
  · 客户真名不出现：cases[].customer = {"real":"真名","label":"客户A"}，
    生成时把正文里所有 real 换成 label；报过姓的用「姓+女士/先生」，没报姓的用客户A/B。
  · 条数一律由脚本算，不手写：标签页数字、复制头「第 0-N 条（M 条原文）」、
    标题「只看要点 · N 条」全部从 items 推。total 写原文总条数（含被略过的图片/表情条）。
  · 页面上的字只有三处来自「散文」：hero 卡片、折叠口径、页脚。其余全是数据推出来的。
  · 截图不进页面（只留文字）。要图另做，别塞回来。

===============================================================================
"""
import argparse
import io
import json
import os
import re
import sys

VERSION = "1.0"
CIRCLED = "①②③④⑤⑥"

KIND_ALIAS = {"value": "dual", "connect": "single"}

# 默认样式表顺序：先底座，再页面类型，最后补丁
CSS_OF_KIND = {
    "dual": ["style.css", "manual.css", "livechat.css", "kit.css"],
    "single": ["style.css", "manual.css", "livechat.css", "connect.css", "kit.css"],
}

NAV = None      # 由文件末尾注入
DEMO = None     # 由文件末尾注入
ASSETS = None   # 由文件末尾注入


# ───────────────────────────── 小工具 ─────────────────────────────

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def attr(s):
    return esc(s).replace('"', "&quot;").replace("\n", "&#10;")


def kind_of(cfg):
    k = cfg.get("kind", "dual")
    return KIND_ALIAS.get(k, k)


def safe_stdout():
    """cmd.exe 是 GBK，✓ / ✗ 印不出来会直接崩，这里别让它崩。"""
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(errors="replace")
        except Exception:
            pass


# ───────────────────────────── 导航 ─────────────────────────────

def nav_html(nav, current_key, brand):
    out = ['<nav class="nav">', '  <div class="nav-in">',
           '    <div class="nav-brand"><i></i><span>%s</span></div>' % esc(brand),
           '    <div class="nav-links">']
    for it in nav["items"]:
        if it.get("off"):
            out.append('      <span class="nav-off" aria-disabled="true">%s<em>暂不开放</em></span>'
                       % esc(it["label"]))
        else:
            on = ' class="on"' if it.get("key") == current_key else ""
            out.append('      <a href="%s"%s>%s</a>' % (attr(it["href"]), on, esc(it["label"])))
    out += ['    </div>', '  </div>', '  <div class="nav-progress"></div>', '</nav>']
    return "\n".join(out)


# ───────────────────────────── 单条消息 ─────────────────────────────

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


# ───────────────────────────── 消息序列 ─────────────────────────────

def anchors_for(items):
    """要点版补哪些客户原话：每段要点的第一条之前，补最近的那句客户原话。
    同一句只补一次；几条连续要点共用一句时只留一遍。"""
    keyed_stages = set()
    for it in items:
        if it["t"] == "msg" and it.get("k"):
            keyed_stages.update(it["k"])
    out, last_k, used = [], None, set()
    for idx, it in enumerate(items):
        if it["t"] != "msg" or not it.get("k"):
            continue
        if it["k"] != last_k:
            # 这一段第一条就是客户自己说的，它本身就是锚点，不用再从上面借
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


def body_full(items, stages, label_s, label_c):
    """完整版：时间 / 色带 / 消息，逐条排下来。"""
    lines, prev_who, prev_k = [], None, None
    for idx, it in enumerate(items):
        if it["t"] == "time":
            lines.append('<div class="cl-time"><span>%s</span></div>' % esc(it["x"]))
        elif it["t"] == "band":
            st = stages[it["k"] - 1]
            lines.append('<div class="cl-band" style="background:%s;border-left-color:%s;color:%s">%s %s</div>'
                         % (st["bandbg"], st["color"], st["color"], st["mark"], esc(it["x"])))
            prev_k = None
        else:
            lines.append(msg_html(it, idx, prev_who, prev_k, stages, label_s, label_c))
            prev_who, prev_k = it["who"], it.get("k")
    return "\n".join(lines)


def body_plain(items, stages, label_s, label_c):
    """要点版：只留要点的消息 + 每段开头补一句客户原话，色带只留这一段的。"""
    picks, keyed = anchors_for(items)
    keep = {i for i, _ in picks}
    anchors = {i for i, a in picks if a}
    lines, prev_who, prev_k = [], None, None
    for idx, it in enumerate(items):
        if it["t"] == "band":
            if it["k"] in keyed:
                st = stages[it["k"] - 1]
                lines.append('<div class="cl-band" style="background:%s;border-left-color:%s;color:%s">%s %s</div>'
                             % (st["bandbg"], st["color"], st["color"], st["mark"], esc(it["x"])))
                prev_k = None
            continue
        if idx not in keep:
            continue
        lines.append(msg_html(it, idx, prev_who, prev_k, stages, label_s, label_c, anchor=idx in anchors))
        prev_who, prev_k = it["who"], it.get("k")
    return "\n".join(lines)


# ───────────────────────────── 图例 / 结论 ─────────────────────────────

def legend_html(stages):
    sp = []
    for st in stages:
        em = "<em>%s</em>" % esc(st["legend"]) if st.get("legend") else ""
        sp.append('<span class="cl-lg"><i style="background:%s"></i><b style="color:%s">%s%s</b>%s</span>'
                  % (st["color"], st["color"], st["mark"], esc(st["name"]), em))
    return '<div class="cl-legend">%s</div>' % "".join(sp)


def note_html(case):
    n = (case.get("note") or "").strip()
    return '<div class="cl-note">%s</div>\n' % esc(n) if n else ""


# ───────────────────────────── 案例卡 ─────────────────────────────

def case_html(case, cfg, idx):
    stages = cfg["stages"]
    items = case["items"]
    label_c = case["customer"]["label"]
    label_s = case.get("sales", "招生老师")
    total = case.get("total") or sum(1 for it in items if it["t"] == "msg")
    n_full = sum(1 for it in items if it["t"] == "msg")
    n_key = sum(1 for it in items if it["t"] == "msg" and it.get("k"))
    seg = case.get("seg", "整段")
    nav_name = cfg.get("nav_name", "案例")
    marks = CIRCLED[:len(stages)]
    stage_names = "／".join(st["name"] for st in stages)
    full = body_full(items, stages, label_s, label_c)

    head_f = "%s × %s｜%s · 第 0-%d 条（%d 条原文）\n〔%s = %s〕" % (
        label_s, label_c, nav_name, total - 1, n_full, marks, stage_names)

    if kind_of(cfg) == "dual":
        plain = body_plain(items, stages, label_s, label_c)
        n_plain = plain.count('class="cl-msg')
        n_anchor = plain.count('data-anchor="1"')
        tabs = ('<div class="cl-tabs">'
                '<button type="button" class="cl-tab on" data-clgrp="%d" data-pane="chat%dk">要点版<b>%d</b>条</button>'
                '<button type="button" class="cl-tab" data-clgrp="%d" data-pane="chat%d">完整版<b>%d</b>条</button></div>'
                % (idx, idx, n_plain, idx, idx, n_full))
        head_p = "%s × %s｜%s · 要点版（%d 条要点 + %d 句客户原话）" % (
            label_s, label_c, nav_name, n_key, n_anchor)
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
                     cfg.get("tag_label", "标注"), total, total - n_full,
                     legend_html(stages), full, note_html(case)))
        panes = '<div class="cl-wrap"><div class="shotwin">\n%s\n%s\n%s\n</div></div>' % (tabs, pane_p, pane_f)
        art_id, art_cls = "m%d" % idx, "qcard p1 mcase rv"
        tools = ('<button type="button" class="lcb lcb1" data-lc="chat%d" data-lcgrp="%d" '
                 'data-lbl-slim="复制要点" data-lbl-full="复制全文">复制要点</button>'
                 '<button type="button" class="lcb" data-lcsel="chat%d" data-lcgrp="%d">全选</button>'
                 % (idx, idx, idx, idx))
    else:
        pane_f = ('<div class="cl-chat" id="chat%d" data-cc-head="%s">\n'
                  '<div class="cl-title">客户「%s」｜%s｜%s · 第 0-%d 条</div>\n'
                  '<div class="cl-sub">这一段共 %d 条，图片与表情消息 %d 条略过，其余逐条排下来。'
                  '色条与标签只标一件事：这句话在完成哪一项。</div>\n'
                  '%s\n<div class="cl-body">\n%s\n</div>\n%s</div>'
                  % (idx, attr(head_f), esc(label_c), esc(label_s), nav_name, total - 1,
                     total, total - n_full, legend_html(stages), full, note_html(case)))
        panes = '<div class="cl-wrap"><div class="shotwin">%s</div></div>' % pane_f
        art_id, art_cls = "c%d" % idx, "qcard cc-case rv"
        tools = ('<button type="button" class="lcb lcb1" data-lc="chat%d">复制全文</button>'
                 '<button type="button" class="lcb" data-lcsel="chat%d">全选</button>' % (idx, idx))

    hint = (case.get("shot") or {}).get("hint", "")
    return ('<article id="%s" class="%s">\n\n<figure class="mcase-shot cclive" id="live%d">\n'
            '<input type="checkbox" id="sw%d" class="swchk">\n'
            '<div class="shotbar"><span class="sbt">原文 · 整段聊天记录</span><span class="sbd">%s</span>\n'
            '<div class="cl-tools">%s'
            '<label class="swtoggle" for="sw%d"><span class="t1">展开全部 ↓</span><span class="t2">收起 ↑</span></label>\n'
            '</div></div>\n%s\n</figure>\n</article>'
            % (art_id, art_cls, idx, idx, esc(hint), tools, idx, panes))


# ───────────────────────────── 整页 ─────────────────────────────

def style_block(cfg, inline):
    """inline=True 把样式直接写进 <style>，页面就是单文件；False 仍引 assets/。"""
    names = cfg.get("css") or CSS_OF_KIND[kind_of(cfg)]
    if not inline:
        return "\n".join('<link rel="stylesheet" href="assets/%s?v=%d">' % (n, VER_STR.get(n, 1))
                         for n in names)
    out = []
    for n in names:
        body = ASSETS.get(n)
        if body is None:
            raise SystemExit("内嵌样式缺 %s" % n)
        out.append("<style>\n/* ===== %s ===== */\n%s\n</style>" % (n, body.strip()))
    return "\n".join(out)


VER_STR = {"style.css": 10, "manual.css": 2, "livechat.css": 5, "connect.css": 5, "kit.css": 1}


def render(cfg, inline=True):
    h = cfg["hero"]
    cards = h["cards"]
    cards_cls = "stage4" if len(cards) >= 4 else "stage3"
    hero_cls = "hero hero-c" if len(cards) >= 4 else "hero"
    nav = cfg.get("nav") or NAV

    out = ['<!DOCTYPE html>', '<html lang="zh-CN">', '<head>', '<meta charset="UTF-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           "<title>%s</title>" % esc(cfg["title"]),
           '<meta name="description" content="%s">' % attr(cfg.get("desc", ""))]
    out.append(style_block(cfg, inline))
    out += ["</head>", "<body>", ""]
    out.append(nav_html(nav, cfg.get("key", ""), cfg["brand"]))
    out.append("")
    out.append('<header class="%s">' % hero_cls)
    out.append('  <div class="hero-in">')
    out.append('    <div class="eyebrow">%s</div>' % esc(h["eyebrow"]))
    out.append("    <h1>%s</h1>" % "<br>".join(h["h1"]))
    out.append('    <div class="%s">' % cards_cls)
    for i, c in enumerate(cards, start=1):
        out.append('      <div class="st s%d"><span class="stn">%s</span><b>%s</b>' % (i, c["no"], esc(c["name"])))
        out.append('        <span class="stk">%s</span><p>%s</p>' % (esc(c["kicker"]), esc(c["lead"])))
        out.append('        <span class="stq">%s</span></div>' % esc(c["note"]))
    out.append("    </div>")
    out.append('    <div class="hero-meta">%s</div>'
               % "".join("<span>%s</span>" % esc(x) for x in h.get("meta", [])))
    out += ["  </div>", "</header>", ""]

    if cfg.get("fold_html"):
        out.append('<section class="sec" id="c-rule">')
        out.append(cfg["fold_html"])
        out += ["</section>", ""]

    sec_id = cfg.get("sec_id") or ("c-good" if kind_of(cfg) == "single" else "m-good")
    out.append('<section class="sec" id="%s">' % sec_id)
    out.append('<div class="sec-head rv"><div class="sec-no">%s</div>' % esc(cfg["sec"]["no"]))
    out.append("<h2>%s</h2></div>" % esc(cfg["sec"]["h"]))
    out.append("")
    for i, c in enumerate(cfg["cases"], start=1):
        out.append(case_html(c, cfg, i))
        out.append("")
    out += ["</section>", ""]
    out.append('<footer class="foot">')
    out.append("  " + cfg.get("footer", ""))
    out += ["</footer>", ""]

    js = ASSETS["livechat.js"]
    if inline:
        out.append("<script>\n%s\n</script>" % js.strip())
    else:
        out.append('<script src="assets/livechat.js?v=5"></script>')
    if cfg.get("tail_script"):
        out.append(cfg["tail_script"])
    out += ["</body>", "</html>", ""]
    return "\n".join(out)


# ───────────────────────────── 校验 ─────────────────────────────

def panes(page):
    out = {}
    for part in re.split(r'(?=<div class="cl-chat[^"]*" id="chat\d+k?")', page)[1:]:
        pid = re.search(r'id="(chat\d+k?)"', part).group(1)
        out[pid] = part
    return out


def msgs_of(chunk):
    body = chunk.split('<div class="cl-body">', 1)[-1]
    return re.findall(r'<div class="cl-msg ([sc])"([^>]*)>', body)


def run_check(cfg, page, verbose=True):
    ok_l, bad_l, warn_l = [], [], []

    def ok(m):
        ok_l.append(m)

    def bad(m):
        bad_l.append(m)

    P = panes(page)
    nav = cfg.get("nav") or NAV
    cases = cfg["cases"]

    if verbose:
        print("\n检查 %s（%d 字节）" % (cfg.get("out", "页面"), len(page.encode("utf-8"))))

    # 1 结构
    opens = len(re.findall(r"<div\b", page))
    closes = len(re.findall(r"</div>", page))
    (ok if opens == closes else bad)("div 开合 %d/%d" % (opens, closes))
    if len(P) == len(set(P)):
        ok("pane 不重复：%s" % " ".join(sorted(P)))
    else:
        bad("pane id 重复")
    for m in re.finditer(r'data-lc="(chat\d+)"', page):
        (ok if m.group(1) in P else bad)("复制按钮指向 %s" % m.group(1))
    for m in re.finditer(r'data-lcsel="(chat\d+)"', page):
        (ok if m.group(1) in P else bad)("全选按钮指向 %s" % m.group(1))

    # 2 条数（标签页 vs 实际）
    tabs = re.findall(r'class="cl-tab[^"]*"[^>]*data-pane="(chat\d+k?)"[^>]*>[^<]*<b>(\d+)</b>', page)
    for pid, n in tabs:
        real = len(msgs_of(P.get(pid, "")))
        (ok if int(n) == real else bad)("%s 标签写 %s 条，实际 %d 条" % (pid, n, real))

    # 2b 条数（复制头 / 标题 vs 原文总条数）
    for i, case in enumerate(cases, start=1):
        pid = "chat%d" % i
        chunk = P.get(pid, "")
        n_msg = len(msgs_of(chunk))
        real_total = case.get("total") or n_msg
        head = re.search(r'data-cc-head="([^"]*)"', chunk)
        if head:
            hh = head.group(1).replace("&#10;", "\n")
            m = re.search(r"第 0-(\d+) 条（(\d+) 条原文）", hh)
            if m:
                (ok if int(m.group(2)) == n_msg else bad)(
                    "%s 复制头写 %s 条原文，实际 %d 条" % (pid, m.group(2), n_msg))
                (ok if int(m.group(1)) == real_total - 1 else bad)(
                    "%s 复制头写第 0-%s 条，原文共 %d 条" % (pid, m.group(1), real_total))
        tt = re.search(r'<div class="cl-title">(.*?)</div>', chunk)
        if tt:
            t = tt.group(1)
            rg = re.search(r"第 0-(\d+) 条", t)
            m = re.search(r"(\d+) 条", t)
            want = real_total - 1 if rg else real_total
            got = int(rg.group(1)) if rg else (int(m.group(1)) if m else None)
            (ok if got == want else bad)("%s 标题写 %s，应为 %d（原文共 %d 条）"
                                         % (pid, got, want, real_total))
        if n_msg > real_total:
            bad("%s 排了 %d 条，超过原文总条数 %d" % (pid, n_msg, real_total))

    # 3 要点版
    want_note = sum(1 for c in cases if (c.get("note") or "").strip())
    got_note = len(re.findall(r'<div class="cl-note">', page))
    (ok if want_note == got_note else bad)("【结论】块 %d 个，配置里写了 %d 个" % (got_note, want_note))
    for i, case in enumerate(cases, start=1):
        pid = "chat%dk" % i
        if pid not in P:
            continue
        ms = msgs_of(P[pid])
        keyed = sum(1 for w, a in ms if re.search(r'data-k="[0-9]+"', a))
        anchors = [(w, a) for w, a in ms if "data-anchor" in a]
        (ok if len(ms) == keyed + len(anchors) else bad)(
            "%s 共 %d 条 = 要点 %d + 锚点 %d" % (pid, len(ms), keyed, len(anchors)))
        for j, (w, at) in enumerate(anchors, start=1):
            if w != "c":
                bad("%s 第 %d 个锚点不是客户说的" % (pid, j))
            if re.search(r'data-k="[0-9]+"', at):
                bad("%s 第 %d 个锚点自己挂了标注，会重复计要点" % (pid, j))
        req = sum(1 for it in case["items"] if it["t"] == "msg" and it.get("k"))
        (ok if keyed == req else bad)("%s 要点 %d 条，配置里标了 %d 条" % (pid, keyed, req))

    # 4 客户代号
    reals = [c["customer"].get("real", "") for c in cases if c["customer"].get("real")]
    hit = [r for r in reals if r and r in page]
    (ok if not hit else bad)("真名残留：%s" % ("无" if not hit else "、".join(hit)))
    for c in cases:
        if c["customer"].get("label") in ("客户", "", None):
            bad("代号没起：%s" % c["customer"])

    # 5 标签
    loose = len(re.findall(r"</div><span class=\"cl-chip\"", page))
    (ok if loose == 0 else bad)("裸标签（chip 没在 cl-chips 里）：%d 处" % loose)
    empty = page.count('<div class="cl-chips"></div>')
    (ok if empty == 0 else bad)("空 cl-chips：%d 处" % empty)
    fullwidth = len(re.findall(r'style="[^"]*：', page))
    (ok if fullwidth == 0 else bad)("style 里有全角冒号：%d 处" % fullwidth)
    # 6 导航
    links = re.findall(r'<a href="([^"]*)"( class="on")?>([^<]*)</a>', page)
    offs = re.findall(r'<span class="nav-off"[^>]*>([^<]*)<em>', page)
    (ok if len(links) + len(offs) == len(nav["items"]) else bad)(
        "导航 %d 项，应为 %d 项" % (len(links) + len(offs), len(nav["items"])))
    on = [t for _, c, t in links if c]
    (ok if len(on) == 1 else bad)("当前页高亮 %d 个：%s" % (len(on), on))
    if on and cfg.get("key"):
        (ok if on[0] == cfg["nav_name"] else bad)("高亮的是「%s」，配置里 nav_name 是「%s」" % (on[0], cfg["nav_name"]))
    for lbl in offs:
        (ok if "暂不开放" in page else bad)("暂不开放项 %s 缺小标" % lbl)
    if re.search(r'<a[^>]*\shref=""', page):
        bad('有 href="" 的空链接，点了会重载当前页')

    # 7 卡片
    cards = re.findall(r'<div class="st s(\d)"><span class="stn">(.)</span><b>(.*?)</b>', page)
    (ok if len(cards) == len(cfg["hero"]["cards"]) else bad)(
        "卡片 %d 张，配置里 %d 张" % (len(cards), len(cfg["hero"]["cards"])))
    for i, (n, mark, nm) in enumerate(cards, start=1):
        if int(n) != i:
            bad("卡片顺序错：第 %d 张写成 s%s" % (i, n))
        if mark != cfg["stages"][i - 1]["mark"]:
            bad("卡片「%s」的标记是 %s，stages 里是 %s" % (nm, mark, cfg["stages"][i - 1]["mark"]))

    # 8 图例
    for st in cfg["stages"]:
        if ('<b style="color:%s">%s%s</b>' % (st["color"], st["mark"], st["name"])) not in page:
            bad("图例缺 %s%s" % (st["mark"], st["name"]))
    ok("图例 %d 段都在" % len(cfg["stages"]))

    # 8b 层级真的有被用到
    used = set()
    for c in cases:
        for it in c["items"]:
            if it["t"] == "msg":
                used.update(it.get("k") or [])
            elif it["t"] == "band":
                used.add(it["k"])
    for st in cfg["stages"]:
        if st["no"] not in used:
            warn_l.append("第 %s 层「%s」一条都没标，图例会多出一项" % (st["mark"], st["name"]))

    # 9 全局
    (ok if "客户「客户」" not in page else bad)("标题出现「客户「客户」」")
    for token in ("TODO", "{{", "}}", "None"):
        if token in page:
            bad("页面里残留占位符 %r" % token)

    # 10 引用 / 内联
    if "<style>" in page:
        ok("样式已内联（单文件，不依赖 assets/）")
        if 'rel="stylesheet"' in page:
            warn_l.append("既内联又引了外部样式表")
        (ok if "<script>" in page else bad)("脚本没内联")
    else:
        for ref in re.findall(r'(?:href|src)="(assets/[^"?]+)', page):
            if not os.path.exists(ref):
                warn_l.append("引用了 %s，当前目录没有（--link 模式需 assets/ 在旁边）" % ref)
        ok("外链样式/脚本模式")

    if verbose:
        print("通过 %d 项" % len(ok_l))
        for w in warn_l:
            print("  · 提示 " + w)
        for b in bad_l:
            print("  ✗ " + b)
        print("全部通过" if not bad_l else "未通过 %d 项" % len(bad_l))
    return ok_l, bad_l, warn_l


# ───────────────────────────── 配置规整 ─────────────────────────────

def prepare(cfg):
    """把真名换成代号；补齐默认值。返回新 cfg（不改原件）。"""
    cfg = json.loads(json.dumps(cfg))      # 深拷贝
    for c in cfg["cases"]:
        real = (c["customer"].get("real") or "").strip()
        label = (c["customer"].get("label") or "").strip()
        if real and label and real != label:
            for it in c["items"]:
                if it.get("x"):
                    it["x"] = it["x"].replace(real, label)
            for k in ("note", "sub", "title"):
                if c.get(k):
                    c[k] = c[k].replace(real, label)
        c.setdefault("sales", "招生老师")
        c.setdefault("seg", "整段")
    cfg.setdefault("tag_label", "标注")
    cfg.setdefault("desc", cfg.get("title", ""))
    return cfg


def out_path(cfg, out_arg):
    name = cfg.get("out") or re.sub(r"[\\/:*?\"<>|]", "_", cfg.get("title", "案例页")) + ".html"
    if out_arg:
        if os.path.isdir(out_arg) or out_arg.endswith(("/", "\\")):
            return os.path.join(out_arg, os.path.basename(name))
        return out_arg
    return name


def build_one(cfg, out_arg="", inline=True, verbose=True):
    cfg = prepare(cfg)
    page = render(cfg, inline=inline)
    path = out_path(cfg, out_arg)
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(path, "w", encoding="utf-8", newline="\n").write(page)
    if verbose:
        print("写出 %s（%d 字节）" % (path, len(page.encode("utf-8"))))
    return path, page, cfg


# ───────────────────────────── 骨架 ─────────────────────────────

SKELETON = {
    "kind": "dual",
    "out": "TODO_阶段名.html",
    "title": "TODO 阶段名｜体德智训 · 阶段 4",
    "desc": "TODO 一句话说明这一页给谁看、看完能干什么。",
    "brand": "体德智训 · 阶段名",
    "key": "stage4",
    "nav_name": "方案报价",
    "tag_label": "三段标注",
    "hero": {
        "eyebrow": "Stage 4 · 阶段名",
        "h1": ["第一行讲判断", "<em>第二行讲做对的样子</em>"],
        "cards": [
            {"no": "①", "name": "TODO 第一件", "kicker": "判销售的行动", "lead": "一句话说清判什么", "note": "怎么算成立"},
            {"no": "②", "name": "TODO 第二件", "kicker": "判销售的行动", "lead": "一句话说清判什么", "note": "怎么算成立"},
            {"no": "③", "name": "TODO 第三件", "kicker": "判客户的反应", "lead": "一句话说清判什么", "note": "怎么算成立"},
        ],
        "meta": ["TODO 一句口径总结", "聊天记录整段可查"],
    },
    "stages": [
        {"no": 1, "mark": "①", "name": "TODO 层一", "chip": "①层一", "color": "#2563EB", "bandbg": "#E8EFFF", "legend": "客户心里的问题"},
        {"no": 2, "mark": "②", "name": "TODO 层二", "chip": "②层二", "color": "#0E9F6E", "bandbg": "#E6F9F1", "legend": "客户心里的问题"},
        {"no": 3, "mark": "③", "name": "TODO 层三", "chip": "③层三", "color": "#D97706", "bandbg": "#FFF4DF", "legend": "客户心里的问题"},
    ],
    "sec": {"no": "第 2 块 / 做对的", "h": "参考话术："},
    "footer": '<div class="eyebrow">Stage 4 · 阶段名</div>\n  <p>TODO 页脚：判据取自哪份文档 ｜ 样例：招生老师 × 客户A，共 N 条 ｜ 逐句读过原文，非词表命中</p>',
    "fold_html": "",
    "tail_script": "",
    "cases": [
        {
            "id": "c1",
            "sales": "招生老师",
            "customer": {"real": "TODO 真名", "label": "客户A"},
            "shot": {"hint": "①第 1-3 条 ②第 5 条 ③第 8-9 条"},
            "note": "【结论】TODO 这一段做对了什么，一句话。",
            "total": 9,
            "seg": "整段",
            "items": [
                {"t": "time", "x": "9月29日 11:44"},
                {"t": "msg", "who": "c", "k": [], "x": "TODO 客户第一句"},
                {"t": "band", "k": 1, "x": "TODO 这一段销售在干什么"},
                {"t": "msg", "who": "s", "k": [1], "x": "TODO 销售原文，逐字"},
                {"t": "msg", "who": "c", "k": [], "x": "TODO 客户回一句"},
                {"t": "band", "k": 2, "x": "TODO 第二段在干什么"},
                {"t": "msg", "who": "s", "k": [2], "x": "TODO 销售原文"},
                {"t": "band", "k": 3, "x": "TODO 第三段在干什么"},
                {"t": "msg", "who": "s", "k": [3], "x": "TODO 销售原文"},
            ],
        }
    ],
}

SCHEMA_TEXT = r"""
================================================================================
数据结构（一份 JSON = 一页；键全在下面，没有第六块）
================================================================================

kind            "dual" | "single"        dual = 要点版 + 完整版两档（价值传递就是这版）
                                          single = 只有完整版（接通建联就是这版）
                                          （兼容旧名 value=dual、connect=single）
out             输出文件名，如 "方案报价(可用于案例分享).html"
title           <title>，形如「阶段名｜体德智训 · 阶段 4」
desc            meta description，一句话
brand           导航左上角那行，形如「体德智训 · 方案报价」
key             导航高亮用，要和 nav 里对应项的 key 一致
nav_name        出现在复制头、标题里，如「价值传递」
nav             可选。整张导航表；不写就用文件末尾的 NAV（六阶段，后四个暂不开放）。
                开新阶段时两种做法：① 直接改文件末尾 NAV 里那一项（去 off，补 href 和 key）；
                ② 在配置里写一份完整 nav 覆盖它。

hero.eyebrow    小标，如「Stage 4 · 方案报价」
hero.h1         两行；第二行会自动套斜体强调 → ["第一行", "<em>第二行</em>"]
hero.cards[]    {no:①, name, kicker, lead, note}
                3 张 → 三列；4 张 → 四列（自动）
hero.meta[]     标题下面那一行小字，2 条左右

stages[]        层级＝颜色。{no:1, mark:"①", name:"形态", chip:"①形态",
                color:"#2563EB", bandbg:"#E8EFFF", legend:"我买的是什么"}
                · color 色条 / 标签 / 图例，三处同源
                · bandbg 色带底色，要浅
                · chip 气泡右侧那个小标签上的字
                · legend 图例里括号注释，可空

sec.no          案例区标号，写「第 2 块 / 做对的」
sec.h           「参考话术：」
footer          页脚 HTML（会原样插入，写 <div class="eyebrow"> + <p>）
fold_html       single 版的口径折叠区；顶层是 <details class="cc-fold" id="ccFold">
                summary 里三块 chips，正文 .cc-fold-body 里若干 .cc-part
tail_script     附在 </body> 前的脚本（折叠自动展开那段就是它）

cases[]         一案一张卡
  .id .sales              sales 固定写「招生老师」
  .customer {real,label}  real 是原文真名（页面上一律换成 label）
  .shot.hint              工具栏那行说明，如「三段穿插着走：出口在 24-25…」
  .note                   【结论】，一句话说这段做对了什么；不写就不出
  .total                  原文总条数（含图片/表情那几条被略过的）
  .seg                    "整段" | "整组"
  .items[]                见下

items[] 三种
  {"t":"time","x":"9月29日 11:44"}
  {"t":"band","k":1,"x":"这一段在做什么"}        同一层级共用一个色带
  {"t":"msg","who":"s","k":[1],"x":"逐字原文"}   who: s=招生老师／c=客户
                                                 k 空数组 = 不标 = 灰条

================================================================================
硬规则（脚本已经替你把关，但填的时候别故意绕）
================================================================================
1 total ≥ 实际排出来的消息条数；复制头自动写「第 0-(total-1) 条（M 条原文）」。
2 每一层（stages 里的）至少要被标到一次，否则图例多出一项、销售会问这是啥。
3 要点版不用你管：标了 k 的进要点版，前面自动补客户原话锚点。你只要保证
  「客户为什么会说这句话」在原文里有出处，脚本就能找到。
4 k 只填层级号数组，按层级顺序；同一句同时命中两层的写 [1,3]，色条会切成双色。
5 正文一律逐字原文，不改字、不删语气词、不补标点。要解释写在 band 的 x 里。
6 客户真名不许出现在页面任何位置（脚本会全文比对 real）。

================================================================================
最短工作流
================================================================================
  python 案例页生成器.py new --kind dual --out 配置_方案报价.json
  （填 TODO）
  python 案例页生成器.py build 配置_方案报价.json
  python 案例页生成器.py check 配置_方案报价.json "方案报价(可用于案例分享).html"
"""


# ───────────────────────────── CLI ─────────────────────────────

def main(argv=None):
    safe_stdout()
    ap = argparse.ArgumentParser(
        prog="案例页生成器.py",
        description="体德智训招生教材页生成器（单文件版 %s）" % VERSION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="先跑 schema 看数据结构；demo 看成品；selftest 验全套。")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("build", help="一份配置 → 一页 HTML")
    p.add_argument("config")
    p.add_argument("--out", default="")
    p.add_argument("--link", action="store_true", help="不内联样式，改引 assets/")
    p.add_argument("--no-check", action="store_true")

    p = sub.add_parser("check", help="校验一页")
    p.add_argument("config")
    p.add_argument("page", nargs="?")

    p = sub.add_parser("demo", help="用内嵌真实数据重建两页")
    p.add_argument("--out", default="输出_示例")
    p.add_argument("--link", action="store_true")

    p = sub.add_parser("new", help="出骨架配置")
    p.add_argument("--kind", default="dual", choices=["dual", "single", "value", "connect"])
    p.add_argument("--out", default="配置_新阶段.json")

    sub.add_parser("schema", help="打印数据结构与硬规则")

    p = sub.add_parser("selftest", help="造两页 + 全量自检")
    p.add_argument("--keep", action="store_true", help="保留生成的 html")

    a = ap.parse_args(argv)

    if a.cmd == "schema" or a.cmd is None:
        print(SCHEMA_TEXT)
        return 0

    if a.cmd == "new":
        sk = json.loads(json.dumps(SKELETON))
        k = KIND_ALIAS.get(a.kind, a.kind)
        sk["kind"] = k
        if k == "single":
            sk["fold_html"] = ('<details class="cc-fold rv" id="ccFold">\n'
                               '<summary class="cc-fold-sum">\n<span class="ccf-no">C1 / 口径</span>\n'
                               '<span class="ccf-t">口径细则</span>\n'
                               '<span class="ccf-chips"><b>TODO 要点一</b><b>TODO 要点二</b></span>\n'
                               '<span class="ccf-act"><span class="t1">展开看 ↓</span>'
                               '<span class="t2">收起 ↑</span></span>\n</summary>\n'
                               '<div class="cc-fold-body">\n<div class="rv cc-part">\n'
                               '<h3>TODO 小节标题</h3>\n<p>TODO 正文。</p>\n</div>\n</div>\n</details>')
            sk["tail_script"] = (
                "<script>\n/* 落 #c-rule 自动展开一次 */\n(function () {\n"
                "  var d = document.getElementById('ccFold');\n  if (!d) return;\n"
                "  function sync() { if (location.hash === '#c-rule') d.open = true; }\n"
                "  sync();\n  window.addEventListener('hashchange', sync);\n})();\n</script>")
        io.open(a.out, "w", encoding="utf-8", newline="\n").write(
            json.dumps(sk, ensure_ascii=False, indent=1) + "\n")
        print("写出骨架 %s（%s）" % (a.out, k))
        print("  1 把 TODO 全部填掉（填不完 build 出来的页面 check 会拦住）")
        print("  2 填 cases[0].items：谁说的 who、挂第几层 k、原文逐字")
        print("  3 开新阶段还要改导航：本文件末尾 NAV 里把这一项的 off 去掉、补 href")
        return 0

    if a.cmd == "check":
        cfg = json.load(io.open(a.config, encoding="utf-8-sig"))
        cfg = prepare(cfg)
        page_path = a.page or out_path(cfg, "")
        if not os.path.exists(page_path):
            print("找不到页面 %s，先 build" % page_path)
            return 2
        page = io.open(page_path, encoding="utf-8").read()
        _, bad, _ = run_check(cfg, page)
        return 0 if not bad else 2

    if a.cmd == "build":
        cfg = json.load(io.open(a.config, encoding="utf-8-sig"))
        path, page, cfg2 = build_one(cfg, a.out, inline=not a.link)
        if not a.no_check:
            _, bad, _ = run_check(cfg2, page)
            if bad:
                print("（页面已写出，但校验没过，先修上面几条再交付）")
                print("  文件：%s" % os.path.abspath(path))
                return 2
        print("打开：%s" % os.path.abspath(path))
        return 0

    if a.cmd == "demo":
        os.makedirs(a.out, exist_ok=True)
        allok = True
        for key in ("single", "dual"):
            cfg = json.loads(json.dumps(DEMO[key]))
            path, page, cfg2 = build_one(cfg, os.path.join(a.out, os.path.basename(cfg["out"])),
                                         inline=not a.link)
            json.dump(cfg, io.open(os.path.join(a.out, os.path.splitext(os.path.basename(path))[0] + ".配置.json"),
                                   "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
            _, bad, _ = run_check(cfg2, page)
            allok = allok and not bad
        return 0 if allok else 2

    if a.cmd == "selftest":
        import tempfile
        tmp = tempfile.mkdtemp(prefix="casepage_")
        total_bad = 0
        for key in ("single", "dual"):
            cfg = json.loads(json.dumps(DEMO[key]))
            path, page, cfg2 = build_one(cfg, os.path.join(tmp, "t.html"), inline=True, verbose=False)
            ok_l, bad, warn = run_check(cfg2, page, verbose=False)
            print("[%s] 通过 %d 项，未通过 %d 项%s"
                  % (key, len(ok_l), len(bad), ("　提示 %d" % len(warn)) if warn else ""))
            for b in bad:
                print("   ✗ " + b)
            total_bad += len(bad)
        # 负向测试：把页面手工改坏，检查必须拦住
        cfg = prepare(json.loads(json.dumps(DEMO["dual"])))
        good = render(cfg, inline=True)
        real = cfg["cases"][1]["customer"]["real"]
        negs = [
            ("真名漏出", good.replace("客户B", real, 1)),
            ("标签条数改错", good.replace("要点版<b>11</b>条", "要点版<b>9</b>条", 1)),
            ("裸标签 + 全角冒号",
             good.replace('<div class="cl-chips">',
                          '<span class="cl-chip" style="background：">③</span><div class="cl-chips">', 1)),
            ("锚点改成销售说的",
             good.replace('<div class="cl-msg c" data-who="客户A" data-k="" data-i=',
                          '<div class="cl-msg s" data-who="客户A" data-k="" data-i=', 1)),
        ]
        for name, broken in negs:
            if broken == good:
                print("[负向] %s：注入没生效（页面结构变了，改一下自检）" % name)
                total_bad += 1
                continue
            _, bad, _ = run_check(cfg, broken, verbose=False)
            print("[负向] %s → %s" % (name, "拦住" if bad else "没拦住 ← 检查失效"))
            if not bad:
                total_bad += 1
        print("\n%s（临时目录 %s）" % ("全部通过" if not total_bad else "有 %d 项未通过" % total_bad, tmp))
        return 0 if not total_bad else 2

    ap.print_help()
    return 0


# =============================================================================
# 以下是把 css / js / 导航 / 两份真实案例 原样内嵌的部分。
# 上面的代码是逻辑，不用动；这一段是数据，改文案请改配置 JSON，别改这里。
# =============================================================================

ASSETS = {}
ASSETS["style.css"] = r"""/* 体德智训 · 销售对话质检报告 */
:root {
  --bg: #F5F2EC;
  --paper: #FFFFFF;
  --ink: #16202C;
  --ink2: #5A6472;
  --ink3: #8C949F;
  --navy: #1F3A5F;
  --navy2: #2C527F;
  --red: #A33F31;
  --redbg: #FAF0ED;
  --green: #17695F;
  --greenbg: #ECF4F1;
  --amber: #8A6A1F;
  --amberbg: #FBF4E4;
  --line: #E6E1D6;
  --line2: #EFEBE2;
  --shadow: 0 1px 2px rgba(22,32,44,.04), 0 8px 24px -12px rgba(22,32,44,.18);
  --radius: 14px;
  --mono: "SF Mono", "JetBrains Mono", Consolas, "Courier New", monospace;
}

* { box-sizing: border-box; }

html { scroll-behavior: smooth; scroll-padding-top: 76px; }

body {
  margin: 0;
  overflow-x: hidden;
  background: var(--bg);
  color: var(--ink);
  font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Source Han Sans SC", "Noto Sans CJK SC", sans-serif;
  font-size: 15px;
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

::selection { background: #C9D8E8; }

/* ---------- 顶部导航 ---------- */
.nav {
  position: sticky; top: 0; z-index: 60;
  background: rgba(245,242,236,.86);
  backdrop-filter: saturate(180%) blur(14px);
  -webkit-backdrop-filter: saturate(180%) blur(14px);
  border-bottom: 1px solid var(--line);
}
.nav-in {
  max-width: 1180px; margin: 0 auto; padding: 0 28px;
  height: 58px; display: flex; align-items: center; gap: 8px; min-width: 0;
}
.nav-brand {
  font-size: 13.5px; font-weight: 700; letter-spacing: .04em;
  color: var(--navy); white-space: nowrap; margin-right: 12px;
  display: flex; align-items: center; gap: 8px; flex: 0 0 auto;
}
.nav-brand i {
  width: 20px; height: 20px; border-radius: 5px; display: inline-block;
  background: linear-gradient(135deg, var(--navy), #3E6B9E);
  position: relative;
}
.nav-brand i::after {
  content: ""; position: absolute; inset: 5px; border-radius: 2px;
  border: 1.5px solid rgba(255,255,255,.85); border-bottom-color: transparent;
}
.nav-links { display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; min-width: 0; flex: 1 1 auto; }
.nav-links::-webkit-scrollbar { display: none; }
.nav-links a {
  font-size: 13.5px; color: var(--ink2); text-decoration: none;
  padding: 6px 12px; border-radius: 8px; white-space: nowrap;
  transition: background .18s, color .18s;
}
.nav-links a:hover { background: rgba(31,58,95,.07); color: var(--navy); }
.nav-links a.on { background: var(--navy); color: #fff; }
.nav-progress {
  position: absolute; left: 0; bottom: -1px; height: 2px;
  background: linear-gradient(90deg, var(--navy), #5B8CC4);
  width: 0; transition: width .1s linear;
}

/* ---------- 封面 ---------- */
.hero {
  position: relative; overflow: hidden;
  background:
    radial-gradient(900px 420px at 88% -12%, rgba(107,158,214,.28), transparent 62%),
    radial-gradient(600px 300px at 4% 108%, rgba(23,105,95,.22), transparent 60%),
    linear-gradient(150deg, #14243A 0%, #1F3A5F 58%, #2A4A72 100%);
  color: #fff;
  padding: 86px 28px 74px;
}
.hero::before {
  content: ""; position: absolute; inset: 0;
  background-image: radial-gradient(rgba(255,255,255,.16) 1px, transparent 1px);
  background-size: 26px 26px; opacity: .35;
  mask-image: linear-gradient(180deg, rgba(0,0,0,.6), transparent 72%);
  -webkit-mask-image: linear-gradient(180deg, rgba(0,0,0,.6), transparent 72%);
}
.hero-in { position: relative; max-width: 1124px; margin: 0 auto; }
.eyebrow {
  font-size: 12px; letter-spacing: .22em; text-transform: uppercase;
  color: rgba(255,255,255,.62); margin-bottom: 20px;
  display: flex; align-items: center; gap: 10px;
}
.eyebrow::before {
  content: ""; width: 26px; height: 1px; background: rgba(255,255,255,.5);
}
.hero h1 {
  font-size: clamp(34px, 4.4vw, 54px); line-height: 1.16; margin: 0 0 20px;
  font-weight: 800; letter-spacing: -.015em;
}
.hero h1 em {
  font-style: normal; color: #9DC3E8;
  background: linear-gradient(90deg, #A8CDED, #7FA9D4);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.hero .sub {
  font-size: 16.5px; line-height: 1.85; color: rgba(255,255,255,.76);
  max-width: 640px; margin: 0 0 40px;
}
.hero-stats {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.14);
  border-radius: 12px; overflow: hidden; max-width: 760px;
}
.hero-stats div {
  background: rgba(10,22,38,.42); padding: 20px 22px;
}
.hero-stats b {
  display: block; font-size: 30px; font-weight: 800; letter-spacing: -.02em;
  font-variant-numeric: tabular-nums; line-height: 1.2; color: #fff;
}
.hero-stats span { font-size: 12.5px; color: rgba(255,255,255,.6); letter-spacing: .04em; }
.hero-quote {
  margin-top: 46px; padding-left: 20px; border-left: 2px solid rgba(157,195,232,.55);
  font-size: 17px; line-height: 1.9; color: rgba(255,255,255,.92); max-width: 700px;
}
.hero-quote b { color: #fff; font-weight: 700; }
.hero-meta {
  margin-top: 30px; padding-top: 18px; border-top: 1px solid rgba(255,255,255,.12);
  font-size: 11.5px; color: rgba(255,255,255,.44); line-height: 1.9;
  font-family: var(--mono); letter-spacing: .01em; max-width: 640px;
  display: flex; gap: 14px; flex-wrap: wrap;
}
.hero-meta span { white-space: nowrap; }

/* ---------- 章节 ---------- */
.sec { max-width: 1180px; margin: 0 auto; padding: 76px 28px 20px; }
.sec-head { margin-bottom: 34px; }
.sec-no {
  font-family: var(--mono); font-size: 12px; letter-spacing: .16em;
  color: var(--ink3); margin-bottom: 10px;
}
.sec h2 {
  font-size: clamp(25px, 2.6vw, 33px); margin: 0 0 12px; font-weight: 800;
  letter-spacing: -.01em; line-height: 1.3; color: var(--ink);
}
.sec .lead {
  font-size: 15.5px; color: var(--ink2); max-width: 780px; margin: 0;
  line-height: 1.9;
}
.sec .lead strong { color: var(--navy); font-weight: 700; }

/* ---------- 通用卡片 ---------- */
.card {
  background: var(--paper); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: var(--shadow);
}

/* ---------- 复核方法 ---------- */
.method { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 26px; }
.method .card { padding: 24px 22px; position: relative; overflow: hidden; }
.method .card::before {
  content: attr(data-n);
  position: absolute; right: 14px; top: 2px;
  font-family: var(--mono); font-size: 54px; font-weight: 700;
  color: var(--navy); opacity: .06; line-height: 1;
}
.method h4 { margin: 0 0 8px; font-size: 15px; color: var(--navy); font-weight: 700; }
.method p { margin: 0; font-size: 13.5px; color: var(--ink2); line-height: 1.8; }

.revoke {
  background: var(--greenbg); border: 1px solid #CFE3DD; border-radius: var(--radius);
  padding: 22px 24px; margin-bottom: 8px;
}
.revoke h4 {
  margin: 0 0 6px; font-size: 14px; color: var(--green); font-weight: 700;
  display: flex; align-items: center; gap: 8px;
}
.revoke h4 .badge {
  background: var(--green); color: #fff; font-size: 11px; padding: 2px 8px;
  border-radius: 20px; font-weight: 600; letter-spacing: .04em;
}
.revoke p { margin: 0; font-size: 13.5px; color: #37544F; line-height: 1.85; }
.revoke ul { margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 7px; }
.revoke li { font-size: 13px; color: #3A5B55; line-height: 1.72; padding-left: 18px; position: relative; }
.revoke li::before {
  content: "✓"; position: absolute; left: 0; top: 0; color: var(--green); font-weight: 700;
}
.revoke li b { color: #16443E; }

/* ---------- 问题点分布 ---------- */
.dist-legend {
  display: flex; gap: 18px; align-items: center; font-size: 12px; color: var(--ink3);
  margin: 0 0 14px; flex-wrap: wrap;
}
.dist-legend i {
  display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px;
  vertical-align: -1px;
}
.dist-legend .a { background: linear-gradient(90deg, #8E3A2C, #B9543F); }
.dist-legend .b { background: linear-gradient(90deg, #2E5A8A, #4A7CB0); }
.dist { display: grid; grid-template-columns: 1fr; gap: 8px; margin: 8px 0 30px; }
.dist-row { display: grid; grid-template-columns: 240px 1fr 44px; align-items: center; gap: 14px; }
.dist-row .nm { font-size: 13px; color: var(--ink2); text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dist-row .nm b { color: var(--ink); font-weight: 700; }
.dist-bar { height: 26px; border-radius: 5px; background: var(--line2); overflow: hidden; position: relative; }
.dist-bar i {
  display: block; height: 100%; border-radius: 5px;
  background: linear-gradient(90deg, #2E5A8A, #4A7CB0);
}
.dist-row.hi .dist-bar i { background: linear-gradient(90deg, #8E3A2C, #B9543F); }
.dist-row .vv { font-family: var(--mono); font-size: 13px; font-weight: 700; color: var(--navy); text-align: right; }
.dist-row.hi .vv { color: var(--red); }

/* ---------- 问题点卡片 ---------- */
.plist { display: grid; gap: 14px; }
.pcard { background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); }
.pcard-h {
  display: grid; grid-template-columns: 56px 1fr auto 26px; align-items: center; gap: 14px;
  padding: 18px 22px; cursor: pointer; user-select: none;
  transition: background .18s;
}
.pcard-h:hover { background: #FBFAF6; }
.pid {
  font-family: var(--mono); font-size: 13px; font-weight: 700; color: #fff;
  background: var(--navy); border-radius: 7px; text-align: center; padding: 5px 0;
  letter-spacing: .02em;
}
.pcard.sev1 .pid { background: var(--red); }
.ptitle { font-size: 16px; font-weight: 700; color: var(--ink); line-height: 1.5; }
.pmeta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 5px; }
.chip {
  font-size: 11.5px; padding: 2px 9px; border-radius: 20px;
  background: #EFF2F6; color: var(--navy2); font-weight: 600; letter-spacing: .02em;
}
.chip.red { background: #F7E9E6; color: var(--red); }
.chip.gray { background: #F1EFE9; color: var(--ink2); font-weight: 500; }
.pcount { font-family: var(--mono); font-size: 22px; font-weight: 700; color: var(--navy); white-space: nowrap; }
.pcount s { font-size: 11px; text-decoration: none; color: var(--ink3); font-family: inherit; font-weight: 500; margin-left: 3px; }
.pcard.sev1 .pcount { color: var(--red); }
.pcaret {
  width: 22px; height: 22px; border-radius: 50%; background: #F1EFE9;
  display: grid; place-items: center; color: var(--ink2); font-size: 11px;
  transition: transform .25s, background .2s;
}
.pcard.open .pcaret { transform: rotate(180deg); background: var(--navy); color: #fff; }
.pbody { display: none; padding: 0 22px 22px; border-top: 1px solid var(--line2); }
.pcard.open .pbody { display: block; animation: fade .32s ease; }
@keyframes fade { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }

.judge {
  font-size: 13px; color: var(--ink2); background: #FBF9F4;
  border-left: 3px solid #D8CFB9; border-radius: 0 8px 8px 0;
  padding: 12px 16px; margin: 16px 0 18px; line-height: 1.85;
}
.judge b { color: var(--navy); }

.case { display: grid; grid-template-columns: 1fr 300px; gap: 22px; padding: 16px 0; border-top: 1px dashed var(--line); align-items: start; }
.case:first-of-type { border-top: none; }
.case > div:first-child { align-self: center; }
.case-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 7px; flex-wrap: wrap; }
.case-no { font-family: var(--mono); font-size: 11.5px; font-weight: 700; color: #fff; background: #7E8A99; padding: 2px 7px; border-radius: 5px; }
.case-who { font-size: 12.5px; color: var(--ink2); line-height: 1.65; word-break: break-word; min-width: 0; }
.case-who b { color: var(--ink); font-weight: 600; }
.cid {
  font-family: var(--mono); font-size: 11px; font-weight: 700; letter-spacing: .02em;
  color: #1F4E79; background: #E9F0F8; border: 1px solid #C9DAEC;
  padding: 1.5px 7px; border-radius: 5px; margin-left: 9px;
  white-space: nowrap; vertical-align: 2px; cursor: help;
}
.cid.warn { color: #8A6318; background: #FBF3E2; border: 1px dashed #E3CFA4; }
.cid.none { color: #8A8A8A; background: #F1F0EC; border: 1px solid #DEDBD3; font-weight: 600; }
.lvl {
  font-size: 11px; font-weight: 700; letter-spacing: .02em; font-family: inherit;
  padding: 1.5px 7px; border-radius: 5px; margin-left: 6px; white-space: nowrap;
  vertical-align: 2px; border: 1px solid transparent;
}
.lvl[data-lv="A"] { color: #2C6B3F; background: #E8F1E4; border-color: #CBE0C4; }
.lvl[data-lv="B"] { color: #1F4E79; background: #E9F0F8; border-color: #C9DAEC; }
.lvl[data-lv="C"] { color: #6B6355; background: #F3F1EA; border-color: #E2DDD0; }
.lvl[data-lv="D"] { color: #A33F31; background: #F7ECEA; border-color: #EBD3CE; }

.case-txt { font-size: 13.5px; line-height: 1.9; color: #2C3644; margin: 0; }
.case-txt mark { background: #FBEDE9; color: var(--red); padding: 0 2px; border-radius: 2px; }
.case-shot {
  border: 1px solid var(--line); border-radius: 10px; overflow: hidden;
  cursor: zoom-in; background: #F8F7F3; position: relative; max-height: 200px;
}
.case-shot::before {
  content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 64px; z-index: 1;
  background: linear-gradient(180deg, rgba(248,247,243,0), rgba(248,247,243,.92));
  pointer-events: none;
}
.case-shot img { display: block; width: 100%; height: auto; }
.case-shot::after {
  content: "点击放大"; position: absolute; right: 8px; bottom: 8px;
  font-size: 10.5px; color: #fff; background: rgba(22,32,44,.62);
  padding: 2px 7px; border-radius: 4px; opacity: 0; transition: opacity .2s;
}
.case-shot:hover::after { opacity: 1; }

/* ---------- 六阶段 ---------- */
.stages { display: grid; grid-template-columns: repeat(6, 1fr); gap: 16px; margin-bottom: 34px; }
.stage { position: relative; padding: 0; }
.stage-in {
  background: var(--paper); border: 1px solid var(--line); border-radius: 12px;
  padding: 18px 14px 16px; height: 100%; position: relative;
  box-shadow: 0 1px 2px rgba(22,32,44,.04);
}
.stage:not(:last-child) .stage-in::after {
  content: ""; position: absolute; right: -12px; top: 50%; width: 7px; height: 7px;
  border-top: 1.6px solid #B9C2CD; border-right: 1.6px solid #B9C2CD;
  transform: translateY(-50%) rotate(45deg); z-index: 2;
}
.stage-no { font-family: var(--mono); font-size: 11px; color: var(--ink3); letter-spacing: .1em; }
.stage-nm { font-size: 14.5px; font-weight: 700; color: var(--navy); margin: 4px 0 12px; }
.stage-n { font-size: 25px; font-weight: 800; color: var(--ink); font-variant-numeric: tabular-nums; line-height: 1; }
.stage-n s { font-size: 11.5px; font-weight: 500; color: var(--ink3); text-decoration: none; margin-left: 4px; }
.stage-drop { font-size: 11.5px; color: var(--red); margin-top: 6px; font-weight: 600; }
.stage-drop.zero { color: var(--ink3); font-weight: 500; }
.stage-desc { font-size: 11.5px; color: var(--ink2); line-height: 1.65; margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line); }

/* ---------- 漏斗 ---------- */
.funnel { background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius); padding: 30px 32px 26px; box-shadow: var(--shadow); margin-bottom: 30px; }
.funnel h3 { margin: 0 0 4px; font-size: 15px; color: var(--ink); font-weight: 700; }
.funnel .hint { font-size: 12.5px; color: var(--ink3); margin: 0 0 24px; }
.fn-row { display: grid; grid-template-columns: 150px 1fr 76px; align-items: center; gap: 16px; margin-bottom: 9px; }
.fn-lbl { font-size: 13px; color: var(--ink2); text-align: right; }
.fn-lbl b { color: var(--ink); font-weight: 700; }
.fn-track { height: 34px; background: #F4F2EC; border-radius: 6px; position: relative; overflow: hidden; }
.fn-fill {
  height: 100%; border-radius: 6px;
  background: linear-gradient(90deg, #234672, #3F6F9F);
  display: flex; align-items: center; justify-content: flex-end;
  color: #fff; font-size: 13px; font-weight: 700; padding-right: 12px;
  font-variant-numeric: tabular-nums;
}
.fn-row.last .fn-fill { background: linear-gradient(90deg, #17695F, #2C8B7E); }
.fn-drop { font-size: 12px; color: var(--red); font-weight: 600; font-variant-numeric: tabular-nums; }
.fn-drop.zero { color: var(--ink3); font-weight: 500; }
.funnel .note {
  margin: 18px 0 0; padding-top: 16px; border-top: 1px dashed var(--line);
  font-size: 13px; color: var(--ink2); line-height: 1.85;
}
.funnel .note b { color: var(--red); }

/* ---------- 结论卡 ---------- */
.concl { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-bottom: 36px; }
.concl .card { padding: 26px 24px; display: flex; flex-direction: column; }
.concl .tag { font-family: var(--mono); font-size: 11px; letter-spacing: .1em; color: var(--ink3); margin-bottom: 12px; }
.concl h3 { font-size: 16.5px; margin: 0 0 14px; color: var(--ink); line-height: 1.55; font-weight: 700; }
.concl h3 em { font-style: normal; color: var(--red); }
.concl .big {
  font-size: 40px; font-weight: 800; line-height: 1; letter-spacing: -.02em;
  color: var(--navy); font-variant-numeric: tabular-nums; margin-bottom: 4px;
}
.concl .big s { font-size: 13px; text-decoration: none; font-weight: 500; color: var(--ink3); margin-left: 6px; }
.concl p { font-size: 13.5px; color: var(--ink2); line-height: 1.85; margin: 0 0 14px; }
.concl p:last-child { margin-bottom: 0; }
.concl .split {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 4px 0 16px;
  padding: 14px 0; border-top: 1px dashed var(--line); border-bottom: 1px dashed var(--line);
}
.concl .split div { text-align: center; }
.concl .split b { display: block; font-size: 26px; font-weight: 800; color: var(--navy); font-variant-numeric: tabular-nums; line-height: 1.2; }
.concl .split span { font-size: 11.5px; color: var(--ink3); }
.concl .list { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.concl .list li { font-size: 13px; color: var(--ink2); line-height: 1.8; padding-left: 16px; position: relative; }
.concl .list li::before { content: ""; position: absolute; left: 0; top: 10px; width: 5px; height: 5px; border-radius: 50%; background: #C0C8D2; }
.concl .list li b { color: var(--ink); font-weight: 600; }

/* ---------- 数据表 ---------- */
.tbl-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
.fbtn {
  border: 1px solid var(--line); background: var(--paper); color: var(--ink2);
  font-size: 12.5px; padding: 6px 13px; border-radius: 20px; cursor: pointer;
  font-family: inherit; transition: all .16s;
}
.fbtn:hover { border-color: #C3CBD5; color: var(--navy); }
.fbtn.on { background: var(--navy); border-color: var(--navy); color: #fff; font-weight: 600; }
.tbl-bar input {
  margin-left: auto; border: 1px solid var(--line); border-radius: 20px;
  background: var(--paper); padding: 7px 16px; font-size: 13px; font-family: inherit;
  color: var(--ink); width: 210px; outline: none;
}
.tbl-bar input:focus { border-color: #9AB3CE; box-shadow: 0 0 0 3px rgba(31,58,95,.07); }
.tbl-wrap { background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius); overflow-x: auto; box-shadow: var(--shadow); }
.tbl-wrap table { min-width: 620px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th {
  background: #FBF9F4; text-align: left; padding: 12px 14px; font-weight: 700;
  color: var(--ink2); font-size: 12px; letter-spacing: .03em;
  border-bottom: 1px solid var(--line); white-space: nowrap; position: sticky; top: 0; z-index: 2;
}
tbody td { padding: 11px 14px; border-bottom: 1px solid var(--line2); vertical-align: top; line-height: 1.65; }
tbody tr:hover td { background: #FBFAF6; }
tbody tr:last-child td { border-bottom: none; }
td.cust { font-weight: 700; color: var(--ink); white-space: nowrap; }
td.cust small { display: block; font-weight: 400; color: var(--ink3); font-size: 11px; margin-top: 1px; }
.stg {
  display: inline-block; font-family: var(--mono); font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: 5px; white-space: nowrap;
}
.stg.s6 { background: var(--greenbg); color: var(--green); }
.stg.s5 { background: #EAF1F7; color: var(--navy2); }
.stg.s4 { background: var(--redbg); color: var(--red); }
.stg.s3 { background: var(--amberbg); color: var(--amber); }
.stg.s2, .stg.s0 { background: #F1EFE9; color: var(--ink2); }
td.num { font-variant-numeric: tabular-nums; color: var(--ink2); white-space: nowrap; }
td.num b { color: var(--ink); }
td.tag { color: var(--ink2); }
.tbl-note { font-size: 12px; color: var(--ink3); margin-top: 12px; line-height: 1.8; }
.tbl-empty { padding: 40px; text-align: center; color: var(--ink3); font-size: 13.5px; }

/* ---------- 节奏案例 ---------- */
.rcases { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin: 34px 0 8px; }
.rcase { background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); }
.rcase-h { padding: 20px 22px 14px; }
.rcase-kind { font-size: 11px; letter-spacing: .1em; color: var(--red); font-weight: 700; text-transform: uppercase; }
.rcase-h h4 { margin: 6px 0 8px; font-size: 16px; color: var(--ink); line-height: 1.5; font-weight: 700; }
.rcase-h p { margin: 0; font-size: 13px; color: var(--ink2); line-height: 1.85; }
.rcase-shot { border-top: 1px solid var(--line); cursor: zoom-in; background: #F8F7F3; max-height: 420px; overflow: hidden; position: relative; }
.rcase-shot img { width: 100%; display: block; }
.rcase-shot::after {
  content: ""; position: absolute; inset: 0;
  background: linear-gradient(180deg, transparent 74%, rgba(248,247,243,.95));
  pointer-events: none;
}
.zoom-tip {
  position: absolute; right: 12px; top: 12px; z-index: 2;
  background: rgba(22,32,44,.74); color: #fff; font-size: 11.5px;
  padding: 5px 12px; border-radius: 20px; pointer-events: none;
  backdrop-filter: blur(4px);
}
.rcase-ft { padding: 12px 22px 16px; font-size: 12px; color: var(--ink3); border-top: 1px solid var(--line2); }

/* ---------- 优秀片段 ---------- */
.qfun { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 34px; }
.qfun .step { background: var(--paper); border: 1px solid var(--line); border-radius: 12px; padding: 20px 18px; position: relative; }
.qfun .step:not(:last-child)::after {
  content: "→"; position: absolute; right: -10px; top: 50%; transform: translateY(-50%);
  color: #C3CBD5; font-size: 14px; background: var(--bg); z-index: 2; padding: 0 2px;
}
.qfun .step b { display: block; font-size: 30px; font-weight: 800; color: var(--green); font-variant-numeric: tabular-nums; line-height: 1.1; }
.qfun .step span { font-size: 12.5px; color: var(--ink2); }
.qfun .step:last-child b { color: var(--ink); }

.qwrap { display: grid; gap: 22px; }
.qcard { background: var(--paper); border: 1px solid var(--line); border-radius: 16px; overflow: hidden; box-shadow: var(--shadow); }
.qcard-h { padding: 28px 30px 20px; border-bottom: 1px solid var(--line2); }
.qcard-no {
  display: inline-block; font-family: var(--mono); font-size: 11px; font-weight: 700;
  background: var(--green); color: #fff; padding: 3px 10px; border-radius: 5px;
  letter-spacing: .06em; margin-bottom: 12px;
}
/* 反面卡片：标签改红，和正面卡片一眼区分 */
.qcard.neg .qcard-no { background: var(--red); }
.qcard-h h3 { margin: 0 0 10px; font-size: 21px; line-height: 1.5; font-weight: 800; color: var(--ink); letter-spacing: -.005em; }
.qcard-meta { font-size: 12.5px; color: var(--ink2); font-variant-numeric: tabular-nums; }
.qcard-meta b { color: var(--green); font-weight: 700; }
.qcard-body { display: grid; grid-template-columns: 1fr 330px; gap: 0; }
.qcard-txt { padding: 24px 30px 28px; }
.qblock { margin-bottom: 18px; }
.qblock:last-child { margin-bottom: 0; }
.qlabel {
  font-size: 11.5px; font-weight: 700; letter-spacing: .08em; color: var(--navy);
  margin-bottom: 7px; display: flex; align-items: center; gap: 7px;
}
.qlabel::after { content: ""; flex: 1; height: 1px; background: var(--line2); }
.qlabel.g { color: var(--green); }
.qlabel.r { color: var(--red); }
.qblock p { margin: 0; font-size: 13.8px; line-height: 1.95; color: #2C3644; }
.qblock p + p { margin-top: 12px; }
.qacts { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
.qacts li { display: grid; grid-template-columns: 22px 1fr; gap: 10px; font-size: 13.5px; line-height: 1.9; color: #2C3644; }
.qacts li i {
  font-style: normal; font-family: var(--mono); font-size: 11px; font-weight: 700;
  color: var(--navy); background: #EEF2F7; border-radius: 5px; height: 19px;
  display: grid; place-items: center; margin-top: 3px;
}
.qopp { background: var(--redbg); border-radius: 10px; padding: 14px 16px; }
.qopp p { color: #7A3529; font-size: 13.2px; }
.qreuse { background: var(--greenbg); border-radius: 10px; padding: 14px 16px; }
.qreuse p { color: #1B4F48; font-size: 13.2px; }
.qcard-shot { border-left: 1px solid var(--line2); padding: 20px; background: #FAF9F5; }
.qcard-shot .inner { position: sticky; top: 74px; }
.qcard-shot img { width: 100%; display: block; border: 1px solid var(--line); border-radius: 10px; cursor: zoom-in; background: #fff; }
.qshot-cap { font-size: 11.5px; color: var(--ink3); text-align: center; margin-top: 10px; }

/* ---------- 规律 & 建议 ---------- */
.rules { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin: 30px 0 0; }
.rules .card { padding: 24px 24px; }
.rules .rn { font-family: var(--mono); font-size: 12px; color: var(--green); font-weight: 700; margin-bottom: 8px; }
.rules h4 { margin: 0 0 8px; font-size: 15px; color: var(--ink); font-weight: 700; line-height: 1.55; }
.rules p { margin: 0; font-size: 13.3px; color: var(--ink2); line-height: 1.85; }

.acts { display: grid; gap: 12px; }
.act { display: grid; grid-template-columns: 74px 1fr; gap: 18px; background: var(--paper); border: 1px solid var(--line); border-radius: 12px; padding: 20px 22px; box-shadow: 0 1px 2px rgba(22,32,44,.03); }
.act .p {
  font-family: var(--mono); font-size: 11.5px; font-weight: 700; color: #fff;
  background: var(--navy); border-radius: 6px; height: 26px; display: grid; place-items: center;
  letter-spacing: -.02em; white-space: nowrap;
}
.act.p4 .p { background: var(--red); }
.act h4 { margin: 0 0 5px; font-size: 14.5px; color: var(--ink); font-weight: 700; }
.act p { margin: 0; font-size: 13.3px; color: var(--ink2); line-height: 1.85; }

.endnote {
  margin: 36px 0 0; padding: 20px 24px; background: #F1EEE6; border-radius: 12px;
  font-size: 12.5px; color: var(--ink2); line-height: 1.9;
}
.endnote b { color: var(--ink); }

footer {
  max-width: 1180px; margin: 60px auto 0; padding: 30px 28px 50px;
  border-top: 1px solid var(--line); display: flex; justify-content: space-between;
  gap: 20px; flex-wrap: wrap; font-size: 12px; color: var(--ink3);
}

/* ---------- 灯箱 ---------- */
.lb {
  position: fixed; inset: 0; z-index: 200; background: rgba(12,18,26,.9);
  display: none; align-items: center; justify-content: center; padding: 34px;
  backdrop-filter: blur(3px);
}
.lb.on { display: flex; }
.lb img { max-width: 100%; max-height: 100%; border-radius: 8px; box-shadow: 0 24px 80px rgba(0,0,0,.5); }
.lb-close {
  position: absolute; top: 20px; right: 24px; width: 40px; height: 40px;
  border-radius: 50%; background: rgba(255,255,255,.14); color: #fff;
  border: none; font-size: 20px; cursor: pointer; line-height: 1;
}
.lb-close:hover { background: rgba(255,255,255,.26); }
.lb-cap { position: absolute; bottom: 18px; left: 0; right: 0; text-align: center; color: rgba(255,255,255,.66); font-size: 12.5px; }

/* ---------- 入场 ---------- */
/* 入场动画已取消：长报告以稳定可读为先，避免任何环境下内容不可见 */
.rv { opacity: 1; }

/* ---------- 响应式 ---------- */
@media (max-width: 1024px) {
  .stages { grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .stage-in::after { display: none; }
  .concl { grid-template-columns: 1fr; }
  .qcard-body { grid-template-columns: 1fr; }
  .qcard-shot { border-left: none; border-top: 1px solid var(--line2); }
  .qcard-shot .inner { position: static; max-width: 360px; margin: 0 auto; }
}
@media (max-width: 760px) {
  body { font-size: 14.5px; }
  .hero { padding: 60px 20px 50px; }
  .hero-stats { grid-template-columns: repeat(2, 1fr); }
  .sec { padding: 52px 20px 10px; }
  .nav-in { padding: 0 16px; }
  .nav-brand span { display: none; }
  .method, .rules, .rcases { grid-template-columns: 1fr; }
  .stages { grid-template-columns: repeat(2, 1fr); }
  .qfun { grid-template-columns: repeat(2, 1fr); }
  .case { grid-template-columns: 1fr; }
  .case-shot { max-width: 300px; }
  .dist-row { grid-template-columns: 120px 1fr 34px; gap: 8px; }
  .dist-row .nm { font-size: 11.5px; }
  .pcard-h { grid-template-columns: 44px 1fr 20px; gap: 10px; padding: 15px 16px; }
  .pcount { display: none; }
  .fn-row { grid-template-columns: 92px 1fr; }
  .fn-drop { display: none; }
  .tbl-bar input { margin-left: 0; width: 100%; }
  .act { grid-template-columns: 1fr; gap: 10px; }
  .act .p { width: 74px; }
}

@media print {
  .nav, .lb { display: none !important; }
  body { background: #fff; }
  .sec { page-break-inside: auto; padding-top: 30px; }
  .pcard .pbody { display: block !important; }

}

/* ---------- 专题：价值传递 ---------- */
.vhead { margin: 68px 0 8px; padding-top: 34px; border-top: 1px solid var(--line); }
.vhead .kick {
  display: inline-flex; align-items: center; gap: 9px;
  font-family: var(--mono); font-size: 11.5px; font-weight: 800;
  letter-spacing: .14em; color: var(--green);
}
.vhead .kick::before { content: ""; width: 24px; height: 2px; background: var(--green); display: inline-block; }
.vhead h3 { margin: 12px 0 12px; font-size: clamp(22px, 2.2vw, 28px); font-weight: 800; letter-spacing: -.01em; line-height: 1.35; color: var(--ink); }
.vhead .lead { font-size: 15px; color: var(--ink2); max-width: 800px; margin: 0; line-height: 1.95; }
.vhead .lead strong { color: var(--navy); font-weight: 700; }

.vgates { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 28px 0 30px; }
.vgate { background: var(--paper); border: 1px solid var(--line); border-radius: 14px; padding: 22px 20px; box-shadow: var(--shadow); }
.vgate b { font-family: var(--mono); font-size: 11px; font-weight: 700; letter-spacing: .1em; color: var(--green); }
.vgate h4 { margin: 8px 0 9px; font-size: 15.5px; font-weight: 800; color: var(--ink); line-height: 1.5; }
.vgate p { margin: 0; font-size: 13px; color: var(--ink2); line-height: 1.85; }

.qcard-tag {
  display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .06em;
  color: var(--green); background: var(--greenbg); border: 1px solid #CFE3DD;
  padding: 2px 9px; border-radius: 5px; margin-left: 8px; vertical-align: 3px;
}
.qblock.qnote { background: var(--amberbg); border-radius: 10px; padding: 14px 16px; }
.qblock.qnote .qlabel { color: var(--amber); }
.qblock.qnote p { color: #6B5320; font-size: 13px; }

.vwrong { margin-top: 30px; background: #F4F1E9; border: 1px solid #E0D9C8; border-radius: 14px; padding: 22px 24px; }
.vwrong h4 { margin: 0 0 10px; font-size: 14px; color: var(--navy); font-weight: 800; }
.vwrong ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.vwrong li { font-size: 13px; color: #4A4436; line-height: 1.8; padding-left: 18px; position: relative; }
.vwrong li::before { content: "×"; position: absolute; left: 0; top: 0; color: var(--red); font-weight: 800; }
.vwrong li b { color: var(--red); }
.vwrong .foot { margin: 14px 0 0; padding-top: 12px; border-top: 1px solid #E0D9C8; font-size: 13px; color: #4A4436; line-height: 1.85; }
.vwrong .foot b { color: var(--navy); }

@media (max-width: 900px) {
  .vgates { grid-template-columns: 1fr; }
}

/* 未截图的其余案例：一行一个 pill，避免长括号嵌套挤在一起 */
.rest-list { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 0; padding: 0; list-style: none; }
.rest-list li {
  font-size: 12.5px; color: var(--ink2); background: #F7F6F2;
  border: 1px solid var(--line); border-radius: 6px;
  padding: 3px 10px; line-height: 1.7;
}
.rest-list b {
  font-family: var(--mono); font-size: 11.5px; font-weight: 700;
  color: #77838F; margin-right: 7px;
}

.idnote {
  font-size: 11.5px; color: #7A7568; line-height: 1.7;
  background: #FAF7EE; border: 1px solid #EAE3D2; border-radius: 6px;
  padding: 4px 10px; margin-left: auto; max-width: 640px;
}
@media (max-width: 760px) { .idnote { margin-left: 0; max-width: 100%; } }
/* ---------- 顶部概要条：数据来源与依据（交付必填） ---------- */
.prov {
  background: #FBF9F4; border-bottom: 1px solid var(--line);
  font-family: var(--mono);
  font-size: 12.5px; line-height: 1.95; letter-spacing: .005em;
  color: #625D50;
}
.prov-in { max-width: 1180px; margin: 0 auto; padding: 10px 28px 11px; }
.prov p { margin: 0; overflow-wrap: anywhere; }
.prov p + p { margin-top: 3px; }
.prov .seg { display: inline; }
.prov .seg + .seg { margin-left: 24px; }
.prov .nb { white-space: nowrap; }
.prov em {
  font-style: normal; display: inline;
  font-size: 10.5px; letter-spacing: .14em; color: #8C8474; margin-right: 8px;
}

.prov b { color: var(--navy); font-weight: 700; }
.prov code {
  font-family: inherit; font-size: 11.5px; color: #7A4A2E;
  background: #F3EDDF; border: 1px solid #E6DCC6; border-radius: 3px;
  padding: 0 4px;
}
.prov a { color: #3F4E5E; text-decoration: none; border-bottom: 1px dashed #C6BEA9; }
.prov a + a { margin-left: 14px; }
.prov a:hover { color: var(--navy); border-bottom-color: var(--navy); }
@media (max-width: 860px) {
  .prov { font-size: 12px; }
  .prov-in { padding: 8px 18px; }
  .prov .seg { display: block; }
  .prov .seg + .seg { margin-left: 0; margin-top: 2px; }
}
@media print { .prov { background: #fff; } }

/* ── 重点标注：单独拎出来的几组，和统计批分开口径 ───────────────── */
.nav-links a.nav-focus::after {
  content: ""; display: inline-block; width: 5px; height: 5px; border-radius: 50%;
  background: var(--amber); margin-left: 5px; vertical-align: 2px;
}
.focus-bar {
  display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
  background: var(--amberbg); border: 1px solid #E6D5A8; border-left: 3px solid var(--amber);
  border-radius: 12px; padding: 13px 18px; margin: 0 0 26px;
}
.focus-bar b {
  font-size: 11.5px; font-weight: 800; letter-spacing: .1em;
  color: var(--amber); white-space: nowrap;
}
.focus-bar span { font-size: 13px; color: #6B5320; line-height: 1.75; }
.focus-bar span b { font-size: 13px; letter-spacing: 0; color: #5A4413; }

.fgrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 30px; }
.fcell {
  background: var(--paper); border: 1px solid var(--line); border-top: 3px solid var(--amber);
  border-radius: 12px; padding: 15px 16px 14px; box-shadow: var(--shadow);
}
.fcell em {
  font-style: normal; font-family: var(--mono); font-size: 10px; font-weight: 700;
  letter-spacing: .1em; color: var(--amber);
}
.fcell h4 { margin: 6px 0 3px; font-size: 16px; font-weight: 800; color: var(--ink); line-height: 1.4; }
.fcell .fwho { font-size: 11.5px; color: var(--ink3); margin: 0 0 8px; }
.fcell p { margin: 0; font-size: 12px; color: var(--ink2); line-height: 1.75; }

.qcard.focus { border-color: #E6D5A8; }
.qcard.focus .qcard-no { background: var(--amber); }
.qcard-tag.focus {
  color: var(--amber); background: var(--amberbg); border: 1px solid #E6D5A8;
  font-size: 11px; font-weight: 700; letter-spacing: .06em;
  padding: 2px 9px; border-radius: 5px; margin-left: 8px; vertical-align: 3px;
  display: inline-block;
}
.qblock.qnext {
  background: #EBF1F8; border-radius: 10px; padding: 14px 16px 15px;
  border-left: 3px solid var(--navy);
}
.qblock.qnext .qlabel { color: var(--navy); }
.qblock.qnext .qlabel::after { background: #D3E0EE; }
.qblock.qnext p { color: #22364D; font-size: 13.2px; }
.qblock.qnext ol { margin: 0; padding-left: 19px; }
.qblock.qnext li { font-size: 13.2px; color: #22364D; line-height: 1.85; margin-bottom: 7px; }
.qblock.qnext li:last-child { margin-bottom: 0; }
.qblock.qnext li b { color: var(--navy); }

/* 卡片只有一列文字时，别把右侧那 330px 空着 */
.qcard-body > .qcard-txt:only-child { grid-column: 1 / -1; }

@media (max-width: 1024px) { .fgrid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 640px) { .fgrid { grid-template-columns: 1fr; } }"""

ASSETS["manual.css"] = r"""/* 口径与范本（教材版）增量样式
   只做四件事：顶部三段图例、三项记分牌、卡号按项上色、速查表。
   style.css 里已有的东西一律不动——那份文件被 6 个页面共用。 */

/* ---------- 顶部三段图例 ---------- */
.stage3 {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
  margin: 0 0 34px;
}
.stage3 .st {
  position: relative;
  background: rgba(255,255,255,.055);
  border: 1px solid rgba(255,255,255,.13);
  border-left-width: 3px;
  border-radius: 12px;
  padding: 15px 17px 16px;
  min-width: 0;
}
.stage3 .st.s1 { border-left-color: #7FA9D4; }
.stage3 .st.s2 { border-left-color: #6FBFAF; }
.stage3 .st.s3 { border-left-color: #D8B45F; }
.stage3 .stn {
  position: absolute; top: 13px; right: 15px;
  font-size: 19px; line-height: 1; font-weight: 800;
  color: rgba(255,255,255,.2);
}
.stage3 .st b {
  display: block; font-size: 15.5px; font-weight: 800; letter-spacing: .04em;
  color: #fff; margin-bottom: 9px;
}
/* 「客户心里的问题」做成小标签，问题本身单独放大——三张卡等高，
   不必靠字重区分（600 在微软雅黑上是合成粗体，深色小字会糊） */
.stage3 .st .stk {
  display: block; font-size: 10.5px; line-height: 1.4;
  letter-spacing: .1em; color: rgba(255,255,255,.4); margin-bottom: 3px;
}
.stage3 .st p {
  margin: 0 0 10px; font-size: 15px; line-height: 1.45;
  color: #fff; font-weight: 400; letter-spacing: .01em;
}
.stage3 .stq {
  display: block; font-size: 12px; line-height: 1.72; color: rgba(255,255,255,.64);
  padding-top: 9px; border-top: 1px solid rgba(255,255,255,.1);
}

/* ---------- 三项记分牌 ---------- */
.mm {
  display: inline-block; vertical-align: 1px;
  margin-right: 6px; padding: 1px 9px 2px;
  border: 1px solid transparent; border-radius: 999px;
  font-size: 11.5px; font-weight: 700; line-height: 1.55;
  letter-spacing: .01em; white-space: nowrap;
  font-variant-numeric: tabular-nums;
  font-family: var(--mono);
}
.mm:last-child { margin-right: 0; }
.mm.k1 { background: #EDF1F7; color: #1F3A5F; border-color: #D7E0EC; }
.mm.k2 { background: var(--greenbg); color: var(--green); border-color: #D2E3DE; }
.mm.k3 { background: var(--amberbg); color: var(--amber); border-color: #EBDBB6; }
.mm.off { background: #F3F1EA; color: #9A9483; border-color: #E4DFD2; }

/* 卡号按项上色：三项全过=navy、出口=green、落点=amber
   放在 style.css 之后，才能盖掉 .qcard.focus .qcard-no 的琥珀色 */
.qcard.p1 .qcard-no { background: var(--navy); }
.qcard.p2 .qcard-no { background: var(--green); }
.qcard.p3 .qcard-no { background: var(--amber); }

/* ---------- 速查表 ---------- */
.mm-intro {
  margin: 30px 2px 10px; padding-left: 14px;
  border-left: 3px solid var(--navy);
}
.mm-intro h3 {
  margin: 0 0 5px; font-size: 15.5px; font-weight: 800; letter-spacing: .01em;
  color: var(--ink);
}
.mm-intro p {
  margin: 0; font-size: 13px; line-height: 1.75; color: var(--ink2);
}
.mm-intro p b { color: var(--ink); }

.mm-tblwrap { margin-top: 14px; }
/* 固定列宽：不固定的话「做对了什么」那一列会把前四列挤到竖排 */
.mm-tbl { table-layout: fixed; font-size: 13.2px; }
.mm-tbl th:nth-child(1) { width: 122px; }
.mm-tbl th:nth-child(2) { width: 88px; }
.mm-tbl th:nth-child(3) { width: 238px; }
.mm-tbl th:nth-child(4) { width: 170px; }
.mm-tbl th:nth-child(6) { width: 56px; }
.mm-tbl thead th { white-space: nowrap; }
.mm-tbl td { vertical-align: middle; padding-top: 10px; padding-bottom: 10px; }
.mm-tbl td.who { color: var(--ink2); white-space: nowrap; }
.mm-tbl td.no {
  font-family: var(--mono); font-size: 11.5px; color: var(--ink3);
  white-space: nowrap; text-align: right;
}
.mm-tbl td.mmcell { white-space: nowrap; }
.mm-tbl td.mmcell .mm { font-size: 10.5px; padding: 0 7px 1px; margin-right: 3px; }
.mm-tbl .qjump {
  color: var(--ink); text-decoration: none;
  display: inline-flex; align-items: center; gap: 6px;
  border-bottom: 1px solid transparent;
}
.mm-tbl .qjump b { font-weight: 800; }
.mm-tbl .qjump:hover { color: var(--navy); border-bottom-color: var(--navy); }
.mm-tbl tr.qt { transition: background .14s ease; }
.mm-tbl tr.qt:hover { background: #FBF9F4; }
.mm-tbl tr.qt.p1:hover { background: #F7F9FC; }
.mm-tbl tr.qt.p2:hover { background: #F6FAF8; }
.mm-tbl tr.qt.p3:hover { background: #FDFAF1; }
.mm-tbl .chip.fchip {
  background: var(--amber); color: #fff; font-size: 10px;
  padding: 0 5px; margin-left: 5px; font-weight: 700;
}

/* ---------- 整段聊天记录卡（M2）----------
   和主页面 .qcard-body 的「左文右图」不同：这里图是主体，通栏放在下面，
   文字四块按 2×2 排在上面。图按 780px 原宽显示（不缩放，字才清楚），
   外面套一个固定高度的窗口上下滚动。 */
.mcase-body {
  display: grid; grid-template-columns: 1fr 1fr; gap: 24px 34px;
  padding: 26px 30px 4px;
}
.mcase-body .qblock { min-width: 0; }
.mcase-body .qblock p { font-size: 13.5px; line-height: 1.9; color: #2C3644; }

.mcase-shot { margin: 16px 30px 30px; border-top: 1px dashed var(--line); padding-top: 18px; }
.shotbar { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.shotbar .sbt {
  font-size: 12.5px; font-weight: 800; letter-spacing: .05em; color: var(--ink);
}
.shotbar .sbd { font-size: 11.5px; color: var(--ink3); font-family: var(--mono); }
.shotopen {
  margin-left: 18px; font-size: 11.5px; color: var(--navy); text-decoration: none;
  border-bottom: 1px solid rgba(31,58,95,.3); white-space: nowrap;
}
.shotopen:hover { border-bottom-color: var(--navy); }

/* 窗口底色比图（#EDEDED）深一档，780 宽的图在里头才有边界感；
   不加这一档，图和窗口糊成一片，看不出「这里可以滚」。 */
.shotwin {
  max-height: 780px; overflow-y: auto; overscroll-behavior: contain;
  border: 1px solid #D9D5C9; border-radius: 12px; background: #E1DED6;
  box-shadow: inset 0 1px 4px rgba(20,30,45,.08);
}

/* 「展开全部」用 checkbox + 兄弟选择器，不引 JS（assets/app.js 是多页共用的模板，
   check.py 会逐字节比对，不能为了这个页面改它） */
.swchk { display: none; }
.swtoggle {
  margin-left: auto; font-size: 11.5px; color: var(--navy); cursor: pointer;
  border-bottom: 1px dashed rgba(31,58,95,.35); white-space: nowrap; user-select: none;
}
.swtoggle:hover { border-bottom-style: solid; }
.swtoggle .t2 { display: none; }
.swchk:checked ~ .shotbar .t1 { display: none; }
.swchk:checked ~ .shotbar .t2 { display: inline; }
.swchk:checked ~ .shotbar .swtoggle { margin-left: auto; }
.swchk:checked ~ .shotwin { max-height: none; }
.swchk:checked ~ .shotbar + .shotwin { box-shadow: none; }
/* 定宽 780 而不是 100%：图是按 780px 渲染的，拉宽就是放大插值，字会发虚。
   容器更窄时才退让。 */
.shotwin img {
  width: 780px; max-width: 100%; display: block; margin: 0 auto; cursor: zoom-in;
}
.mcase-shot .qshot-cap {
  text-align: left; margin-top: 9px; line-height: 1.7;
}
.mcase-shot .qshot-cap code {
  font-family: var(--mono); font-size: 10.8px; color: var(--ink2);
  background: #F1EFE8; padding: 1px 4px; border-radius: 4px;
}

/* 「可以直接抄的原话」：原话一行、用法一行，扫读时不用在句子里找重点 */
.mclist { margin: 0; padding: 0; list-style: none; display: grid; gap: 9px; }
.mclist li { font-size: 13.2px; line-height: 1.75; color: #2C3644; }
.mclist li b { display: block; font-weight: 700; color: var(--ink); }
.mclist li span { color: var(--ink2); font-size: 12.4px; }

/* 跳到卡片后，卡号闪一下，让人知道落在哪 */
.qcard:target { animation: mmflash 1.1s ease 1; }
@keyframes mmflash {
  0%, 36% { box-shadow: 0 0 0 3px rgba(31,58,95,.28), var(--shadow); }
  100% { box-shadow: var(--shadow); }
}

/* M1 那张三项定义表：第一列只有两个字，不给宽度会竖排 */
#m-rule table { table-layout: fixed; }
#m-rule table th:nth-child(1) { width: 78px; white-space: nowrap; }
#m-rule table th:nth-child(2) { width: 178px; }

@media (max-width: 900px) {
  .stage3 { grid-template-columns: 1fr; gap: 9px; }
  .mm-tbl { font-size: 12.4px; }
  .mcase-body { grid-template-columns: 1fr; gap: 20px; padding: 22px 18px 2px; }
  .mcase-shot { margin: 14px 18px 22px; }
  .shotwin { max-height: 560px; }
}"""

ASSETS["livechat.css"] = r"""/* 聊天记录「文字版」—— 把长图换成真文字
   原来那块是 <img> 长图：像素里的字选不中、复制不了。这里用 DOM 按同一套标注
   重排一遍，气泡、时间条、标注带、条首标签一个不少，但每个字都是真文本。

   只被「接通建联(可用于案例分享)」「价值传递(可用于案例分享)」两页引用。
   style.css / manual.css 是多页共用的模板，不动。 */

/* ---------- 图框：沿用 manual.css 的 .shotwin（边框、圆角、滚动、展开） ---------- */
.cclive .shotwin {
  background: #E1DED6;
  padding: 10px 0;
}
.cclive .shotwin .cl-chat {
  max-width: 780px;
  margin: 0 auto;
  background: #EDEDED;
  padding: 16px 16px 22px;
  border-radius: 8px;
}
@media (max-width: 820px) {
  .cclive .shotwin { padding: 0; }
  .cclive .shotwin .cl-chat { border-radius: 0; padding: 14px 10px 18px; }
}

/* ---------- 两版切换：要点版 / 完整版 ----------
   三段那页（价值传递）一块聊天记录给两版：要点版只留色条标过的几句，
   完整版是原文全量。同一时刻只露一版，用上面这行标签切。
   标签 sticky 吸在滚动区顶：完整版 40-74 条，滚到中间还得能切回来。 */
.cclive .cl-tabs {
  position: sticky; top: 0; z-index: 4;
  max-width: 780px; margin: 0 auto 8px;
  display: flex; justify-content: center; gap: 8px;
  padding: 7px 10px 9px;
  background: #E1DED6;
  box-shadow: 0 7px 10px -9px rgba(0, 0, 0, .45);
}
.cclive .cl-tab {
  font: inherit; font-size: 13px; line-height: 1;
  display: inline-flex; align-items: baseline;
  padding: 8px 15px 9px; border-radius: 999px; cursor: pointer;
  border: 1px solid rgba(31, 58, 95, .22);
  background: rgba(255, 255, 255, .8); color: #3F5675;
  transition: background .15s, color .15s, border-color .15s, box-shadow .15s;
}
.cclive .cl-tab b { font-weight: 700; font-variant-numeric: tabular-nums; margin: 0 2px 0 5px; }
.cclive .cl-tab:hover { background: #fff; }
.cclive .cl-tab.on {
  background: #1F3A5F; border-color: #1F3A5F; color: #fff;
  box-shadow: 0 1px 4px rgba(31, 58, 95, .28);
}
.cclive .cl-pane[hidden] { display: none !important; }

/* 工具栏：标题与灰字在左，复制按钮 + 展开 + 原图链接靠右。
   .shotopen 原样式（manual.css）带 margin-left:18px，会贴在灰字后面；
   这里用 order 把它排到按钮之后，让右边四个控件连成一组。 */
.cclive .shotbar { align-items: center; }
.cclive .cl-tools {
  order: 2;
  margin-left: auto;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.cclive .shotbar .shotopen { order: 3; margin-left: 4px; }
.cclive .cl-tools .swtoggle { margin-left: 2px; }
.lcb {
  font: inherit; font-size: 11.5px; line-height: 1; padding: 6px 13px;
  border-radius: 999px; cursor: pointer; white-space: nowrap;
  border: 1px solid rgba(31,58,95,.26); background: #fff; color: var(--navy, #1F3A5F);
  transition: background .15s, border-color .15s, color .15s;
}
.lcb:hover { background: #EEF2F8; }
.lcb1 { background: #1F3A5F; border-color: #1F3A5F; color: #fff; }
.lcb1:hover { background: #162C4A; border-color: #162C4A; }
.lcb.ok { background: #EDF8F2; border-color: #1E7A52; color: #1E7A52; }
.lcb1.ok { background: #1E7A52; border-color: #1E7A52; color: #fff; }

/* ---------- 聊天记录本体 ---------- */
.cl-chat {
  font-family: "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "Segoe UI", sans-serif;
  color: #111;
  text-align: left;
  -webkit-font-smoothing: antialiased;
}
.cl-title {
  font-size: 20px; font-weight: 700; text-align: center;
  line-height: 1.4; color: #111; margin: 0 0 4px;
}
.cl-sub {
  font-size: 12.5px; line-height: 1.7; text-align: center;
  color: #777; margin: 0 0 10px;
}
.cl-legend {
  display: flex; flex-wrap: wrap; justify-content: center; gap: 8px 12px;
  margin: 0 0 14px;
}
.cl-lg {
  display: inline-flex; align-items: center; gap: 6px;
  background: #fff; border: 1px solid #DCDCDC; border-radius: 6px;
  padding: 3px 9px 4px; font-size: 12.5px; line-height: 1.4;
}
.cl-lg i { width: 11px; height: 11px; border-radius: 2px; flex: 0 0 auto; }
.cl-lg b { font-weight: 700; }
.cl-lg em { color: #666; font-style: normal; }

/* 标注说明带：整条横贯，左边一条色杠（与长图一致） */
.cl-band {
  border-left: 4px solid #999;
  border-radius: 2px;
  padding: 3px 10px 5px;
  margin: 12px 0 8px;
  font-size: 14.5px; font-weight: 600; line-height: 1.55;
}
.cl-time { text-align: center; margin: 10px 0 8px; }
.cl-time span {
  display: inline-block; background: #DADADA; color: #666;
  font-size: 12.5px; line-height: 1.5; padding: 2px 10px 3px; border-radius: 6px;
  font-variant-numeric: tabular-nums;
}
.cl-gap {
  display: flex; align-items: center; gap: 10px;
  margin: 12px 0; font-size: 12.5px; color: #999;
}
.cl-gap i { flex: 1 1 auto; height: 1px; background: #CCCCCC; }
.cl-gap span { flex: 0 0 auto; }

/* 一条消息：标签 → 名字 → 气泡，销售靠右、客户靠左 */
.cl-msg { display: flex; flex-direction: column; margin: 0 0 10px; }
.cl-msg.s { align-items: flex-end; }
.cl-msg.c { align-items: flex-start; }
.cl-chips { display: flex; gap: 4px; margin: 0 0 5px; }
.cl-chip {
  color: #fff; font-size: 12px; line-height: 1.35;
  padding: 2px 7px 3px; border-radius: 5px; font-weight: 700;
  white-space: nowrap;
}
.cl-nm {
  font-size: 12.5px; line-height: 1.5; color: #888;
  margin: 0 6px 3px;
}
.cl-bub {
  position: relative;
  max-width: 420px;
  padding: 7px 13px 8px;
  border-radius: 8px;
  font-size: 18px; line-height: 26px;
  word-break: break-word; overflow-wrap: anywhere;
  user-select: text;
  /* 色条是绝对定位贴在气泡里的，溢出裁掉才能跟圆角咬合，否则两个方角会露出气泡 */
  overflow: hidden;
}
.cl-msg.s .cl-bub { background: #95EC69; padding-right: 15px; }
.cl-msg.c .cl-bub { background: #fff; border: 1px solid #DDD; padding-left: 15px; }
.cl-msg.s .cl-bar { right: 2px; }
.cl-msg.c .cl-bar { left: 2px; }
.cl-bar {
  position: absolute; top: 4px; bottom: 4px; width: 4px;
  border-radius: 2px; pointer-events: none;
}
.cl-txt { display: inline; }

/* 收起时底边渐隐：窗口是滚动区，最后一个气泡常被硬切一半，看着像排版坏了。
   做法是窗口外面盖一条绝对定位的渐变（不能挂在滚动容器里，那样会跟着内容滚走），
   滚到底 / 点「展开全部」时由 livechat.js 加 .at-end 把渐变撤掉——
   静态渐变会把最后一行永远压住。 */
.cclive .cl-wrap { position: relative; }
/* manual.css 里「展开全部」是靠 .swchk:checked ~ .shotwin 生效的，
   这里 .shotwin 被 .cl-wrap 包了一层，兄弟关系断了，max-height 收不回来，
   于是补一条：跨过 .cl-wrap 仍然生效。 */
.cclive .swchk:checked ~ .cl-wrap .shotwin { max-height: none; box-shadow: none; }
.cclive .cl-fade {
  position: absolute; left: 1px; right: 1px; bottom: 1px; height: 28px;
  background: linear-gradient(rgba(237,237,237,0), #EDEDED 78%);
  border-radius: 0 0 12px 12px;
  pointer-events: none;
  transition: opacity .18s;
}
.cclive .cl-wrap.at-end .cl-fade { opacity: 0; }

/* 结论条：与长图上那块黄底一致 */
.cl-note {
  background: #FFF3D6; border-radius: 6px;
  padding: 9px 12px 10px; margin: 14px 0 2px;
  font-size: 13.5px; line-height: 1.75; color: #B45309;
}

@media (max-width: 820px) {
  .cl-title { font-size: 17px; }
  .cclive .cl-tabs { gap: 6px; padding: 6px 8px 8px; }
  .cclive .cl-tab { font-size: 12px; padding: 7px 11px 8px; }
  .cclive .cl-tab b { margin: 0 1px 0 4px; }
  .cl-bub { font-size: 16px; line-height: 24px; max-width: 84%; }
  .cl-band { font-size: 13px; }
  /* 窄屏：链接挪到标题行右端（order 1），按钮独占下一行（order 2 + 满宽），
     不要三段式各占一行。这条必须排在基础 order 规则之后才生效。 */
  .cclive .shotbar .shotopen { order: 1; margin-left: auto; }
  .cclive .cl-tools { margin-left: 0; width: 100%; }
}"""

ASSETS["connect.css"] = r"""/* 接通建联（阶段 1 教材页）增量样式
   复用 manual.css 的记分牌 / 长图窗 / 四块分析 / 速查表，
   这里只补四件这一步独有的：四要件卡、四色记分牌、判据表、禁区列表。 */

/* ---------- 顶部四要件（深色 hero 内） ---------- */
.stage4 {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
  margin: 0 0 32px;
}
.stage4 .st {
  position: relative;
  background: rgba(255,255,255,.055);
  border: 1px solid rgba(255,255,255,.13);
  border-left-width: 3px;
  border-radius: 12px;
  padding: 14px 15px 15px;
  min-width: 0;
}
.stage4 .st.s1 { border-left-color: #7FA9D4; }
.stage4 .st.s2 { border-left-color: #A78BFA; }
.stage4 .st.s3 { border-left-color: #6FBFAF; }
.stage4 .st.s4 { border-left-color: #D8B45F; }
.stage4 .stn {
  position: absolute; top: 12px; right: 13px;
  font-size: 18px; line-height: 1; font-weight: 800;
  color: rgba(255,255,255,.2);
}
.stage4 .st b {
  display: block; font-size: 15px; font-weight: 800; letter-spacing: .04em;
  color: #fff; margin-bottom: 8px;
}
.stage4 .st .stk {
  display: block; font-size: 10px; line-height: 1.4;
  letter-spacing: .09em; color: rgba(255,255,255,.4); margin-bottom: 3px;
}
.stage4 .st p {
  margin: 0 0 9px; font-size: 14.5px; line-height: 1.45;
  color: #fff; font-weight: 400; letter-spacing: .01em;
}
.stage4 .stq {
  display: block; font-size: 11.5px; line-height: 1.65; color: rgba(255,255,255,.62);
  padding-top: 8px; border-top: 1px solid rgba(255,255,255,.1);
}

/* ---------- 四色记分牌（与长图四色同一套） ---------- */
.mm.c1 { background: #E8EFFF; color: #2563EB; border-color: #CFDCFA; }
.mm.c2 { background: #F2EBFE; color: #7C3AED; border-color: #E1D3FB; }
.mm.c3 { background: var(--greenbg); color: var(--green); border-color: #D2E3DE; }
.mm.c4 { background: var(--amberbg); color: var(--amber); border-color: #EBDBB6; }

/* ---------- 判据表 ---------- */
.cc-tblwrap { margin-top: 18px; }
.cc-tbl { table-layout: fixed; font-size: 13px; }
.cc-tbl th:nth-child(1) { width: 40px; }
.cc-tbl th:nth-child(2) { width: 84px; }
.cc-tbl th:nth-child(3) { width: 236px; }
.cc-tbl th:nth-child(4) { width: 236px; }
.cc-tbl thead th { white-space: nowrap; }
.cc-tbl td { vertical-align: top; padding-top: 11px; padding-bottom: 11px; line-height: 1.7; }
.cc-tbl td.cno {
  font-size: 15px; font-weight: 800; color: var(--navy);
  white-space: nowrap; text-align: center;
}
.cc-tbl td.cno2 { color: var(--ink3); font-size: 12.4px; }
.cc-tbl td.chit { color: #2C3644; }
.cc-tbl tbody tr:nth-child(4) { background: #FDFBF5; }
.cc-tbl tbody tr:nth-child(4) td.cno { color: var(--amber); }

/* ---------- 三条说明 ---------- */
.cc-notes {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
  margin: 26px 0 6px;
}
.cc-notes .cn {
  background: #FBF9F4; border: 1px solid var(--line); border-radius: 12px;
  padding: 16px 18px 17px;
}
.cc-notes .cn h4 {
  margin: 0 0 8px; font-size: 13.5px; font-weight: 800; letter-spacing: .02em;
  color: var(--ink);
}
.cc-notes .cn h4::before {
  content: ""; display: inline-block; width: 3px; height: 12px;
  background: var(--navy); border-radius: 2px; margin-right: 8px; vertical-align: -1px;
}
.cc-notes .cn p {
  margin: 0 0 8px; font-size: 12.6px; line-height: 1.82; color: var(--ink2);
}
.cc-notes .cn p:last-child { margin-bottom: 0; }
.cc-notes .cn p b { color: var(--ink); }

/* ---------- 分区（两种线索 / 禁区 / 沉默） ---------- */
.cc-part {
  margin: 34px 2px 0; padding-left: 16px;
  border-left: 3px solid var(--navy);
}
.cc-part h3 {
  margin: 0 0 7px; font-size: 16px; font-weight: 800; letter-spacing: .01em;
  color: var(--ink);
}
.cc-part > p {
  margin: 0 0 14px; font-size: 13.2px; line-height: 1.85; color: var(--ink2);
}
.cc-part > p b { color: var(--ink); }

/* 两类线索对照 */
.cc-lead2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.cc-lead2 .l2 {
  border: 1px solid var(--line); border-radius: 12px;
  padding: 15px 17px 16px; background: #fff;
}
.cc-lead2 .l2.l2b { background: #FBF9F4; border-color: #E7E1D2; }
.cc-lead2 .l2t {
  display: inline-block; margin-bottom: 10px; padding: 2px 10px 3px;
  border-radius: 999px; background: #DCE6F4; color: #1B3A63;
  font-size: 11.5px; font-weight: 700; letter-spacing: .05em;
}
.cc-lead2 .l2b .l2t { background: #F2E3C4; color: #7A4A08; }
.cc-lead2 .l2q {
  margin: 0 0 9px; padding: 9px 12px;
  background: #F7F6F2; border-left: 2px solid #D9D4C6; border-radius: 0 6px 6px 0;
  font-size: 12.4px; line-height: 1.8; color: #3A4450;
}
.cc-lead2 .l2q:last-of-type { margin-bottom: 10px; }
.cc-lead2 .l2n {
  margin: 0; font-size: 12px; line-height: 1.8; color: var(--ink3);
}
.cc-lead2 .l2n b { color: var(--ink2); }

/* 禁区列表 */
.cc-ban {
  margin: 0 0 12px; padding: 0; list-style: none;
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px 14px;
}
.cc-ban li {
  position: relative; padding: 8px 12px 8px 30px;
  background: #FDF3F0; border: 1px solid #F2DAD3; border-radius: 8px;
  font-size: 12.8px; line-height: 1.6; color: #8A3A28;
}
.cc-ban li::before {
  content: "✕"; position: absolute; left: 11px; top: 8px;
  font-size: 11px; font-weight: 800; color: #C0563C;
}
.cc-ban li.b2 {
  background: #FDF3F0; border-color: #F2DAD3; color: #8A3A28;
}
.cc-ban li.b2::before { content: "⚠"; color: #C0563C; }
.cc-fine { font-size: 12.2px; line-height: 1.8; color: var(--ink3); margin: 0; }
.cc-fine b { color: var(--ink2); }

/* C1 区的 h2 在删减时被去掉了，section 头只剩一个「C1 / 口径」小标签。
   .sec-head 的 34px 下边距再叠上 .cc-part 的 34px 上边距，中间会空出 120px，
   看着像漏了一段。这里把 section 头的下边距收掉。 */
#c-rule .sec-head { margin-bottom: 6px; }

/* 代称清单（② 补充：客户不报名字时用代称顶） */
.cc-alias {
  margin: 0 0 14px; padding: 0; list-style: none;
  display: flex; flex-wrap: wrap; gap: 8px;
}
.cc-alias li {
  padding: 5px 15px 6px; border-radius: 999px;
  background: #F2EBFE; border: 1px solid #E1D3FB; color: #7C3AED;
  font-size: 13px; font-weight: 700; letter-spacing: .02em;
}
/* 算 / 不算 两栏对照 */
.cc-vs { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
.cc-vs .vs { border: 1px solid; border-radius: 10px; padding: 11px 14px 12px; }
.cc-vs .vs p { margin: 0; font-size: 12.2px; line-height: 1.8; }
.cc-vs .vs p b { color: var(--ink); }
.cc-vs .vst {
  display: inline-block; margin-bottom: 6px; padding: 1px 9px 2px;
  border-radius: 999px; font-size: 11px; font-weight: 800; letter-spacing: .06em;
}
.cc-vs .vs-y { background: #F1FAF6; border-color: #D2E3DE; }
.cc-vs .vs-y .vst { background: #D8EFE6; color: #0B7A56; }
.cc-vs .vs-y p { color: #2C4A40; }
.cc-vs .vs-n { background: #FDF3F0; border-color: #F2DAD3; }
.cc-vs .vs-n .vst { background: #F7DDD5; color: #8A3A28; }
.cc-vs .vs-n p { color: #6E3C2F; }

/* ---------- 速查表（一行） ---------- */
.cc-quick th:nth-child(1) { width: 120px; }
.cc-quick th:nth-child(2) { width: 90px; }
.cc-quick th:nth-child(3) { width: 300px; }
.cc-quick th:nth-child(4) { width: 300px; }
.cc-quick td.mmcell .mm { font-size: 10.5px; }

/* ---------- 卡片 ---------- */
.cc-case .qcard-meta { line-height: 2; }
/* 「可以直接抄的原话」比左栏短，默认会被 grid 拉成等高，框里空一大片。
   这一块本来就该按内容高度收口。 */
.cc-case .qreuse { align-self: start; }

/* footer 的 .eyebrow 是给深色 hero 写的一套（白字），页脚是浅底，直接套会看不见。
   style.css 被 6 个页面共用、check.py 逐字节比对，不能动，这里局部覆盖。 */
.foot .eyebrow { color: var(--ink3); margin-bottom: 9px; letter-spacing: .2em; }
.foot .eyebrow::before { background: var(--line); }

/* ---------- 口径整体折叠：一到页面只看得到聊天记录 ---------- */
/* 首屏只剩标题 + 一条折叠条 + 聊天记录。判据卡、两种线索、代称、禁区全在
   <details> 里，点开才占位；不用 JS 也能开合，file:// 下照样工作。 */
.hero-c { padding: 34px 28px 28px; }
.hero-c h1 { margin-bottom: 12px; font-size: clamp(30px, 3.6vw, 44px); }
.hero-c .stage4 { margin-bottom: 22px; }
.hero-c .sub:empty { display: none; }
.hero-c .hero-meta { margin-top: 20px; padding-top: 16px; }

.cc-fold {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--paper); box-shadow: var(--shadow);
  overflow: hidden;
}
.cc-fold-sum {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 17px 22px; cursor: pointer; list-style: none;
  border-left: 3px solid var(--navy); user-select: none;
}
.cc-fold-sum::-webkit-details-marker { display: none; }
.cc-fold-sum::marker { content: ""; }
.cc-fold-sum:hover { background: #FBFAF7; }
.cc-fold[open] > .cc-fold-sum { background: #FBFAF7; border-bottom: 1px solid var(--line2); }
.ccf-no {
  font-family: var(--mono); font-size: 11.5px; letter-spacing: .16em; color: var(--ink3);
}
.ccf-t { font-size: 15.5px; font-weight: 800; letter-spacing: .01em; color: var(--ink); }
.ccf-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.ccf-chips b {
  font-size: 11.5px; font-weight: 600; line-height: 1;
  padding: 5px 9px 6px; border-radius: 999px;
  background: #F4F1EA; border: 1px solid var(--line); color: var(--ink2);
}
.ccf-act { margin-left: auto; white-space: nowrap; font-size: 12.5px; font-weight: 700; color: var(--navy); }
.ccf-act .t2 { display: none; }
.cc-fold[open] .ccf-act .t1 { display: none; }
.cc-fold[open] .ccf-act .t2 { display: inline; }

.cc-fold-body { padding: 2px 22px 24px; }
/* 折进去的第一块自己要留一点上边距，否则贴着折叠条的分隔线 */
.cc-fold-body > .cc-part:first-child { margin-top: 16px; }

/* 折叠后 C1 只剩一条，原来的 76px 上边距会顶出一大块空白。
   把 C1 收上去、C2 拉近，聊天记录才不会掉到首屏外面。 */
#c-rule { padding-top: 18px; padding-bottom: 2px; }
#c-good { padding-top: 22px; }
/* C2 只有一个章节、下面就是聊天卡片，标题不必占两行：编号和标题并排放，
   省下的四十来像素刚好让聊天卡片露出首屏。 */
#c-good .sec-head {
  display: flex; align-items: baseline; gap: 12px;
  margin-bottom: 12px;
}
#c-good .sec-no { margin-bottom: 0; }
#c-good .sec-head h2 { font-size: 20px; margin: 0; letter-spacing: .01em; }

@media (max-width: 1100px) {
  .stage4 { grid-template-columns: 1fr 1fr; }
  .cc-notes { grid-template-columns: 1fr; }
}
@media (max-width: 900px) {
  .stage4 { grid-template-columns: 1fr; gap: 9px; }
  .cc-tbl { font-size: 12.2px; }
  .cc-lead2, .cc-ban, .cc-vs { grid-template-columns: 1fr; }
  .cc-part { padding-left: 12px; }
  .cc-fold-sum { padding: 14px 16px; gap: 8px; }
  .ccf-t { font-size: 14.5px; }
  .ccf-act { margin-left: auto; }
  .cc-fold-body { padding: 0 14px 18px; }
  #c-rule { padding-top: 24px; }
  #c-good { padding-top: 34px; }
}

/* 手机上「一进来就看到聊天记录」也要成立：标题压短、折叠条的说明标签收掉，
   首屏才不会全被页头吃掉。 */
@media (max-width: 600px) {
  .hero-c { padding: 26px 18px 24px; }
  .hero-c h1 { font-size: 26px; margin-bottom: 10px; }
  .hero-c .hero-meta { margin-top: 14px; padding-top: 12px; }
  .cc-fold-sum { padding: 13px 14px; row-gap: 6px; }
  .ccf-chips { display: none; }
  .ccf-act { font-size: 12px; }
  /* 四张判据卡在手机上一列排会把聊天记录挤到两屏之后，改两列、字小一号 */
  .hero-c .stage4 { grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
  .hero-c .stage4 .st { padding: 11px 11px 12px; }
  .hero-c .stage4 .st b { font-size: 13.5px; margin-bottom: 6px; }
  .hero-c .stage4 .st p { font-size: 13px; margin-bottom: 7px; }
  .hero-c .stage4 .stq { font-size: 10.5px; line-height: 1.55; padding-top: 6px; }
  .hero-c .stage4 .stn { font-size: 14px; top: 9px; right: 9px; }
}"""

ASSETS["kit.css"] = r"""/* kit.css —— 套件自己补的一点点样式，不改动 style.css 原有规则。 */

/* 还没做的阶段：灰字 + 「暂不开放」小标，点不动，避免 href="" 点了重载 */
.nav-links .nav-off {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 13.5px;
  color: #A8A396;
  white-space: nowrap;
  cursor: default;
  user-select: none;
}
.nav-links .nav-off em {
  font-style: normal;
  font-size: 10.5px;
  line-height: 1;
  padding: 3px 5px;
  border: 1px solid #DED9CC;
  border-radius: 999px;
  color: #B3AEA1;
  letter-spacing: 0;
}

/* 窄屏：六项塞不下，横向能滑，右侧给一点渐隐提示还有东西 */
@media (max-width: 760px) {
  .nav-links {
    -webkit-mask-image: linear-gradient(90deg, #000 calc(100% - 28px), transparent);
    mask-image: linear-gradient(90deg, #000 calc(100% - 28px), transparent);
  }
}"""

ASSETS["livechat.js"] = r"""/* 聊天记录文字版 · 复制
   长图里的字是像素，选不中；这一块是真 DOM，所以两件事要做：
     1. 拖选 —— 不用写代码，别拦着就行（不设 user-select:none，不绑 data-zoom 灯箱）
     2. 一键带走 —— 拼成「说话人：正文　〔①②〕」的纯文本进剪贴板

   报告是双击本地打开（file://），非安全上下文拿不到 navigator.clipboard，
   必须留 textarea + execCommand 兜底，再失败就自动选中提示 Ctrl+C。
   不引第三方库，不改 assets/app.js（多页共用、check.py 逐字节比对）。 */
(function () {
  'use strict';

  var CIRC = ['①', '②', '③', '④'];

  function execCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0;';
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    var okk = false;
    try { okk = document.execCommand('copy'); } catch (e) { okk = false; }
    document.body.removeChild(ta);
    return okk;
  }

  function flash(btn, txt, cls) {
    var orig = btn.getAttribute('data-orig') || btn.textContent;
    btn.setAttribute('data-orig', orig);
    btn.textContent = txt;
    if (cls) btn.classList.add(cls);
    clearTimeout(btn._t);
    btn._t = setTimeout(function () {
      btn.textContent = orig;
      if (cls) btn.classList.remove(cls);
    }, 2000);
  }

  function crisp(k) {
    var out = '';
    for (var i = 0; i < k.length; i++) {
      var n = parseInt(k.charAt(i), 10);
      out += (n >= 1 && n <= 4) ? CIRC[n - 1] : k.charAt(i);
    }
    return out;
  }

  /* 拼纯文本：只取原文与说话人，标注带（解释性文字）不混进来，
     否则粘出去会插在两句对话中间，读起来像另一个人说的话。
     要点版（data-cc-plain="1"）连条尾的〔②〕也不加 —— 那一版是给销售
     照着念的，正文里多一个括号反而碍事，标号只在网页上看。 */
  function build(box) {
    var out = [];
    var plain = box.getAttribute('data-cc-plain') === '1';
    var head = box.getAttribute('data-cc-head');
    if (head) out.push(head.replace(/&amp;/g, '&').replace(/&quot;/g, '"'));

    var rows = box.querySelectorAll('.cl-body > *');
    [].forEach.call(rows, function (el) {
      if (el.classList.contains('cl-time')) {
        var t = el.textContent.trim();
        var sep = '—— ' + t + ' ——';
        /* 同一天连着出现两次时间条（说明带把一个上午切成几段）时只留一条 */
        if (t && out[out.length - 1] !== sep) { out.push(''); out.push(sep); }
      } else if (el.classList.contains('cl-msg')) {
        var x = el.querySelector('.cl-txt');
        if (!x) return;
        var ks = crisp(el.getAttribute('data-k') || '');
        out.push((el.getAttribute('data-who') || '') + '：' + x.textContent +
                 (!plain && ks ? '　〔' + ks + '〕' : ''));
      } else if (el.classList.contains('cl-note')) {
        out.push('');
        out.push(el.textContent.trim());
      } else if (el.classList.contains('cl-gap')) {
        out.push('');
        out.push('（' + el.textContent.trim() + '）');
      }
    });
    return out.join('\n');
  }

  /* 自检脚本用它验证「点复制拿到的 == 页面上印的原文」 */
  window.clBuildText = function (el) { return build(el); };

  function selectBody(box) {
    var body = box.querySelector('.cl-body');
    if (!body) return false;
    try {
      var r = document.createRange();
      r.selectNodeContents(body);
      var s = window.getSelection();
      s.removeAllRanges();
      s.addRange(r);
      return true;
    } catch (e) { return false; }
  }

  /* 一页两版时按钮没有固定目标：点「复制要点」要拿当前露出来的那一版。
     data-lcgrp 记着这一组，谁没 hidden 就是谁；没有 lcgrp 的（接通建联那块）照旧按 id 找。 */
  function boxOf(btn, attr) {
    var g = btn.getAttribute('data-lcgrp');
    if (g) {
      var panes = document.querySelectorAll('[data-clgrp="' + g + '"].cl-pane');
      for (var i = 0; i < panes.length; i++) {
        if (!panes[i].hidden) return panes[i];
      }
    }
    return document.getElementById(btn.getAttribute(attr));
  }

  [].forEach.call(document.querySelectorAll('[data-lc]'), function (btn) {
    btn.addEventListener('click', function () {
      var box = boxOf(btn, 'data-lc');
      if (!box) return;
      var text = build(box);
      if (!text) return;
      var n = 0, lines = text.split('\n');
      for (var i = 0; i < lines.length; i++) if (lines[i] && lines[i].indexOf('：') > 0) n++;
      function fail() {
        if (selectBody(box)) flash(btn, '已选中 · 按 Ctrl+C');
        else flash(btn, '复制失败，请拖选');
      }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function () {
          flash(btn, '已复制 ' + n + ' 条 ✓', 'ok');
        }, function () {
          if (execCopy(text)) flash(btn, '已复制 ' + n + ' 条 ✓', 'ok');
          else fail();
        });
      } else if (execCopy(text)) {
        flash(btn, '已复制 ' + n + ' 条 ✓', 'ok');
      } else {
        fail();
      }
    });
  });

  [].forEach.call(document.querySelectorAll('[data-lcsel]'), function (btn) {
    btn.addEventListener('click', function () {
      var box = boxOf(btn, 'data-lcsel');
      if (!box) return;
      if (selectBody(box)) flash(btn, '已选中 · 按 Ctrl+C', 'ok');
      else flash(btn, '选中失败');
    });
  });

  /* 要点版 / 完整版切换：一组两个 pane，同时只露一个。
     切完要滚回顶部、重算底边渐隐 —— 否则从 40 条的完整版切到 8 条的要点版，
     滚动位置还停在半路，看起来像一片空白。工具栏那个复制按钮的文字也跟着换：
     在要点版上写着「复制全文」，粘出来却只有 8 条，会让人以为漏了。 */
  [].forEach.call(document.querySelectorAll('.cl-tabs'), function (tabs) {
    var btns = [].slice.call(tabs.querySelectorAll('.cl-tab'));
    var win = tabs.parentNode;
    if (!win) return;
    var wrap = win.parentNode;
    var tools = wrap && wrap.parentNode
      ? wrap.parentNode.querySelector('.cl-tools') : null;
    var cp = tools ? tools.querySelector('[data-lcgrp]') : null;

    function show(btn) {
      var id = btn.getAttribute('data-pane');
      var grp = btn.getAttribute('data-clgrp');
      var slim = /k$/.test(id);
      [].forEach.call(document.querySelectorAll('[data-clgrp="' + grp + '"].cl-pane'),
        function (p) { p.hidden = (p.id !== id); });
      btns.forEach(function (b) { b.classList.toggle('on', b === btn); });
      win.scrollTop = 0;
      if (cp) {
        var lbl = cp.getAttribute(slim ? 'data-lbl-slim' : 'data-lbl-full');
        if (lbl) {
          clearTimeout(cp._t);
          cp.classList.remove('ok');
          cp.textContent = lbl;
          cp.removeAttribute('data-orig');
        }
      }
      if (typeof win._clUpd === 'function') setTimeout(win._clUpd, 20);
    }

    btns.forEach(function (b) {
      b.addEventListener('click', function () { if (!b.classList.contains('on')) show(b); });
    });
  });

  /* 底边渐隐：收起时窗口能滚，最后一个气泡会被硬切，用一条渐变压住；
     滚到底（含「展开全部」后不再有滚动）就把渐变撤掉，否则最后一行永远看不清。 */
  [].forEach.call(document.querySelectorAll('.cclive .shotwin'), function (win) {
    var wrap = win.parentNode;
    if (!wrap || !/cl-wrap/.test(wrap.className)) return;
    function upd() {
      var atEnd = win.scrollTop + win.clientHeight >= win.scrollHeight - 6;
      wrap.classList.toggle('at-end', atEnd);
    }
    /* 切版之后内容高度变了，得让切换那一段能把它叫起来重算一次 */
    win._clUpd = upd;
    win.addEventListener('scroll', upd, { passive: true });
    window.addEventListener('resize', upd);
    var cb = wrap.parentNode.querySelector('.swchk');
    if (cb) cb.addEventListener('change', function () { setTimeout(upd, 30); });
    upd();
  });
})();"""


NAV = json.loads(r"""{
 "说明": "六个阶段的主干导航。href 换成实际文件名即可；off=true 的只显示灰字「暂不开放」，点不动。",
 "items": [
  {
   "label": "接通建联",
   "key": "connect",
   "href": "接通建联(可用于案例分享).html"
  },
  {
   "label": "定级探需",
   "key": "probe",
   "href": "定级探需(可用于案例分享).html"
  },
  {
   "label": "价值传递",
   "key": "value",
   "href": "价值传递(可用于案例分享).html"
  },
  {
   "label": "方案报价",
   "key": "quote",
   "href": "方案报价(可用于案例分享).html"
  },
  {
   "label": "异议处理",
   "off": true
  },
  {
   "label": "逼单收口",
   "off": true
  }
 ]
}""")

DEMO = json.loads(r"""{
 "single": {
  "kind": "connect",
  "out": "接通建联(可用于案例分享).html",
  "title": "接通建联｜体德智训 · 阶段 1",
  "desc": "接通建联教材版：四要件怎么判（自我介绍 / 称呼客户 / 说明来意 / 客户回应）+ 一组从头看到尾的原文案例，聊天记录整段标色，逐字可查。",
  "brand": "体德智训 · 接通建联",
  "key": "connect",
  "nav_name": "接通建联",
  "hero": {
   "eyebrow": "Stage 1 · 接通建联",
   "h1": [
    "第一次接触",
    "<em>四件事做完才算接通</em>"
   ],
   "cards": [
    {
     "no": "①",
     "name": "自我介绍",
     "kicker": "判销售的行动",
     "lead": "我是谁",
     "note": "姓名或称呼 + 身份来路，能被验证"
    },
    {
     "no": "②",
     "name": "称呼客户",
     "kicker": "判销售的行动",
     "lead": "怎么叫他",
     "note": "说了姓，下一句就用上；没说用代称顶"
    },
    {
     "no": "③",
     "name": "说明来意",
     "kicker": "判销售的行动",
     "lead": "谈什么",
     "note": "接住线索里已有的信息，不重问一遍"
    },
    {
     "no": "④",
     "name": "客户回应",
     "kicker": "判客户的动作",
     "lead": "他有没有接",
     "note": "给信息、提问题、确认到具体点"
    }
   ],
   "meta": [
    "口径逐字来自两份招生培训文档，标了 [原文] 的不改动一个字",
    "聊天记录整段可查 · 口径细则见下方折叠区"
   ]
  },
  "stages": [
   {
    "no": 1,
    "mark": "①",
    "name": "自我介绍",
    "chip": "①",
    "color": "#2563EB",
    "bandbg": "#E8EFFF",
    "legend": ""
   },
   {
    "no": 2,
    "mark": "②",
    "name": "称呼客户",
    "chip": "②",
    "color": "#7C3AED",
    "bandbg": "#F2EBFE",
    "legend": ""
   },
   {
    "no": 3,
    "mark": "③",
    "name": "说明来意",
    "chip": "③",
    "color": "#0E9F6E",
    "bandbg": "#E6F9F1",
    "legend": ""
   },
   {
    "no": 4,
    "mark": "④",
    "name": "客户回应",
    "chip": "④",
    "color": "#D97706",
    "bandbg": "#FFF4DF",
    "legend": ""
   }
  ],
  "sec": {
   "no": "第 2 块 / 做对的",
   "h": "参考话术："
  },
  "footer": "<div class=\"eyebrow\">Stage 1 · Connect</div>\n  <p>接通建联 · 判据取自《招生老师沟通六阶段参考场景》阶段 1、《招生老师参考话术》§一 破冰话术 ｜ 样例：招生老师 × 黄女士（官抖短视频线索），414 条，2026-09-29 至 10-22 ｜ 逐句读过原文，非词表命中</p>",
  "fold_html": "<details class=\"cc-fold rv\" id=\"ccFold\">\n<summary class=\"cc-fold-sum\">\n<span class=\"ccf-no\">C1 / 口径</span>\n<span class=\"ccf-t\">口径细则</span>\n<span class=\"ccf-chips\"><b>两种线索两种开口</b><b>代称也算称呼</b><b>八句禁区</b></span>\n<span class=\"ccf-act\"><span class=\"t1\">展开看 ↓</span><span class=\"t2\">收起 ↑</span></span>\n</summary>\n<div class=\"cc-fold-body\">\n<div class=\"rv cc-part\">\n  <h3>两种线索，两种开口</h3>\n  <p>两类线索的差别只有一处：<b>开口时「已知信息」的多少</b>。用错类型最典型的症状，\n  就是客户已经说过三遍的信息被问第四遍。</p>\n\n  <div class=\"cc-lead2\">\n    <div class=\"l2\"><span class=\"l2t\">直接线索 · 陌生</span>\n      <p class=\"l2q\">哈喽，你好！我是体德从业7年的健身教练x老师，有一线带训+健身房管理经验，国职+NASM双认证教练，怎么称呼你啊 同学？</p>\n      <p class=\"l2q\">哈喽，你好！我是体德智训负责招生+就业指导的x老师，看到你有咨询意向，咱们主要是想了解这边的环境、课程内容、证书区别、价格、吃住安排、还是就业方面呢？我先挑你感兴趣的讲。</p>\n      <p class=\"l2n\">自我介绍带资历 + 问称呼 + 给选项让客户挑切入点，①②③ 全靠这一句立起来。</p></div>\n    <div class=\"l2 l2b\"><span class=\"l2t\">私域转接 · 已聊过</span>\n      <p class=\"l2q\">先看转接前的聊天记录。顺着用户原有意向承接沟通，不要重复问用户已经说过的信息，不从头开始打招呼问好，有前端沟通的铺垫可直入主题。</p>\n      <p class=\"l2n\">③ 的重点变成<b>复述已知 + 确认</b>，不是问一遍。两类都要说明来意，\n      但说什么算说明来意不一样。</p></div>\n  </div>\n</div>\n\n<div class=\"rv cc-part\">\n  <h3>客户不报名字：代称也算称呼</h3>\n  <p>② 判的是<b>「有没有给客户一个称呼」</b>，不是「有没有问到真名」。问了客户不肯说、或者回一句「随便」，\n  再追就成了盘问。这时换一个代称接着聊，② 照样成立。</p>\n\n  <ul class=\"cc-alias\">\n    <li>同学</li><li>铁子</li><li>好兄弟</li><li>宝子</li><li>姐妹</li>\n  </ul>\n\n  <div class=\"cc-vs\">\n    <div class=\"vs vs-y\"><span class=\"vst\">算</span>\n      <p>客户没给名字（或只说「随便」），销售用一个代称<b>从头叫到尾</b></p></div>\n    <div class=\"vs vs-n\"><span class=\"vst\">不算</span>\n      <p>客户说了「姓黄」，下一句还叫「同学」——<b>没接住客户给的信息</b></p></div>\n  </div>\n\n  <p class=\"cc-fine\">代称只顶替<b>「客户没说」</b>这一种情况；说过了就必须用上，这是 ② 的要害。\n  全程只用同一个，一句「宝子」一句「姐妹」来回换，显得没在听；选词跟客户的年纪、语气对上即可——\n  「铁子」「好兄弟」偏熟络，「同学」「宝子」「姐妹」偏轻。<br>\n  <b>来源</b>：这一条是 2026-11-10 补充确认的团队口径，两份培训文档里没有原文，按约定执行。</p>\n</div>\n\n<div class=\"rv cc-part\">\n  <h3>八句禁区</h3>\n  <p>文档原话：这类话术带有催促、质问感，容易给陌生客户造成压迫感，引发反感、拉黑，\n  新人尤其注意避开。开场与客户沉默唤醒，都要规避。</p>\n  <ul class=\"cc-ban\">\n    <li>喂喂喂，还了解吗？</li>\n    <li>吱一声啊</li>\n    <li>还在吗</li>\n    <li>说句话呀</li>\n    <li>在不在？看到回一下</li>\n    <li>怎么不说话了？还考虑吗？</li>\n    <li class=\"b2\">发 无语 / 流汗 / 狗头 等不礼貌的表情</li>\n  </ul>\n  <p class=\"cc-fine\">原文列了 6 句 + 一类表情。判违规看的是<b>意图</b>不是原句——\n  「在吗」「哈喽？」「？？」这类追问同一件事的，都属于同一类。这一条是<b>一票否决</b>性质：\n  四要件全齐但用了禁区话术，不算做得好。</p>\n</div>\n</div>\n</details>",
  "tail_script": "<script>\n/* 顶部导航「一 · 口径」指向 #c-rule，而那一块默认是折着的。\n   点导航要能直接看到内容，所以落到这个锚点时自动展开一次；\n   手动收起后不再抢着打开（只在 hash 变化时触发）。 */\n(function () {\n  var d = document.getElementById('ccFold');\n  if (!d) return;\n  function sync() {\n    if (location.hash === '#c-rule') d.open = true;\n  }\n  sync();\n  window.addEventListener('hashchange', sync);\n})();\n</script>",
  "cases": [
   {
    "id": "c1",
    "sales": "招生老师",
    "customer": {
     "real": "黄小姐",
     "label": "黄女士"
    },
    "shot": {
     "hint": "①第 1 条 ②第 1-3 条 ③第 3-4 条 ④第 6 条",
     "img": "assets/connect/c1.png"
    },
    "note": "【结论】四要件在开场 6 句内全部成立：第 1 句自我介绍 + 问称呼，第 3 句用上客户给的姓、同时把留言三条复述确认，第 6 句客户自己抛问题——建联结束，需求沟通开始。",
    "total": 39,
    "seg": "整段",
    "items": [
     {
      "t": "time",
      "x": "9月29日 11:44"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "你好啊"
     },
     {
      "t": "band",
      "k": 1,
      "x": "自我介绍：姓名 + 资历一起给：从业 4 年认证教练、6 年团队管理"
     },
     {
      "t": "band",
      "k": 2,
      "x": "称呼客户：先问「怎么称呼你呀」，客户答姓黄，下一句立刻用上"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       1,
       2
      ],
      "x": "哈喽哈喽，同学你好~ 我是体德从业4年的认证教练黄老师，有6年团队管理经验，怎么称呼你呀？"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [
       2
      ],
      "x": "姓黄 你可以叫我黄小姐[害羞]"
     },
     {
      "t": "band",
      "k": 3,
      "x": "说明来意：把客服留言里的三条一次复述，客户只需回一个字确认"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       2,
       3
      ],
      "x": "哈哈哈 好滴黄小姐 咱们客服这边留言信息 是人在河源 想了解国内国际认证区别 目前是零基础想学健身教练~"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [
       3
      ],
      "x": "是的呢"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "可以呢 你平时有健身的习惯不？健身多久啦~"
     },
     {
      "t": "band",
      "k": 4,
      "x": "客户回应：不是「嗯哦」，是确认完自己抛出问题"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [
       4
      ],
      "x": "你们从零基础到拿证需要多久"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "还是说完全没去过健身房"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "之前健身过一两年"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "最近这一年没去了"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "（引“你们从零基础到拿证需要多久”）零基础的教练班课程 学习+考证 3个月全日制脱产哦~"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "（引“之前健身过一两年”）原来 之前是找教练带你练嘛"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "那也不算是0基础 只是可能之前练了一段时间 空了一段 有点陌生"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "对的"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "但是感觉动作还是有些不标准"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "那跟很多姐妹一样 就是脱离教练 可能就不太知道怎么练了"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "太久没练陌生了"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "私教的话 更多是带练 就不会讲太多原理 更多是直接指定让你练什么就练什么"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "在学校呢 就是教你原理 让你知道为什么你要练这个 这个动作对应什么肌肉群 有什么效果 让你自己可以给自己制定计划"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "可以把整个流程和学习内容 价格发来看看吗"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "阔以滴"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "对的"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "在学校学习 是3 个月线下全日制集中学习，半天理论、半天实操，分四个阶段循序渐进上课，每个阶段都会进行理论和实操的考试。平时周一到周五上课，每天七节课。周末双休，可以休息，也可以自主加练 课程安排是每天早上8点开始上课，晚上6点后是自由训练时间~"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "（引“大学生暑假在李维刚创办的体德智训学习，我这一天都…”）这些是过来学习的同学做的记录 可以看看 每天基本就是在吃住练 沉浸式学校学习 ~"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "内容比较多 你看完跟我说哈~"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "好嘞"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "哈哈哈你今天应该上班吧"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "没有上班有点闲所以想找点事做[偷笑]"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "嘶 那你也是赶上好时候了 哈哈哈"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "我看完微你"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "马上国庆放7天"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "好嘞 你先看"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "好的 价格和学习内容呢？发来看看"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "这些是课程内容 你先看下哦~ 费用主要是跟你考取不同证书会有一些区别 另外我了解下 咱们是哪一年的嘞？因为考证和入学都会有年龄的要求~"
     }
    ]
   }
  ]
 },
 "dual": {
  "kind": "value",
  "out": "价值传递(可用于案例分享).html",
  "title": "口径与范本｜体德智训 · 价值传递",
  "desc": "价值传递教材版：三项怎么判（形态 / 出口 / 落点）+ 两组从头看到尾的原文案例，聊天记录整段标色，逐字可查。",
  "brand": "体德智训 · 价值传递",
  "key": "value",
  "nav_name": "价值传递",
  "tag_label": "三段标注",
  "hero": {
   "eyebrow": "Value Delivery · 教材版",
   "h1": [
    "三段怎么判",
    "<em>做对的怎么讲</em>"
   ],
   "cards": [
    {
     "no": "①",
     "name": "形态",
     "kicker": "客户心里的问题",
     "lead": "我买的到底是什么",
     "note": "三个月线下 + 九个月线上 + 两年复训，三件都在"
    },
    {
     "no": "②",
     "name": "出口",
     "kicker": "客户心里的问题",
     "lead": "买完能得到什么",
     "note": "就业路径 / 收入区间 / 证书去向，至少一条讲透"
    },
    {
     "no": "③",
     "name": "落点",
     "kicker": "客户心里的问题",
     "lead": "跟我有什么关系",
     "note": "挂到客户说过的话上，他下一句要变具体"
    }
   ],
   "meta": [
    "形态＝讲的件数、出口＝讲透几条、落点＝客户下一句变没变；三项独立算，不合并成一个分数",
    "聊天记录整段可查"
   ]
  },
  "stages": [
   {
    "no": 1,
    "mark": "①",
    "name": "形态",
    "chip": "①形态",
    "color": "#2563EB",
    "bandbg": "#E8EFFF",
    "legend": "我买的是什么"
   },
   {
    "no": 2,
    "mark": "②",
    "name": "出口",
    "chip": "②出口",
    "color": "#0E9F6E",
    "bandbg": "#E6F9F1",
    "legend": "买完能得到什么"
   },
   {
    "no": 3,
    "mark": "③",
    "name": "落点",
    "chip": "③落点",
    "color": "#D97706",
    "bandbg": "#FFF4DF",
    "legend": "跟我有什么关系"
   }
  ],
  "sec": {
   "no": "第 2 块 / 做对的",
   "h": "参考话术："
  },
  "footer": "<div class=\"eyebrow\">Value Delivery · Manual</div>\n  <p>口径与范本 · 取自《价值传递》的「口径」一块，加两组从头看到尾的完整对话 ｜ 全批 99 组、三项全过 11 组，这两组都在其中，也是三段最好指认的两组 ｜ 逐句读过原文，非词表命中</p>",
  "tail_script": "",
  "cases": [
   {
    "id": "c1",
    "sales": "招生老师",
    "customer": {
     "real": "🐈",
     "label": "客户A"
    },
    "shot": {
     "hint": "三段穿插着走：出口在 24-25、落点在 31-32、形态在 38-43",
     "img": "assets/mark/mc3.png"
    },
    "note": "【结论】这个客户 16:11 直接问「三个月多少钱」，没急着报数字——先把证书去向讲清（宁波新一线要国际认证），再把价格挂到「就是让我上手」这句原话上给 1200 优惠，最后才把 20600 的三件套一次说完。三段没按时间顺序走，但每一段都接在客户刚问的那句话后面。",
    "total": 46,
    "seg": "整段",
    "items": [
     {
      "t": "time",
      "x": "10月26日 16:02"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "你好"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "哈喽哈喽"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "请问咱是单纯自我提升"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "还是有打算做教练呀"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "看咱是留了咨来着"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "做教练"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "要考那个新国职"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "想问一下课程安排"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱们系统学习要三个月哦"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱之前是练了多久啦"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "了解一下基础[转圈]"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "纯小白"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "[嘿哈]咱整体下来强度还是在的哦，后续可以考虑到健身房试试看能不能享受训练～咱不冲动消费"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "妹妹是刚毕业噻还是还在上学哇"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "我在健身房上班"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "那也是了解了一些工作内容啦"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "淡旺季这个咱知道不"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "三个月多少钱"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱价格是跟证书挂钩滴"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "这个我知道"
     },
     {
      "t": "band",
      "k": 2,
      "x": "出口 · 证书只是敲门砖，标准落到客户所在城市：宁波新一线，好单位都要求国际认证"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       2
      ],
      "x": "不过证书还是没有摆脱敲门砖的性质嘛，主要还是看咱们以后发展地域单位要求"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       2
      ],
      "x": "宁波那边是新一线诶，好单位基本上都要求国际认证啦"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱们是准备学完在之前单位上不"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "是的"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "那边最低要求是啥证哇"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "对我没要求"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "就是让我上手"
     },
     {
      "t": "band",
      "k": 3,
      "x": "落点 · 挂到客户原话「就是让我上手」，顺手给 1200 考证优惠"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       3
      ],
      "x": "哈哈哈那就这个单纯自我提升的价格也可以，不过近期的班考证有1200的优惠诶，你看你要上一个啵"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       3
      ],
      "x": "（引“就是让我上手”）女教练现在是香饽饽都抢着要哈哈哈"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "就是想考那个新国职"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "我看你发的没有这个"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "第二个就是"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "现在体育总局那边改名啦"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "噢噢"
     },
     {
      "t": "band",
      "k": 1,
      "x": "形态 · 20600 一条说完三件：三个月线下集训 + 九个月线上进阶 + 两年内一次免费复训"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       1
      ],
      "x": "20600，三个月线下集训＋九个月线上进阶课＋两年内一次免费复训的权益"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       1
      ],
      "x": "咱们是理论＋实操一起滴，不会只抓一个，毕竟现在获取知识的方式有很多嘛"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       1
      ],
      "x": "用这些基础出去之后也能正确运用网上的碎片化知识[嘿哈]"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       1
      ],
      "x": "身材也同样是要抓的，咱瞅瞅这些管理能接受啵，[撇嘴]咱们管得还是蛮严格的"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "不是让学生学完只是通过考证这么简单，更需要培养的是实际运用变现"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "不过这边时间还是有那么久诶[撇嘴]时间上好安排啵，实在不行可以断开~"
     }
    ]
   },
   {
    "id": "c2",
    "sales": "招生老师",
    "customer": {
     "real": "姜彦博",
     "label": "客户B"
    },
    "shot": {
     "hint": "三段顺序打乱：落点在 30-35、形态在 49-51、出口在 85-91",
     "img": "assets/mark/mc2.png"
    },
    "note": "【结论】姜彦博：落点靠「按你想去的城市、证书、体型推荐」立住，但建筑工程实习半年这条最硬的事实被自己掐断，全程也没报出一个数字。",
    "total": 96,
    "seg": "整组",
    "items": [
     {
      "t": "time",
      "x": "10月15日 09:20"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "哈喽哈喽"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "请问咱是单纯自我提升还是有打算做教练呀"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "做教练"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱之前是练了多久啦"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "了解一下基础"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "快一年了吧"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "可以啊"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "基础这么好"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "不过这个涉及到考证哦"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱有了解过这些证书的区别啵"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "我提前整理了一个笔记~咱瞅瞅"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "还没去了解"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "1"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "不过有学生说我电脑发出来看不着，手机发出来可以[流泪]"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱看能正常用啵"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "能"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "好好好，对啦咱们怎么称呼呀"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱是几几年滴涅"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "姜彦博"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "05"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "00后健身意识就是强啊"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "弟弟咱是温州那边的啵"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "我看电话是那"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "是的"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "以后还是到那边发展啵"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "还是杭州啊啥的"
     },
     {
      "t": "band",
      "k": 3,
      "x": "落点 · 客户说都可以看就业，就按他的城市、证书、体型来推荐"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [
       3
      ],
      "x": "都可以，看就业怎么样"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       3
      ],
      "x": "因为一线超一线这种城市好点的单位都会要求国际认证"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       3
      ],
      "x": "国际认证会贵一些"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       3
      ],
      "x": "主要咱推荐就业的时候也是根据"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       3
      ],
      "x": "咱想去的城市、"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       3
      ],
      "x": "持有的证书、体型去推荐的"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "弟弟大学学滴啥专业呀"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "建筑工程"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "纳尼"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "好家伙"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "自己喜欢的嘛"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "是的"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "弟弟实习的时候试了下这个行业不"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "建筑"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "有啊，实习了半年"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "坏了忘了正事，光顾着唠嗑了[害羞]"
     },
     {
      "t": "band",
      "k": 1,
      "x": "形态 · 一句话三件套：三个月集训 + 九个月线上 + 两年复训"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       1
      ],
      "x": "弟弟这是咱们课程大纲"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       1
      ],
      "x": "线下系统学习课程是线下三个月集训＋九个月线上课＋两年内一次免费复训的权益"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       1
      ],
      "x": "组成"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "费用是多少呢"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "弟弟之前带过人练啵"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "没有"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "那吃住是怎么样的"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "我找了一个学生录的视频来着，教练的工作内容大概是这样~"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "（引“那吃住是怎么样的”）离咱最近的校区是南京跟长沙"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "如果两种环境咱都能接受我还是比较推荐咱长沙校区"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "我跟刚哥都在这边~"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "有个照应，再加上弟弟以后如果做自媒体的话，体德跟刚哥本身就是流量"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱平时管得还是蛮严的嗷"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "不过咱整体时长还是有那么久，有跟爸妈商量过考虑转行啵"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "一个班有多少人呀"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "30-45人"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "这几个月人会少点[嘿哈]"
     },
     {
      "t": "msg",
      "who": "c",
      "k": [],
      "x": "几号开始上课"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "最近的班是21号滴"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "还有一个名额"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "长沙"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "南京是28号"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "都差不多年前一点点结束"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱们这上边有对上的啵"
     },
     {
      "t": "band",
      "k": 2,
      "x": "出口 · 就业讲成时间线：课程第四阶段就教包装，毕业后 1/3/6 个月回访"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       2
      ],
      "x": "对啦还有一个板块没讲"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       2
      ],
      "x": "就业"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       2
      ],
      "x": "咱就业方面的帮助首先体现在课程设置上，第四阶段着重教咱怎么营销自己包装自己以及授课和转化技巧嘛，期间班主任和就业老师会帮忙拍摄形象照和制作简历（会p），毕业前会安排体验课，由我们工作人员/新生去扮演会员，咱来尝试转化这个会员，在校内查漏补缺"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [
       2
      ],
      "x": "就业咱是推荐就业的形式，根据咱想去的城市、证书、体型去推荐，有体德学生在的地方、一线优先推荐，就业之后还没完等咱毕业之后，第一、三、六个月都会有就业老师定期地去回访，了解学生现在的薪资状况以及就业的状态，招生老师每年都会跟进自己的学生[呲牙]，像6.19号体德8周年家宴邀请了历来的体德毕业生去西湖楼吃饭，安排了咱工作人员了解学生近况，体德对毕业生也很重视~不是推进去之后就不管啦[转圈]"
     },
     {
      "t": "time",
      "x": "10月22日 14:00"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "哈喽哈喽下午好呀弟弟"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱不是之前有考虑过做教练嘛"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "有了解过教练的薪资结构和淡旺季啵"
     },
     {
      "t": "msg",
      "who": "s",
      "k": [],
      "x": "咱们了解行业不能只看好的一面嘛"
     }
    ]
   }
  ]
 }
}""")

if __name__ == "__main__":
    sys.exit(main())
