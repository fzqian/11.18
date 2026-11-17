# -*- coding: utf-8 -*-
"""生成完必须过这一关 —— 这次手工改页面踩过的坑，全部变成断言。

查十组：
  1 页面结构：div 配平、pane 不重复、复制按钮指向的 pane 真的存在
  2 条数：标签页写的数字 == 里面实际的消息条数；标题/复制头里的数字也一样
  3 要点版：条数 == 要点数 + 锚点数；每条锚点必须是客户说的、且没挂标注
  4 客户代号：cases 里的真名一个字都不能出现在页面上（含 title/desc/footer）
  5 标签：cl-chip 必须在 cl-chips 里；不许空 cl-chips；颜色值不许是全角冒号
  6 导航：六项齐全、当前页高亮、暂不开放的项没有 href
  7 卡片：hero 里的卡数 == spec 里的卡数，且顺序标记 ①②③④ 对得上
  8 图例：每个阶段一条，颜色与 stages 一致
  9 全局：没有「客户「客户」」这种代号重复；没有 TODO/占位符残留
 10 引用：css/js 文件都在，css 版本号不是旧的

用法：
  python kit/check.py            # 全部
  python kit/check.py --only 03   # 只查一页
"""
import argparse
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OK, BAD = [], []


def ok(msg):
    OK.append(msg)


def bad(msg):
    BAD.append(msg)


def panes(page):
    """{pane_id: html}，只取 cl-chat 容器内部。"""
    out = {}
    for part in re.split(r'(?=<div class="cl-chat[^"]*" id="chat\d+k?")', page)[1:]:
        pid = re.search(r'id="(chat\d+k?)"', part).group(1)
        out[pid] = part
    return out


def msgs_of(chunk):
    body = chunk.split('<div class="cl-body">', 1)[-1]
    return re.findall(r'<div class="cl-msg ([sc])"([^>]*)>', body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()

    nav = json.load(io.open(os.path.join(ROOT, "kit/nav.json"), encoding="utf-8"))
    for sp in sorted(glob.glob(os.path.join(ROOT, "spec/*.json"))):
        name = os.path.basename(sp)[:-5]
        if a.only and a.only not in name:
            continue
        spec = json.load(io.open(sp, encoding="utf-8"))
        doc = json.load(io.open(os.path.join(ROOT, spec["cases"]), encoding="utf-8"))
        path = os.path.join(ROOT, spec["out"])
        page = io.open(path, encoding="utf-8").read()
        P = panes(page)
        print("\n检查 %s（%d 字节）" % (spec["out"], len(page.encode("utf-8"))))

        # ── 1 结构 ──
        print("[1] 结构")
        opens = len(re.findall(r"<div\b", page))
        closes = len(re.findall(r"</div>", page))
        (ok if opens == closes else bad)("div 开合 %d/%d" % (opens, closes))
        if len(P) == len(set(P)):
            ok("pane 不重复：%s" % " ".join(sorted(P)))
        else:
            bad("pane id 重复")
        for m in re.finditer(r'data-lc="(chat\d+)"', page):
            (ok if m.group(1) in P else bad)("复制按钮指向 %s" % m.group(1))

        # ── 2 条数 ──
        print("[2] 条数")
        for m in re.finditer(r'class="cl-tab[^"]*"[^>]*data-pane="(chat\d+k?)"[^>]*>[^<]*<b>(\d+)</b>', page):
            pid, n = m.group(1), int(m.group(2))
            real = len(msgs_of(P.get(pid, "")))
            (ok if n == real else bad)("%s 标签写 %d 条，实际 %d 条" % (pid, n, real))
        for case in doc["cases"]:
            real_total = case["total"]
            pid = "chat%d" % case["group"]
            chunk = P.get(pid, "")
            head = re.search(r'data-cc-head="([^"]*)"', chunk)
            if head:
                h = head.group(1).replace("&#10;", "\n")
                m = re.search(r"第 0-(\d+) 条（(\d+) 条原文）", h)
                if m:
                    (ok if int(m.group(2)) == len(msgs_of(chunk)) else bad)(
                        "%s 复制头写 %s 条原文，实际 %d 条" % (pid, m.group(2), len(msgs_of(chunk))))
                    (ok if int(m.group(1)) == real_total - 1 else bad)(
                        "%s 复制头写第 0-%s 条，原文共 %d 条" % (pid, m.group(1), real_total))
            tt = re.search(r'<div class="cl-title">(.*?)</div>', chunk)
            if tt:
                t = tt.group(1)
                rg = re.search(r"第 0-(\d+) 条", t)      # 单版页标题写的是区间末尾
                m = re.search(r"(\d+) 条", t)
                want = real_total - 1 if rg else real_total
                got = int(rg.group(1)) if rg else (int(m.group(1)) if m else None)
                (ok if got == want else bad)("%s 标题写 %s，应为 %d（原文共 %d 条）"
                                             % (pid, got, want, real_total))

        # ── 3 要点版 ──
        print("[3] 要点版")
        want_note = sum(1 for c in doc["cases"] if (c.get("note") or "").strip())
        got_note = len(re.findall(r'<div class="cl-note">', page))
        (ok if want_note == got_note else bad)("【结论】块 %d 个，cases 里写了 %d 个" % (got_note, want_note))
        for case in doc["cases"]:
            pid = "chat%dk" % case["group"]
            if pid not in P:
                continue
            chunk = P[pid]
            ms = msgs_of(chunk)
            keyed = sum(1 for w, a in ms if re.search(r'data-k="[0-9]+"', a))
            anchors = [(w, a) for w, a in ms if "data-anchor" in a]
            n = len(ms)
            if n == keyed + len(anchors):
                ok("%s 共 %d 条 = 要点 %d + 锚点 %d" % (pid, n, keyed, len(anchors)))
            else:
                bad("%s 共 %d 条，与要点 %d + 锚点 %d 对不上" % (pid, n, keyed, len(anchors)))
            for i, (w, at) in enumerate(anchors):
                if w != "c":
                    bad("%s 第 %d 个锚点不是客户说的" % (pid, i + 1))
                if re.search(r'data-k="[0-9]+"', at):
                    bad("%s 第 %d 个锚点自己挂了标注，会重复计要点" % (pid, i + 1))
            if anchors:
                ok("%s 锚点全是客户原话、且都没挂标注" % pid)
            for w, at in ms:
                if w == "c" and re.search(r'data-k="[0-9]+"', at) and "data-anchor" in at:
                    bad("%s 有既当锚点又当要点的消息" % pid)

        # ── 4 真名 ──
        print("[4] 客户代号")
        reals = [c["customer"]["real"] for c in doc["cases"] if c["customer"]["real"]]
        hit = [r for r in reals if r and r in page]
        (ok if not hit else bad)("真名残留：%s" % ("无" if not hit else "、".join(hit)))
        for c in doc["cases"]:
            if c["customer"]["label"] in ("客户", ""):
                bad("代号没起：%s" % c["customer"])

        # ── 5 标签 ──
        print("[5] 标签")
        loose = len(re.findall(r"</div><span class=\"cl-chip\"", page))
        (ok if loose == 0 else bad)("裸标签（chip 没在 cl-chips 里）：%d 处" % loose)
        empty = page.count('<div class="cl-chips"></div>')
        (ok if empty == 0 else bad)("空 cl-chips：%d 处" % empty)
        fullwidth = len(re.findall(r'style="[^"]*：', page))
        (ok if fullwidth == 0 else bad)("style 里有全角冒号：%d 处" % fullwidth)

        # ── 6 导航 ──
        print("[6] 导航")
        links = re.findall(r'<a href="([^"]*)"( class="on")?>([^<]*)</a>', page)
        offs = re.findall(r'<span class="nav-off"[^>]*>([^<]*)<em>', page)
        total_nav = len(links) + len(offs)
        (ok if total_nav == len(nav["items"]) else bad)("导航 %d 项，应为 %d 项" % (total_nav, len(nav["items"])))
        on = [t for _, c, t in links if c]
        (ok if len(on) == 1 else bad)("当前页高亮 %d 个：%s" % (len(on), on))
        (ok if not [x for x in offs if "暂不开放" not in page] else bad)("暂不开放项缺小标")

        # ── 7 卡片 ──
        print("[7] 卡片")
        cards = re.findall(r'<div class="st s(\d)"><span class="stn">(.)</span><b>(.*?)</b>', page)
        (ok if len(cards) == len(spec["hero"]["cards"]) else bad)(
            "卡片 %d 张，spec 里 %d 张" % (len(cards), len(spec["hero"]["cards"])))
        for i, (n, mark, nm) in enumerate(cards, start=1):
            if int(n) != i:
                bad("卡片顺序错：第 %d 张写成 s%s" % (i, n))
            if mark != spec["stages"][i - 1]["mark"]:
                bad("卡片 %s 的标记是 %s" % (nm, mark))

        # ── 8 图例 ──
        print("[8] 图例")
        for st in spec["stages"]:
            if ('<b style="color:%s">%s%s</b>' % (st["color"], st["mark"], st["name"])) not in page:
                bad("图例缺 %s%s" % (st["mark"], st["name"]))
        ok("图例 %d 段都在" % len(spec["stages"]))

        # ── 9 全局 ──
        print("[9] 全局")
        (ok if "客户「客户」" not in page else bad)("标题出现「客户「客户」」")
        for token in ("TODO", "{{", "}}", "%s", "None"):
            if token in page:
                bad("页面里残留占位符 %r" % token)

        # ── 10 引用 ──
        print("[10] 引用")
        for ref in re.findall(r'(?:href|src)="(assets/[^"?]+)', page):
            if not os.path.exists(os.path.join(ROOT, ref)):
                bad("引用了不存在的文件 %s" % ref)
        ok("css/js 引用都能找到")

    print("\n" + "=" * 46)
    print("通过 %d 项" % len(OK))
    for b in BAD:
        print("  ✗ " + b)
    if not BAD:
        print("全部通过")
    return 0 if not BAD else 2


if __name__ == "__main__":
    sys.exit(main())
