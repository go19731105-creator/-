#!/usr/bin/env python3
"""福山市のテニスショップ「TENNIS ch.249（テニスチャンネル）」の宣伝動画
（テニススクール生徒募集つき）を生成するスクリプト。

必要なもの: Python 3, Pillow, numpy, pyopenjtalk, ffmpeg, IPAゴシックフォント
使い方:    python3 make_tennis_promo.py [出力ファイル名]
"""
import math
import os
import subprocess
import sys
import wave
from functools import lru_cache

import numpy as np
import pyopenjtalk
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- 設定（ここを書きかえる）
SHOP_NAME = "TENNIS ch.249"          # 画面に出す店名
SHOP_KANA = "テニスチャンネル"        # 店名の読み（画面）
SHOP_READ = "テニスチャンネル"        # 店名の読み（ナレーション）
CATCH = "福山のテニスショップ"
ADDRESS = "福山市沖野上町4-18-19 1F"
TEL = "084-999-0249"

W, H = 1280, 720
FPS = 24
SR = 48000
FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
HERE = os.path.dirname(os.path.abspath(__file__))

NAVY = (22, 45, 70)
GREEN = (46, 140, 87)
DGREEN = (30, 100, 62)
COURT = (52, 110, 180)
DCOURT = (40, 88, 150)
BALL = (214, 236, 60)
YELLOW = (255, 214, 60)
ORANGE = (255, 140, 40)
RED = (230, 50, 60)
WHITE = (255, 255, 255)
CREAM = (250, 250, 240)
TEXT = (35, 45, 60)
GRAY = (150, 160, 175)
SKIN = (245, 205, 170)
HAIR = (70, 50, 40)


# ---------------------------------------------------------------- 台本
# 各シーン: key=画面の種類, lines=[{t:字幕, r:読み(任意), b:画面に出す短い文(任意)}]
SCENES = [
    dict(key="open", lines=[
        dict(t="テニスが好きな人、これからテニスを始めたい人へ。"),
        dict(t=f"福山市沖野上町にあるテニスショップ、{SHOP_NAME}をご紹介します。",
             r=f"福山市おきのかみちょうにあるテニスショップ、{SHOP_READ}をご紹介します。"),
    ]),
    dict(key="shop", title="テニス好きが集まるお店", lines=[
        dict(t="お店では、大きなテレビでプロの試合を観ることができます。", b="大画面でプロの試合を観戦"),
        dict(t="コーヒーを飲みながら、テニスの話でのんびり過ごせる、居心地のいいお店です。",
             b="コーヒー片手にのんびり"),
    ]),
    dict(key="items", title="ラケット・ガットのことなら", icons=["racket", "string", "talk"], lines=[
        dict(t="ヨネックスとバボラを中心に、ラケットの新品注文ができます。", b="YONEX・Babolat\nラケットの新品注文"),
        dict(t="ガットの張り替えも、おまかせください。", b="ガットの\n張り替え"),
        dict(t="自分に合う道具選びも、気軽に相談してください。", b="道具選びの\nご相談"),
    ]),
    dict(key="recruit", lines=[
        dict(t="そして、ここでお知らせです！"),
        dict(t="テニススクールの生徒さんを募集しています！"),
        dict(t="まずは気軽に、見学や体験に来てみませんか？"),
    ]),
    dict(key="easy", title="はじめてでも安心！", lines=[
        dict(t="テニスがはじめての人も、大歓迎です。", b="はじめての方も大歓迎"),
        dict(t="お子さんから大人の方まで、楽しくテニスができます。", b="子どもから大人まで"),
        dict(t="ラケットやガットのことも、お店でそのまま相談できます。", b="道具の相談もお店で"),
    ]),
    dict(key="flow", title="お問い合わせの流れ", lines=[
        dict(t="お問い合わせは、とってもかんたん。"),
        dict(t="まずは、LINEでご連絡ください。", r="まずは、ラインでご連絡ください。", b="LINEで連絡"),
        dict(t="日にちが決まったら、動きやすい服と運動靴で来るだけ。", b="動きやすい服と\n運動靴で"),
        dict(t="コーチと一緒に、ボールを打ってみましょう！", b="コーチと一緒に\n打ってみよう"),
    ]),
    dict(key="cta", lines=[
        dict(t=f"テニスのことなら、{SHOP_NAME}へ。", r=f"テニスのことなら、{SHOP_READ}へ。"),
        dict(t="ご来店やスクールのお問い合わせは、事前にLINEでご連絡ください。",
             r="ご来店やスクールのお問い合わせは、事前にラインでご連絡ください。"),
        dict(t="一緒にテニスを楽しみましょう！"),
    ]),
]

RALLY = 1.25  # ラリーで1球が往復する片道の秒数


# ---------------------------------------------------------------- 汎用
@lru_cache(maxsize=None)
def F(size):
    return ImageFont.truetype(FONT_PATH, size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = clamp(x)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def lerp(a, b, p):
    return a + (b - a) * p


def lerpc(c1, c2, p):
    p = clamp(p)
    return tuple(int(round(lerp(a, b, p))) for a, b in zip(c1, c2))


def text(d, xy, s, size, fill=TEXT, anchor="la", stroke=0, stroke_fill=NAVY):
    d.text(xy, s, font=F(size), fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)


def wrap(s, size, maxw):
    """maxw に収まるように折り返す。"\n" で明示的に改行できる。"""
    if "\n" in s:
        return [l for part in s.split("\n") for l in wrap(part, size, maxw)]
    font = F(size)
    lines, cur = [], ""
    for ch in s:
        if font.getlength(cur + ch) > maxw and cur and ch not in "。、）」！？ー・…":
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def rr(d, box, r, fill=None, outline=None, width=1):
    box = [int(v) for v in box]
    if box[2] <= box[0] or box[3] <= box[1]:
        return
    r = min(r, (box[2] - box[0]) / 2, (box[3] - box[1]) / 2)
    d.rounded_rectangle(box, radius=int(r), fill=fill, outline=outline, width=width)


@lru_cache(maxsize=None)
def gradient(top, bottom):
    t = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t)
    arr = np.repeat(arr, W, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


class Timer:
    """シーン内の各セリフの開始時刻・長さを扱う。"""

    def __init__(self, starts, durs, t):
        self.starts, self.durs, self.t = starts, durs, t

    def since(self, k):
        return self.t - self.starts[k]

    def current(self):
        cur = -1
        for k, st in enumerate(self.starts):
            if self.t >= st:
                cur = k
        return cur


# ---------------------------------------------------------------- 部品
def ball(d, cx, cy, r, shadow=None):
    if shadow is not None:
        sx, sy = shadow
        d.ellipse([sx - r * 0.9, sy - r * 0.3, sx + r * 0.9, sy + r * 0.3], fill=(0, 0, 0, 60))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BALL, outline=lerpc(BALL, NAVY, 0.25), width=max(1, int(r / 8)))
    w = max(1, int(r / 5))
    d.arc([cx - r * 1.9, cy - r, cx - r * 0.1, cy + r], -55, 55, fill=WHITE, width=w)
    d.arc([cx + r * 0.1, cy - r, cx + r * 1.9, cy + r], 125, 235, fill=WHITE, width=w)


def racket_head(d, hx, hy, ang, s, color=RED):
    """(hx, hy) が持ち手側の端。ang 方向へラケットをのばす。"""
    ux, uy = math.cos(ang), math.sin(ang)
    neck = (hx + ux * 26 * s, hy + uy * 26 * s)
    d.line([(hx, hy), neck], fill=NAVY, width=max(3, int(6 * s)))
    c = (hx + ux * 50 * s, hy + uy * 50 * s)
    rx, ry = 17 * s, 24 * s
    pts = []
    for i in range(24):
        a = 2 * math.pi * i / 24
        ex, ey = math.cos(a) * ry, math.sin(a) * rx
        pts.append((c[0] + ex * ux - ey * uy, c[1] + ex * uy + ey * ux))
    d.polygon(pts, fill=(250, 250, 250, 150), outline=color)
    d.line(pts + [pts[0]], fill=color, width=max(2, int(5 * s)), joint="curve")


def player(d, x, y, s=1.0, shirt=(60, 120, 200), swing=0.0, side=1, hair=HAIR, legs_open=0.0):
    """y は足元。swing は -1〜1（ラケットを振る角度）、side=1 で右手持ち。"""
    hip = (x, y - 40 * s)
    lw = max(3, int(10 * s))
    for sign in (1, -1):
        a = (0.25 + legs_open) * sign
        d.line([hip, (x + math.sin(a) * 40 * s, y)], fill=NAVY, width=lw)
    sh = (x, y - 80 * s)
    # 反対の腕
    d.line([sh, (x - side * 30 * s, sh[1] + 22 * s)], fill=shirt, width=lw)
    rr(d, (x - 17 * s, y - 88 * s, x + 17 * s, y - 36 * s), 11 * s, fill=shirt)
    d.ellipse([x - 16 * s, y - 122 * s, x + 16 * s, y - 90 * s], fill=SKIN)
    d.pieslice([x - 16 * s, y - 124 * s, x + 16 * s, y - 96 * s], 180, 360, fill=hair)
    # ラケットを持つ腕
    a = math.radians(-20 + swing * 70) if side > 0 else math.radians(200 - swing * 70)
    hand = (sh[0] + math.cos(a) * 34 * s, sh[1] + math.sin(a) * 34 * s)
    d.line([sh, hand], fill=shirt, width=lw)
    d.ellipse([hand[0] - 5 * s, hand[1] - 5 * s, hand[0] + 5 * s, hand[1] + 5 * s], fill=SKIN)
    racket_head(d, hand[0], hand[1], a - side * 0.6, s)
    return hand


def court(d, top, bottom, xc, wtop, wbot):
    """透視図のテニスコート（上が奥）。"""
    def at(fx, fy):
        w = lerp(wtop, wbot, fy)
        return (xc + (fx - 0.5) * w, lerp(top, bottom, fy))

    m = 0.08
    outer = [at(-m, -0.06), at(1 + m, -0.06), at(1 + m * 1.6, 1.06), at(-m * 1.6, 1.06)]
    d.polygon(outer, fill=GREEN)
    d.polygon([at(0, 0), at(1, 0), at(1, 1), at(0, 1)], fill=COURT)
    lw = 4
    for fx in (0, 0.125, 0.875, 1):
        d.line([at(fx, 0), at(fx, 1)], fill=WHITE, width=lw)
    for fy in (0, 1):
        d.line([at(0, fy), at(1, fy)], fill=WHITE, width=lw)
    for fy in (0.23, 0.77):
        d.line([at(0.125, fy), at(0.875, fy)], fill=WHITE, width=lw)
    d.line([at(0.5, 0.23), at(0.5, 0.77)], fill=WHITE, width=lw)
    # ネット
    l, r = at(-0.04, 0.5), at(1.04, 0.5)
    nh = lerp(wtop, wbot, 0.5) * 0.09
    d.polygon([(l[0], l[1] - nh), (r[0], r[1] - nh), r, l], fill=(30, 30, 40, 110))
    for i in range(1, 40):
        x = lerp(l[0], r[0], i / 40)
        d.line([(x, l[1] - nh), (x, l[1])], fill=(230, 230, 230, 90), width=1)
    d.line([(l[0], l[1] - nh), (r[0], r[1] - nh)], fill=WHITE, width=6)
    for p in (l, r):
        d.line([(p[0], p[1] - nh - 6), p], fill=(60, 60, 60), width=5)
    return at


def check_mark(d, cx, cy, r, color=GREEN):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    d.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)], fill=WHITE,
           width=max(3, int(r * 0.22)), joint="curve")


def channel_badge(d):
    rr(d, (24, 20, 52 + F(24).getlength(SHOP_NAME) + 40, 70), 25, fill=(255, 255, 255, 230))
    ball(d, 50, 45, 15)
    text(d, (74, 45), SHOP_NAME, 24, fill=NAVY, anchor="lm")


def icon(d, kind, cx, cy, s, t=0.0):
    if kind == "basic":  # ボールがはねる
        bh = abs(math.sin(t * 3)) * 30 * s
        d.line([(cx - 40 * s, cy + 34 * s), (cx + 40 * s, cy + 34 * s)], fill=GREEN, width=int(5 * s))
        ball(d, cx, cy + 18 * s - bh, 16 * s)
    elif kind == "form":  # スロー再生
        rr(d, (cx - 44 * s, cy - 32 * s, cx + 44 * s, cy + 32 * s), 10 * s, fill=NAVY)
        d.polygon([(cx - 12 * s, cy - 16 * s), (cx - 12 * s, cy + 16 * s), (cx + 16 * s, cy)], fill=WHITE)
        text(d, (cx + 40 * s, cy + 28 * s), "0.5x", int(16 * s), fill=YELLOW, anchor="rb")
    elif kind == "match":  # トロフィー
        c = YELLOW
        d.pieslice([cx - 30 * s, cy - 60 * s, cx + 30 * s, cy + 10 * s], 0, 180, fill=c)
        d.rectangle([cx - 30 * s, cy - 36 * s, cx + 30 * s, cy - 25 * s], fill=c)
        d.arc([cx - 46 * s, cy - 34 * s, cx - 18 * s, cy - 6 * s], 90, 270, fill=c, width=int(6 * s))
        d.arc([cx + 18 * s, cy - 34 * s, cx + 46 * s, cy - 6 * s], 270, 90, fill=c, width=int(6 * s))
        d.rectangle([cx - 6 * s, cy + 8 * s, cx + 6 * s, cy + 22 * s], fill=c)
        rr(d, (cx - 24 * s, cy + 22 * s, cx + 24 * s, cy + 36 * s), 4 * s, fill=lerpc(c, ORANGE, 0.5))
    elif kind == "home":  # 家
        d.polygon([(cx - 44 * s, cy - 2 * s), (cx, cy - 40 * s), (cx + 44 * s, cy - 2 * s)], fill=ORANGE)
        d.rectangle([cx - 32 * s, cy - 4 * s, cx + 32 * s, cy + 36 * s], fill=CREAM, outline=NAVY, width=2)
        d.rectangle([cx - 9 * s, cy + 12 * s, cx + 9 * s, cy + 36 * s], fill=(160, 110, 70))
    elif kind == "phone":
        rr(d, (cx - 26 * s, cy - 44 * s, cx + 26 * s, cy + 44 * s), 9 * s, fill=NAVY)
        rr(d, (cx - 21 * s, cy - 36 * s, cx + 21 * s, cy + 34 * s), 4 * s, fill=(235, 245, 255))
        rr(d, (cx - 16 * s, cy - 2 * s, cx + 16 * s, cy + 14 * s), 5 * s, fill=(6, 199, 85))
        text(d, (cx, cy + 6 * s), "LINE", int(11 * s), fill=WHITE, anchor="mm")
        for i in range(3):
            d.line([(cx - 14 * s, cy - 26 * s + i * 7 * s), (cx + 14 * s - i * 6 * s, cy - 26 * s + i * 7 * s)],
                   fill=GRAY, width=max(1, int(3 * s)))
    elif kind == "wear":  # Tシャツと靴
        tc = (80, 170, 230)
        d.polygon([(cx - 40 * s, cy - 30 * s), (cx - 14 * s, cy - 40 * s), (cx, cy - 32 * s), (cx + 14 * s, cy - 40 * s),
                   (cx + 40 * s, cy - 30 * s), (cx + 32 * s, cy - 14 * s), (cx + 22 * s, cy - 18 * s),
                   (cx + 22 * s, cy + 14 * s), (cx - 22 * s, cy + 14 * s), (cx - 22 * s, cy - 18 * s),
                   (cx - 32 * s, cy - 14 * s)], fill=tc)
        rr(d, (cx - 30 * s, cy + 24 * s, cx + 30 * s, cy + 42 * s), 8 * s, fill=WHITE, outline=NAVY, width=2)
        d.rectangle([cx - 30 * s, cy + 36 * s, cx + 30 * s, cy + 42 * s], fill=RED)
    elif kind == "racket":  # ラケット2本とボール
        racket_head(d, cx - 36 * s, cy + 40 * s, math.radians(-75), 1.0 * s, color=COURT)
        racket_head(d, cx + 36 * s, cy + 40 * s, math.radians(-105), 1.0 * s, color=ORANGE)
        ball(d, cx, cy + 26 * s, 12 * s)
    elif kind == "string":  # ガットが張られていく
        fx, fy, rx, ry = cx, cy - 6 * s, 30 * s, 40 * s
        d.line([(cx, cy + 34 * s), (cx, cy + 56 * s)], fill=NAVY, width=int(7 * s))
        p = (t * 0.6) % 1.4
        for i in range(-3, 4):
            x = fx + i * rx / 4
            h = ry * math.sqrt(max(0, 1 - (i / 4) ** 2))
            if (i + 3) / 7 < p:
                d.line([(x, fy - h), (x, fy + h)], fill=(120, 120, 130), width=max(1, int(2 * s)))
        for j in range(-4, 5):
            y = fy + j * ry / 5
            w = rx * math.sqrt(max(0, 1 - (j / 5) ** 2))
            if p > 0.5 + (j + 4) / 18:
                d.line([(fx - w, y), (fx + w, y)], fill=(120, 120, 130), width=max(1, int(2 * s)))
        d.ellipse([fx - rx, fy - ry, fx + rx, fy + ry], outline=RED, width=int(6 * s))
    elif kind == "talk":  # 会話のふきだし
        rr(d, (cx - 50 * s, cy - 40 * s, cx + 14 * s, cy + 2 * s), 14 * s, fill=COURT)
        d.polygon([(cx - 34 * s, cy), (cx - 22 * s, cy), (cx - 38 * s, cy + 16 * s)], fill=COURT)
        rr(d, (cx - 10 * s, cy + 2 * s, cx + 50 * s, cy + 40 * s), 14 * s, fill=ORANGE)
        d.polygon([(cx + 30 * s, cy + 38 * s), (cx + 40 * s, cy + 38 * s), (cx + 42 * s, cy + 54 * s)], fill=ORANGE)
        for k in range(3):
            on = int(t * 3) % 3 >= k
            d.ellipse([cx - 36 * s + k * 15 * s, cy - 24 * s, cx - 28 * s + k * 15 * s, cy - 16 * s],
                      fill=WHITE if on else lerpc(COURT, WHITE, 0.4))
    elif kind == "hit":
        racket_head(d, cx - 30 * s, cy + 36 * s, math.radians(-60), 1.1 * s)
        ball(d, cx + 30 * s + math.sin(t * 4) * 6 * s, cy - 26 * s, 14 * s)


def stars(d, t, seed=0, n=14, color=(255, 255, 255)):
    for i in range(n):
        a = (i * 137.5 + seed * 40) % 360
        x = (i * 271 + seed * 97) % W
        y = (i * 163 + seed * 53) % (H - 160)
        tw = 0.5 + 0.5 * math.sin(t * 3 + i)
        r = 3 + 3 * tw
        d.line([(x - r * 2, y), (x + r * 2, y)], fill=color + (int(80 + 120 * tw),), width=2)
        d.line([(x, y - r * 2), (x, y + r * 2)], fill=color + (int(80 + 120 * tw),), width=2)
        _ = a


# ---------------------------------------------------------------- 各シーン
def rally(d, t, at, near, far, near_s, far_s, arc=120):
    """2人のラリー。near/far はプレーヤーの足元座標。"""
    k = int(t // RALLY)
    p = (t % RALLY) / RALLY
    to_far = k % 2 == 0
    sw_n = 1 - clamp(p * 4) if to_far else clamp((p - 0.75) * 4) * -1
    sw_f = 1 - clamp(p * 4) if not to_far else clamp((p - 0.75) * 4) * -1
    hf = player(d, far[0], far[1], far_s, shirt=(230, 90, 70), swing=sw_f, side=-1, hair=(40, 30, 30))
    a = (near[0] + 36 * near_s, near[1] - 100 * near_s)
    b = (hf[0], hf[1] - 10 * far_s)
    if not to_far:
        a, b = b, a
    q = p
    x = lerp(a[0], b[0], q)
    gy = lerp(a[1] + 100 * (near_s if to_far else far_s), b[1] + 100 * (far_s if to_far else near_s), q)
    y = lerp(a[1], b[1], q) - math.sin(math.pi * q) * arc
    r = lerp(near_s, far_s, q if to_far else 1 - q) * 11
    ball(d, x, y, r, shadow=(x, gy))
    player(d, near[0], near[1], near_s, shirt=(60, 120, 210), swing=sw_n, side=1)


def scene_open(img, d, S, t):
    img.paste(gradient((120, 200, 250), (210, 238, 255)))
    d.ellipse([1040, 40, 1180, 180], fill=(255, 235, 140))
    at = court(d, 330, 760, 640, 520, 1500)
    rally(d, t, at, near=(470, 610), far=(780, 350), near_s=1.45, far_s=0.75)
    p = ease_back(t / 0.9)
    y = lerp(-120, 150, p)
    rr(d, (640 - 430, y - 95, 640 + 430, y + 95), 40, fill=(255, 255, 255, 230))
    q = ease_out((t - 0.6) / 0.6)
    if q > 0:
        text(d, (640, y - 58), CATCH, 30, fill=lerpc(WHITE, NAVY, q), anchor="mm")
    text(d, (640, y + 4), SHOP_NAME, 80, fill=GREEN, anchor="mm", stroke=4, stroke_fill=WHITE)
    if q > 0:
        text(d, (640, y + 64), SHOP_KANA, 28, fill=lerpc(WHITE, ORANGE, q), anchor="mm")
    ball(d, 640 - 370, y + 4, 26)
    ball(d, 640 + 370, y + 4, 26)


def scene_shop(img, d, S, t, sc):
    """店内：大きなテレビでプロの試合、コーヒーでくつろぐ。"""
    img.paste(gradient((250, 238, 220), (232, 212, 185)))
    d.rectangle([0, 520, W, H], fill=(190, 150, 110))
    for x in range(0, W, 80):
        d.line([(x, 520), (x - 60, H)], fill=(175, 135, 98), width=2)
    channel_badge(d)
    text(d, (390, 115), sc["title"], 46, fill=(150, 80, 30), anchor="mm", stroke=3, stroke_fill=WHITE)
    # 大画面テレビ
    tx, ty, tw, th = 80, 160, 620, 340
    rr(d, (tx - 14, ty - 14, tx + tw + 14, ty + th + 14), 16, fill=(30, 32, 38))
    tv = gradient((90, 170, 230), (190, 225, 250)).crop((0, 0, tw, th)).copy()
    dt = ImageDraw.Draw(tv, "RGBA")
    at = court(dt, 70, 380, tw / 2, 240, 900)
    rally(dt, t, at, near=(tw / 2 - 90, 300), far=(tw / 2 + 70, 100), near_s=0.9, far_s=0.5, arc=60)
    rr(dt, (14, 14, 150, 44), 8, fill=(20, 30, 50, 210))
    text(dt, (82, 29), "LIVE  6-4  3-2", 16, fill=WHITE, anchor="mm")
    img.paste(tv, (tx, ty))
    d.rectangle([tx + tw / 2 - 30, ty + th + 14, tx + tw / 2 + 30, ty + th + 34], fill=(50, 52, 60))
    # テーブルとコーヒー
    rr(d, (150, 560, 640, 590), 10, fill=(120, 80, 50))
    d.rectangle([200, 590, 220, 680], fill=(100, 66, 40))
    d.rectangle([570, 590, 590, 680], fill=(100, 66, 40))
    for k, cx in enumerate((300, 470)):
        d.ellipse([cx - 40, 548, cx + 40, 566], fill=WHITE, outline=(200, 190, 180))
        rr(d, (cx - 26, 500, cx + 26, 558), 10, fill=WHITE, outline=(200, 190, 180), width=2)
        d.arc([cx + 16, 512, cx + 44, 542], -90, 90, fill=WHITE, width=7)
        d.ellipse([cx - 22, 498, cx + 22, 510], fill=(110, 70, 40))
        for j in range(2):
            ph = t * 2 + j * 1.3 + k
            pts = [(cx - 8 + j * 14 + math.sin(ph + i * 0.7) * 6, 490 - i * 10) for i in range(5)]
            d.line(pts, fill=(255, 255, 255, int(120 + 60 * math.sin(ph))), width=4, joint="curve")
    # ポイント
    for k, ln in enumerate(sc["lines"]):
        st = S.since(k)
        if st < 0:
            continue
        p = ease_back(st / 0.45)
        x = 770 + (1 - p) * 60
        y = 170 + k * 110
        active = S.current() == k
        rr(d, (x, y, x + 460, y + 86), 43, fill=WHITE, outline=ORANGE if active else (230, 205, 170), width=4)
        check_mark(d, x + 46, y + 43, 26, GREEN)
        for i, l in enumerate(wrap(ln["b"], 30, 360)):
            text(d, (x + 90, y + 43), l, 30, fill=TEXT, anchor="lm")
    # 壁のラケット
    for k, (cx, col) in enumerate(((830, RED), (930, COURT), (1030, ORANGE), (1130, GREEN))):
        d.ellipse([cx - 4, 400, cx + 4, 408], fill=(120, 120, 120))
        racket_head(d, cx, 520, math.radians(-90), 1.25, color=col)


def scene_cards(img, d, S, t, sc):
    img.paste(gradient((235, 248, 240), (205, 235, 215)))
    channel_badge(d)
    text(d, (640, 125), sc["title"], 50, fill=DGREEN, anchor="mm", stroke=3, stroke_fill=WHITE)
    kinds = sc["icons"]
    n = len(kinds)
    cw, ch, gap = 330, 330, 40
    x0 = (W - (n * cw + (n - 1) * gap)) / 2
    for k, ln in enumerate(sc["lines"]):
        st = S.since(k)
        if st < 0:
            continue
        p = ease_back(st / 0.5)
        x = x0 + k * (cw + gap)
        y = 200 + (1 - p) * 80
        active = S.current() == k
        rr(d, (x + 6, y + 8, x + cw + 6, y + ch + 8), 22, fill=(0, 0, 0, 40))
        rr(d, (x, y, x + cw, y + ch), 22, fill=WHITE, outline=ORANGE if active else (210, 225, 215), width=5)
        rr(d, (x, y, x + cw, y + 50), 22, fill=GREEN)
        d.rectangle([x, y + 28, x + cw, y + 50], fill=GREEN)
        text(d, (x + cw / 2, y + 26), f"POINT {k + 1}", 24, fill=WHITE, anchor="mm")
        icon(d, kinds[k], x + cw / 2, y + 145, 1.4, t)
        for i, l in enumerate(wrap(ln["b"], 30, cw - 30)):
            text(d, (x + cw / 2, y + 250 + i * 40), l, 30, fill=TEXT, anchor="mm")


def burst(img, t, c1, c2, cx=640, cy=330):
    layer = Image.new("RGB", (W, H), c1)
    d = ImageDraw.Draw(layer)
    n = 18
    rot = t * 12
    for i in range(n):
        a0 = math.radians(rot + i * 360 / n)
        a1 = math.radians(rot + (i + 0.5) * 360 / n)
        R = 1600
        d.polygon([(cx, cy), (cx + math.cos(a0) * R, cy + math.sin(a0) * R), (cx + math.cos(a1) * R, cy + math.sin(a1) * R)],
                  fill=c2)
    img.paste(layer)


def scene_recruit(img, d, S, t):
    burst(img, t, (255, 200, 50), (255, 222, 110))
    d2 = d
    # 小さなボールが飛び回る
    for i in range(6):
        ph = t * 1.2 + i * 1.05
        x = (i * 230 + t * 160) % (W + 100) - 50
        y = 120 + abs(math.sin(ph * 2)) * -80 + (i % 3) * 190
        ball(d2, x, y + 80, 16)
    s1 = S.since(1)
    if s1 < 0:
        p = ease_back(t / 0.6)
        text(d, (640, 330), "お知らせ", int(110 * p) + 1, fill=WHITE, anchor="mm", stroke=8, stroke_fill=ORANGE)
        return
    p = ease_back(s1 / 0.6)
    rr(d, (640 - 520 * p, 150, 640 + 520 * p, 470), 40, fill=WHITE, outline=ORANGE, width=8)
    if p > 0.6:
        text(d, (640, 225), f"{SHOP_NAME} テニススクール", 56, fill=GREEN, anchor="mm")
        text(d, (640, 340), "生徒募集中！", 120, fill=RED, anchor="mm", stroke=5, stroke_fill=WHITE)
    s2 = S.since(2)
    if s2 >= 0:
        q = ease_back(s2 / 0.5)
        wobble = math.sin(t * 6) * 2
        y = 540
        bw = 360 * q
        rr(d, (640 - bw, y - 50, 640 + bw, y + 50), 50, fill=GREEN, outline=WHITE, width=5)
        if q > 0.7:
            text(d, (640, y + wobble), "見学・体験 お気軽に！", 52, fill=WHITE, anchor="mm")


def coach_scene(d, t, x0, y0):
    """コーチがやさしく球出しして、生徒が打つ。"""
    rr(d, (x0, y0, x0 + 520, y0 + 380), 30, fill=(205, 235, 215))
    d.rectangle([x0 + 20, y0 + 250, x0 + 500, y0 + 360], fill=COURT)
    d.line([(x0 + 20, y0 + 250), (x0 + 500, y0 + 250)], fill=WHITE, width=4)
    d.rectangle([x0 + 255, y0 + 205, x0 + 265, y0 + 300], fill=(60, 60, 60))
    for i in range(6):
        d.line([(x0 + 248, y0 + 210 + i * 15), (x0 + 272, y0 + 210 + i * 15)], fill=WHITE, width=2)
    period = 2.0
    p = (t % period) / period
    sw = -1 + clamp((p - 0.55) * 6) * 2 if p > 0.55 else -1
    sw = 1 - clamp((p - 0.55) * 5) * 2 if p > 0.55 else 1
    player(d, x0 + 130, y0 + 330, 1.3, shirt=(255, 120, 150), swing=sw, side=1, hair=(90, 60, 30))
    player(d, x0 + 400, y0 + 330, 1.25, shirt=NAVY, swing=0.2, side=-1, hair=(30, 30, 30))
    text(d, (x0 + 400, y0 + 155), "COACH", 18, fill=NAVY, anchor="mm")
    if p < 0.6:
        q = p / 0.6
        bx = lerp(x0 + 360, x0 + 190, q)
        by = lerp(y0 + 220, y0 + 220, q) - math.sin(math.pi * q) * 90
    else:
        q = (p - 0.6) / 0.4
        bx = lerp(x0 + 190, x0 + 470, q)
        by = y0 + 220 - math.sin(math.pi * q) * 120
    ball(d, bx, by, 11)
    if 0.62 < p < 0.95:
        rr(d, (x0 + 300, y0 + 30, x0 + 500, y0 + 90), 20, fill=WHITE, outline=ORANGE, width=3)
        d.polygon([(x0 + 390, y0 + 88), (x0 + 410, y0 + 88), (x0 + 400, y0 + 110)], fill=WHITE)
        text(d, (x0 + 400, y0 + 60), "ナイスショット！", 24, fill=ORANGE, anchor="mm")


def scene_easy(img, d, S, t, sc):
    img.paste(gradient((255, 250, 230), (255, 236, 200)))
    channel_badge(d)
    text(d, (360, 130), sc["title"], 54, fill=ORANGE, anchor="mm", stroke=3, stroke_fill=WHITE)
    for k, ln in enumerate(sc["lines"]):
        st = S.since(k)
        if st < 0:
            continue
        p = ease_back(st / 0.45)
        y = 200 + k * 98
        x = 60 - (1 - p) * 60
        active = S.current() == k
        rr(d, (x, y, x + 600, y + 80), 40, fill=WHITE, outline=ORANGE if active else (240, 215, 170), width=4)
        check_mark(d, x + 44, y + 40, 26, GREEN)
        text(d, (x + 88, y + 40), ln["b"], 36, fill=TEXT, anchor="lm")
    coach_scene(d, t, 700, 180)


def scene_flow(img, d, S, t, sc):
    img.paste(gradient((225, 240, 255), (200, 225, 250)))
    channel_badge(d)
    text(d, (640, 125), sc["title"], 52, fill=COURT, anchor="mm", stroke=3, stroke_fill=WHITE)
    kinds = ["phone", "wear", "hit"]
    cw, ch = 320, 330
    gap = (W - 3 * cw) / 4
    for k in range(3):
        st = S.since(k + 1)
        if st < 0:
            continue
        ln = sc["lines"][k + 1]
        p = ease_back(st / 0.5)
        x = gap + k * (cw + gap)
        y = 200
        s = 0.6 + 0.4 * p
        cx, cy = x + cw / 2, y + ch / 2
        bw, bh = cw * s, ch * s
        active = S.current() == k + 1
        rr(d, (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2), 26, fill=WHITE,
           outline=ORANGE if active else (190, 210, 235), width=5)
        if p > 0.7:
            d.ellipse([cx - 32, y + 18, cx + 32, y + 82], fill=COURT)
            text(d, (cx, y + 50), str(k + 1), 40, fill=WHITE, anchor="mm")
            icon(d, kinds[k], cx, y + 170, 1.3, t)
            for i, l in enumerate(wrap(ln["b"], 28, cw - 40)):
                text(d, (cx, y + 270 + i * 38), l, 28, fill=TEXT, anchor="mm")
        if k < 2 and S.since(k + 2) >= 0:
            ax = x + cw + gap / 2
            d.polygon([(ax - 16, cy - 22), (ax + 18, cy), (ax - 16, cy + 22)], fill=ORANGE)


def scene_cta(img, d, S, t):
    img.paste(gradient((60, 160, 100), (30, 110, 70)))
    stars(d, t, 7, n=10)
    at = court(d, 470, 780, 640, 700, 1700)
    rally(d, t + 0.3, at, near=(330, 650), far=(960, 520), near_s=1.1, far_s=0.6, arc=90)
    p = ease_back(t / 0.7)
    text(d, (640, 70), "テニスのことなら", int(44 * p) + 1, fill=WHITE, anchor="mm", stroke=3, stroke_fill=DGREEN)
    text(d, (640, 145), SHOP_NAME, int(84 * p) + 1, fill=YELLOW, anchor="mm", stroke=5, stroke_fill=DGREEN)
    s1 = S.since(1)
    if s1 >= 0:
        q = ease_back(s1 / 0.5)
        bw, bh = 760 * q, 230 * q
        rr(d, (640 - bw / 2, 330 - bh / 2, 640 + bw / 2, 330 + bh / 2), 30, fill=(255, 255, 255, 240),
           outline=ORANGE, width=5)
        if q > 0.8:
            rr(d, (300, 228, 980, 276), 24, fill=RED)
            text(d, (640, 252), "テニススクール 生徒募集中！", 32, fill=WHITE, anchor="mm")
            text(d, (640, 306), ADDRESS, 30, fill=TEXT, anchor="mm")
            text(d, (640, 350), f"TEL {TEL}", 34, fill=NAVY, anchor="mm")
            pulse = 1 + 0.03 * math.sin(t * 7)
            lw, lh = 560 * pulse, 46 * pulse
            rr(d, (640 - lw / 2, 400 - lh / 2, 640 + lw / 2, 400 + lh / 2), lh / 2, fill=(6, 199, 85))
            text(d, (640, 400), "ご来店・お問い合わせは事前にLINEで", 26, fill=WHITE, anchor="mm")


def draw_subtitle(img, d, S, sc):
    k = S.current()
    if k < 0:
        return
    st = S.since(k)
    if st > S.durs[k] + 0.35:
        return
    lines = wrap(sc["lines"][k]["t"], 32, 1100)
    h = 20 + 46 * len(lines)
    y0 = H - 22 - h
    rr(d, (640 - 590, y0, 640 + 590, H - 22), 20, fill=(15, 25, 40, 200))
    for i, l in enumerate(lines):
        text(d, (640, y0 + 33 + i * 46), l, 32, fill=WHITE, anchor="mm")


def render_frame(sc, S, t, gt, total):
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img, "RGBA")
    key = sc["key"]
    if key == "open":
        scene_open(img, d, S, t)
    elif key == "shop":
        scene_shop(img, d, S, t, sc)
    elif key == "items":
        scene_cards(img, d, S, t, sc)
    elif key == "recruit":
        scene_recruit(img, d, S, t)
    elif key == "easy":
        scene_easy(img, d, S, t, sc)
    elif key == "flow":
        scene_flow(img, d, S, t, sc)
    elif key == "cta":
        scene_cta(img, d, S, t)
    draw_subtitle(img, d, S, sc)
    # シーンの切り替わりで白くフェード
    fade = clamp(1 - t / 0.25)
    if fade > 0 and gt > 0.3:
        img = Image.blend(img, Image.new("RGB", (W, H), WHITE), fade * 0.8)
    if gt < 0.4:
        img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), 1 - gt / 0.4)
    if total - gt < 1.0:
        img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), clamp(1 - (total - gt)))
    return img


# ---------------------------------------------------------------- 音声
def note_freq(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def sfx_pop():
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    f = 500 + 900 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22) * 0.25


def sfx_hit():
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(1)
    s = rng.standard_normal(n) * np.exp(-t * 90) * 0.5 + np.sin(2 * np.pi * 900 * t) * np.exp(-t * 60)
    return s * 0.18


def sfx_whoosh():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(2)
    s = rng.standard_normal(n)
    s = np.convolve(s, np.ones(8) / 8, mode="same")
    return s * np.sin(np.pi * t / t[-1]) ** 2 * 0.12


def sfx_fanfare():
    out = np.zeros(int(1.4 * SR))
    for i, (m, at, ln) in enumerate([(72, 0.0, 0.14), (76, 0.14, 0.14), (79, 0.28, 0.14), (84, 0.42, 0.9)]):
        n = int(ln * SR)
        t = np.arange(n) / SR
        f = note_freq(m)
        tone = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.2 * np.sin(6 * np.pi * f * t))
        tone *= np.minimum(1, t * 80) * np.exp(-t * (2.0 if i == 3 else 6.0)) * 0.16
        a = int(at * SR)
        out[a:a + n] += tone
    return out


def bgm(total):
    """明るいアップテンポのBGM（C - G - Am - F、120BPM）。左右2ch を返す。"""
    n = int(total * SR) + SR
    left, right = np.zeros(n), np.zeros(n)
    beat = 0.5
    bar = beat * 4
    chords = [(60, 64, 67), (55, 59, 62), (57, 60, 64), (53, 57, 60)]
    rng = np.random.default_rng(0)

    def add(sig, at, pan=0.0):
        a = int(at * SR)
        if a >= n:
            return
        e = min(n, a + len(sig))
        left[a:e] += sig[:e - a] * (1 - pan)
        right[a:e] += sig[:e - a] * (1 + pan)

    kl = int(0.3 * SR)
    kt = np.arange(kl) / SR
    kick = np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-kt * 30)) / SR) * np.exp(-kt * 12) * 0.22
    sl = int(0.2 * SR)
    st = np.arange(sl) / SR
    snare = (rng.standard_normal(sl) * 0.6 + np.sin(2 * np.pi * 190 * st)) * np.exp(-st * 20) * 0.07
    hl = int(0.05 * SR)
    ht = np.arange(hl) / SR
    hat = np.diff(rng.standard_normal(hl + 1)) * np.exp(-ht * 90) * 0.03
    nl = int(beat * 0.5 * SR)
    nt = np.arange(nl) / SR
    i = 0
    while i * bar < total + 1:
        ch = chords[i % 4]
        b0 = i * bar
        for bt in range(4):
            at = b0 + bt * beat
            add(kick if bt % 2 == 0 else snare, at)
            add(hat, at + beat / 2, 0.3)
            add(hat * 0.6, at, -0.3)
            # ベース（8分）
            for h in range(2):
                f = note_freq(ch[0] - 24 + (12 if h else 0))
                bass = (np.sin(2 * np.pi * f * nt) + 0.3 * np.sin(4 * np.pi * f * nt)) * np.exp(-nt * 6) * 0.09
                add(bass, at + h * beat / 2)
            # 裏拍のコード
            cl = int(beat * 0.45 * SR)
            ct = np.arange(cl) / SR
            stab = sum(np.sin(2 * np.pi * note_freq(m) * ct) + 0.3 * np.sin(4 * np.pi * note_freq(m) * ct)
                       for m in ch) * np.exp(-ct * 9) * np.minimum(1, ct * 200) * 0.028
            add(stab, at + beat / 2, 0.2 if bt % 2 else -0.2)
        # メロディ（4小節で一回り）
        mel = [[76, 79, 84, 83], [79, 74, 79, 81], [81, 84, 83, 79], [77, 81, 79, 76]][i % 4]
        for j, m in enumerate(mel):
            ml = int(beat * 0.9 * SR)
            mt = np.arange(ml) / SR
            f = note_freq(m)
            tone = (np.sin(2 * np.pi * f * mt) + 0.2 * np.sin(4 * np.pi * f * mt)) * np.exp(-mt * 4) * np.minimum(1, mt * 150) * 0.03
            add(tone, b0 + j * beat, 0.15)
        i += 1
    fade = np.ones(n)
    k = int(1.0 * SR)
    fade[:k] = np.linspace(0, 1, k)
    end = int(total * SR)
    fade[end - 3 * k:end] = np.linspace(1, 0, 3 * k)
    fade[end:] = 0
    return left * fade, right * fade


def build_timeline():
    """全セリフを音声合成し、シーンごとの開始時刻と音声トラックを作る。"""
    LEAD, GAP, TAIL = 0.7, 0.3, 0.8
    voice_parts, sfx_parts = [], []
    timeline = []
    cur = 0.0
    for si, sc in enumerate(SCENES):
        start = cur
        key = sc["key"]
        lead = {"open": 1.4, "recruit": 0.6}.get(key, LEAD)
        if key == "recruit":
            sfx_parts.append((start + 0.05, sfx_fanfare()))
        elif key != "open":
            sfx_parts.append((start, sfx_whoosh()))
        pos = start + lead
        starts, durs = [], []
        for li, ln in enumerate(sc["lines"]):
            x, sr = pyopenjtalk.tts(ln.get("r", ln["t"]), speed=1.05, half_tone=1.0)
            x = x.astype(np.float64)
            if sr != SR:
                idx = np.arange(0, len(x), sr / SR)
                x = np.interp(idx, np.arange(len(x)), x)
            x = x / (np.abs(x).max() + 1e-9) * 0.85
            starts.append(pos - start)
            durs.append(len(x) / SR)
            voice_parts.append((pos, x))
            if "b" in ln or key in ("recruit", "cta") and li > 0:
                sfx_parts.append((pos, sfx_pop()))
            pos += len(x) / SR + GAP
        end = pos + (2.2 if si == len(SCENES) - 1 else TAIL)
        if key in ("open", "cta"):
            off = 0.0 if key == "open" else 0.3
            k = 1
            while (k * RALLY - off) < end - start:
                if k * RALLY - off > 0:
                    sfx_parts.append((start + k * RALLY - off, sfx_hit()))
                k += 1
        timeline.append((start, end - start, starts, durs))
        cur = end
        print(f"  {key}: {end - start:.1f}秒", flush=True)
    total = cur
    n = int(total * SR) + SR
    voice, fx = np.zeros(n), np.zeros(n)
    for at, s in voice_parts:
        a = int(at * SR)
        voice[a:a + len(s)] += s[:n - a]
    for at, s in sfx_parts:
        a = int(at * SR)
        fx[a:a + len(s)] += s[:n - a]
    # 話している間はBGMを小さくする（ダッキング）
    win = int(0.05 * SR)
    env = np.convolve(np.abs(voice), np.ones(win) / win, mode="same")
    active = np.convolve((env > 0.02).astype(float), np.ones(int(0.5 * SR)) / int(0.5 * SR), mode="same")
    duck = 1.0 - 0.55 * np.clip(active * 3, 0, 1)
    bl, br = bgm(total)
    stereo = np.stack([voice + fx + bl * duck, voice + fx + br * duck], axis=1)
    stereo = np.clip(stereo, -1, 1)
    return timeline, total, (stereo * 32767).astype(np.int16)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "tennis_channel_promo.mp4")
    print("音声を合成中…")
    timeline, total, track = build_timeline()
    wav_path = os.path.splitext(out)[0] + "_audio.wav"
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(track.tobytes())
    nframes = int(math.ceil(total * FPS))
    print(f"映像を生成中… 全{total:.1f}秒 / {nframes}フレーム")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav_path, "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-c:a", "aac",
           "-b:a", "192k", "-movflags", "+faststart", "-shortest", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    si = 0
    for fi in range(nframes):
        gt = fi / FPS
        while si + 1 < len(timeline) and gt >= timeline[si + 1][0]:
            si += 1
        start, _, starts, durs = timeline[si]
        S = Timer(starts, durs, gt - start)
        frame = render_frame(SCENES[si], S, S.t, gt, total)
        proc.stdin.write(frame.tobytes())
        if fi % (FPS * 15) == 0:
            print(f"  {gt:6.1f}秒", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav_path)
    print("完成:", out)


if __name__ == "__main__":
    main()
