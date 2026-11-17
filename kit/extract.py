# -*- coding: utf-8 -*-
"""把已经排好的案例页「反向拆」成 cases/*.json —— 只在第一次搭套件时跑一次。

为什么要拆：页面上 148 条消息是一个字一个字校对过的，重新手打一遍必然出错。
所以先从这里已上线的页面把「原文 / 谁说 / 挂哪一段 / 色带 / 时间条」原样抽出来，
存成 json；以后 build.py 只认这份 json，页面就等于「可再生成」。

用法：
  python kit/extract.py --page "接通建联(可用于案例分享).html" --out cases/01_接通建联.json --stage 1
  python kit/extract.py --page "价值传递(可用于案例分享).html"   --out cases/03_价值传递.json  --stage 3
"""
import argparse
import io
import json
import os
import re
import sys

CIRCLED = {"①": 1, "②": 2, "③": 3, "④": 4}


def unesc(s):
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#10;", "\n"), ("&quot;", '"')):
        s = s.replace(a, b)
    return s


def txt(s):
    return unesc(re.sub(r"<[^>]+>", "", s)).strip()


def conv(body):
    """把 cl-body 里的时间条 / 色带 / 消息按出现顺序转成 items（单一分隔，逐块认）。"""
    rows = []
    body = body.split('<div class="cl-note">')[0]
    chunks = re.split(r'(?=<div class="cl-(?:time|band|msg)\b)', body)
    for c in chunks:
        if c.startswith('<div class="cl-time"'):
            m = re.search(r"<span>(.*?)</span>", c, re.S)
            rows.append({"t": "time", "x": txt(m.group(1)) if m else ""})
        elif c.startswith('<div class="cl-band"'):
            m = re.search(r'>((?:(?!</div>).)*)</div>', c, re.S)
            b = txt(m.group(1)) if m else ""
            k = CIRCLED.get(b[:1], 0)
            if k:
                b = b[1:].lstrip("　 ")
            rows.append({"t": "band", "k": k, "x": b})
        elif c.startswith('<div class="cl-msg'):
            who = re.search(r'<div class="cl-msg ([sc])"', c).group(1)
            # data-k="12" = 一条同时挂 ① 和 ②；空 = 没挂
            dk = re.search(r'data-k="([0-9]*)"', c)
            k = [int(d) for d in (dk.group(1) if dk else "")]
            t = re.search(r'<span class="cl-txt">(.*?)</span>', c, re.S)
            rows.append({"t": "msg", "who": who, "k": k, "x": txt(t.group(1)) if t else ""})
    return rows


def panes(page):
    out = []
    for part in re.split(r'(?=<div class="cl-chat(?: cl-pane)?" id="chat\d+")', page)[1:]:
        pid = re.search(r'id="(chat\d+)"', part).group(1)
        # 单版页没有 chat1k，所以只有完整版会被切出来
        title = re.search(r'<div class="cl-title">(.*?)</div>', part, re.S)
        sub = re.search(r'<div class="cl-sub">(.*?)</div>', part, re.S)
        note = re.search(r'<div class="cl-note">(.*?)</div>', part, re.S)
        head = re.search(r'data-cc-head="([^"]*)"', part)
        who = re.findall(r'<div class="cl-msg ([sc])"[^>]*data-who="([^"]*)"', part)
        names = {}
        for w, n in who:
            names.setdefault(w, n)
        body = part.split('<div class="cl-body">', 1)[1] if '<div class="cl-body">' in part else ""
        out.append({
            "pane": pid,
            "title": txt(title.group(1)) if title else "",
            "sub": txt(sub.group(1)) if sub else "",
            "head": unesc(head.group(1)) if head else "",
            "items": conv(body),
            "note": txt(note.group(1)) if note else "",
            "names": names,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stage", type=int, required=True, help="1=接通建联（四要件） 3=价值传递（三段）")
    a = ap.parse_args()

    page = io.open(a.page, encoding="utf-8").read()
    shots = re.findall(r'<span class="sbd">(.*?)</span>', page)
    imgs = re.findall(r'<a class="shotopen" href="([^"]*)"', page)

    cases = []
    for i, p in enumerate(panes(page), start=1):
        cases.append({
            "id": "c%d" % i,
            "group": i,
            "sales": p["names"].get("s", "招生老师"),
            "customer": {"real": p["names"].get("c", ""), "label": ""},
            "shot": {"hint": txt(shots[i - 1]) if i - 1 < len(shots) else "",
                     "img": imgs[i - 1] if i - 1 < len(imgs) else ""},
            "title": p["title"],
            "sub": p["sub"],
            "head": p["head"],
            "items": p["items"],
            "note": p["note"],
        })

    doc = {"source": os.path.basename(a.page), "stage": a.stage, "cases": cases}
    io.open(a.out, "w", encoding="utf-8", newline="\n").write(json.dumps(doc, ensure_ascii=False, indent=1))
    for c in cases:
        n = sum(1 for it in c["items"] if it["t"] == "msg")
        k = sum(1 for it in c["items"] if it["t"] == "msg" and it["k"])
        print("  %s  消息 %d 条（带标注 %d）  客户=%s  抬头=%s" % (c["id"], n, k, c["customer"]["real"], c["title"]))
    print("→ %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
