#!/usr/bin/env python3
"""「はじめての飛行機 乗り方ガイド」動画を生成するスクリプト。

必要なもの: Python 3, Pillow, numpy, pyopenjtalk, ffmpeg, IPAゴシックフォント
使い方:    python3 make_video.py [出力ファイル名]
"""
import math
import os
import random
import subprocess
import sys
import wave
from functools import lru_cache

import numpy as np
import pyopenjtalk
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FPS = 24
SR = 48000
FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
HERE = os.path.dirname(os.path.abspath(__file__))

NAVY = (27, 42, 74)
SKY = (79, 163, 224)
ORANGE = (245, 150, 35)
BG = (234, 242, 250)
WHITE = (255, 255, 255)
TEXT = (40, 48, 64)
GRAY = (150, 160, 175)
LIGHT = (220, 230, 242)
RED = (220, 55, 55)
GREEN = (60, 175, 95)
SKIN = (245, 205, 170)

# カード（左側のイラスト領域）
CX, CY, CW, CH = 40, 100, 600, 490


# ---------------------------------------------------------------- 台本
# 各シーン: key=イラスト関数, step=STEP番号, title=見出し,
# lines=[{t:字幕, r:読み(任意), b:ポイント(任意)}]
SCENES = [
    dict(key="title", step=None, title="", lines=[
        dict(t="はじめて飛行機に乗るあなたへ。"),
        dict(t="空港に着いてから、目的地に到着するまでの流れを、順番にわかりやすく説明します。"),
    ]),
    dict(key="prep", step=1, title="出発前の準備", lines=[
        dict(t="まずは、出発前の準備です。"),
        dict(t="予約した便名と出発時刻を確認しておきましょう。eチケットは、スマートフォンに保存しておくと便利です。",
             r="予約した便名と出発時刻を確認しておきましょう。イーチケットは、スマートフォンに保存しておくと便利です。",
             b="便名・出発時刻を確認（eチケットはスマホに保存）"),
        dict(t="国際線に乗るときは、パスポートが必ず必要です。", b="国際線はパスポートが必須"),
        dict(t="空港には、国内線なら出発の1時間前、国際線なら2時間から3時間前に着くと安心です。",
             r="空港には、国内線なら出発の一時間前、国際線なら二時間から三時間前に着くと安心です。",
             b="空港へは 国内線1時間前／国際線2〜3時間前"),
    ]),
    dict(key="checkin", step=2, title="チェックイン", lines=[
        dict(t="空港に着いたら、航空会社のカウンターか、自動チェックイン機でチェックインします。",
             b="カウンターか自動チェックイン機で手続き"),
        dict(t="スマートフォンのアプリやウェブサイトで、事前にチェックインすることもできます。",
             b="スマホで事前にチェックインもできる"),
        dict(t="搭乗券には、便名、搭乗ゲート、座席番号などが書かれています。",
             b="搭乗券で便名・ゲート・座席を確認"),
    ]),
    dict(key="baggage", step=3, title="荷物を預ける", lines=[
        dict(t="スーツケースなどの大きな荷物は、カウンターで預けます。", b="大きな荷物はカウンターで預ける"),
        dict(t="モバイルバッテリーやライターは、預ける荷物には入れられません。機内に持ち込む手荷物に入れましょう。",
             b="モバイルバッテリー・ライターは手荷物へ"),
        dict(t="財布などの貴重品や、いつも飲んでいる薬も、手元に持っておきましょう。", b="貴重品・薬は手元に"),
    ]),
    dict(key="security", step=4, title="保安検査", lines=[
        dict(t="次は、保安検査場です。"),
        dict(t="手荷物とスマートフォン、鍵や小銭などの金属類をトレーに乗せて、X線検査に通します。",
             r="手荷物とスマートフォン、鍵や小銭などの金属類をトレーに乗せて、エックス線検査に通します。",
             b="手荷物・スマホ・金属類はトレーへ"),
        dict(t="そのあと、金属探知機のゲートをくぐります。", b="金属探知機のゲートをくぐる"),
        dict(t="国際線では、液体は100ml以下の容器に入れ、透明な袋にまとめます。",
             r="国際線では、液体は百ミリリットル以下の容器に入れ、透明な袋にまとめます。",
             b="国際線の液体は100ml以下の容器で透明な袋に"),
        dict(t="刃物や、一部のスプレー缶などは持ち込めないので、事前に確認しておきましょう。",
             b="刃物・一部のスプレー類は持ち込めない"),
        dict(t="国際線の場合は、このあと出国審査で、パスポートを見せます。", b="国際線はこのあと出国審査"),
    ]),
    dict(key="gate", step=5, title="搭乗ゲートへ", lines=[
        dict(t="保安検査を通ったら、搭乗券に書かれた番号の搭乗ゲートへ向かいます。", b="搭乗券に書かれたゲートへ"),
        dict(t="国内線なら出発時刻の20分前までに、国際線ならさらに早めに、ゲートに着いておきましょう。",
             r="国内線なら出発時刻の二十分前までに、国際線ならさらに早めに、ゲートに着いておきましょう。",
             b="国内線は出発20分前までにゲートへ"),
        dict(t="ゲートが変更になることもあるので、案内表示やアナウンスを確認してください。",
             b="ゲート変更に注意（案内表示・放送）"),
        dict(t="搭乗が始まったら、案内された順番で、搭乗券のQRコードを読み取り機にかざして進みます。",
             r="搭乗が始まったら、案内された順番で、搭乗券のキューアールコードを読み取り機にかざして進みます。",
             b="順番が来たらQRコードをかざして搭乗"),
    ]),
    dict(key="seat", step=6, title="座席に着く", lines=[
        dict(t="機内に入ったら、搭乗券に書かれた座席を探します。"),
        dict(t="数字が列、アルファベットが席の位置です。例えば23Aなら、23列目のA席です。",
             r="数字が列、アルファベットが席の位置です。例えば、にじゅうさんエーなら、にじゅうさん列目の、エー席です。",
             b="数字＝列、アルファベット＝席（例：23A）"),
        dict(t="列の番号は、頭上の荷物入れや、座席の横に書かれています。", b="列番号は頭上の棚などに表示"),
        dict(t="荷物は、頭上の棚か、前の座席の下に置きます。", b="荷物は頭上の棚か前の座席の下へ"),
        dict(t="座ったら、シートベルトを腰の低い位置で、しっかり締めましょう。", b="シートベルトは腰の低い位置で"),
    ]),
    dict(key="takeoff", step=7, title="離陸の前に", lines=[
        dict(t="出発の前に、スマートフォンは機内モードに切り替えます。", b="スマホは機内モードに"),
        dict(t="離着陸のときは、座席の背もたれを元の位置に戻し、テーブルをしまいます。",
             b="背もたれを戻し、テーブルをしまう"),
        dict(t="非常口や酸素マスクの使い方を説明する、安全のビデオもしっかり見ておきましょう。",
             b="安全のビデオ（非常口・酸素マスク）を見る"),
        dict(t="飛行機は滑走路へ移動して、いよいよ離陸です。"),
    ]),
    dict(key="flight", step=8, title="飛行中", lines=[
        dict(t="シートベルト着用サインが消えたら、トイレに行くことができます。", b="ベルトサインが消えたらトイレOK"),
        dict(t="揺れることもあるので、座っている間はベルトを締めておくと安心です。", b="座っている間はベルトを締めておく"),
        dict(t="飲み物のサービスがあります。国際線では機内食も出ます。", b="飲み物のサービス（国際線は機内食も）"),
        dict(t="気圧の変化で耳が痛くなったら、あくびをしたり、つばを飲み込んだりしてみましょう。",
             b="耳が痛い時は、あくび・つばを飲み込む"),
        dict(t="困ったときは、座席の呼び出しボタンで客室乗務員を呼べます。", b="困ったら呼び出しボタン"),
    ]),
    dict(key="arrive", step=9, title="到着", lines=[
        dict(t="着陸して飛行機が完全に止まり、シートベルト着用サインが消えるまでは、席に座ったまま待ちましょう。",
             b="完全に止まりサインが消えるまで着席"),
        dict(t="降りる前に、座席のポケットや頭上の棚に、忘れ物がないか確認します。", b="座席ポケット・棚の忘れ物チェック"),
        dict(t="飛行機を降りたら、案内に従って手荷物受取所へ向かいます。"),
        dict(t="預けた荷物は、ターンテーブルから受け取ります。似たかばんも多いので、目印をつけておくと便利です。",
             b="預けた荷物はターンテーブルで受け取る"),
        dict(t="国際線の場合は、入国審査と税関を通ってから、到着ロビーに出ます。", b="国際線は入国審査・税関のあと出口へ"),
    ]),
    dict(key="summary", step=None, title="まとめ", lines=[
        dict(t="最後に、流れをおさらいしましょう。"),
        dict(t="出発前の準備、チェックイン、荷物を預ける、保安検査、搭乗ゲート、座席に着く、離陸の前に、飛行中、そして到着です。"),
        dict(t="時間や持ち込みのルールは、航空会社や路線によって異なります。必ず、利用する航空会社の案内を確認してください。"),
        dict(t="わからないことがあれば、空港のスタッフや客室乗務員に、遠慮なく聞いてみてください。"),
        dict(t="それでは、よい空の旅を！"),
    ]),
]

STEP_NAMES = ["準備", "チェックイン", "荷物を預ける", "保安検査", "搭乗ゲート", "座席へ", "離陸の前に", "飛行中", "到着"]


# ---------------------------------------------------------------- 汎用
@lru_cache(maxsize=None)
def F(size):
    return ImageFont.truetype(FONT_PATH, size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


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


def text(d, xy, s, size, fill=TEXT, anchor="la", bold=False):
    d.text(xy, s, font=F(size), fill=fill, anchor=anchor,
           stroke_width=1 if bold else 0, stroke_fill=fill)


def wrap(s, size, maxw):
    font = F(size)
    lines, cur = [], ""
    for ch in s:
        if font.getlength(cur + ch) > maxw and cur and ch not in "。、）」！？ー・":
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


def gradient(w, h, top, bottom):
    t = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t)
    arr = np.repeat(arr, w, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


class Timer:
    """シーン内の各セリフの開始時刻・長さを扱う。"""

    def __init__(self, starts, durs):
        self.starts, self.durs = starts, durs

    def since(self, k):
        return self.t - self.starts[k]

    def dur(self, k):
        return self.durs[k]

    def current(self):
        cur = -1
        for k, st in enumerate(self.starts):
            if self.t >= st:
                cur = k
        return cur


# ---------------------------------------------------------------- 部品
def person(d, x, y, s=1.0, color=(70, 110, 190), phase=None):
    """y は足元。phase を与えると歩くアニメーション。"""
    a = math.sin(phase) * 0.45 if phase is not None else 0.0
    hip = (x, y - 34 * s)
    lw = max(3, int(9 * s))
    for sign in (1, -1):
        ang = a * sign
        d.line([hip, (x + math.sin(ang) * 34 * s, hip[1] + math.cos(ang) * 33 * s)], fill=NAVY, width=lw)
    sh = (x, y - 68 * s)
    for sign in (1, -1):
        ang = -a * sign
        d.line([sh, (x + math.sin(ang) * 30 * s, sh[1] + math.cos(ang) * 30 * s)], fill=color, width=lw)
    rr(d, (x - 15 * s, y - 74 * s, x + 15 * s, y - 30 * s), 10 * s, fill=color)
    d.ellipse([x - 14 * s, y - 104 * s, x + 14 * s, y - 76 * s], fill=SKIN)
    d.pieslice([x - 14 * s, y - 106 * s, x + 14 * s, y - 80 * s], 180, 360, fill=(70, 50, 40))


def suitcase(d, cx, bottom, w, h, color=ORANGE):
    x0, y0 = cx - w / 2, bottom - h
    d.rounded_rectangle([cx - w * 0.2, y0 - h * 0.16, cx + w * 0.2, y0 + 6], radius=6, outline=NAVY, width=5)
    rr(d, (x0, y0, x0 + w, bottom - h * 0.06), w * 0.12, fill=color, outline=lerpc(color, NAVY, 0.4), width=3)
    for fx in (0.3, 0.7):
        d.line([(x0 + w * fx, y0 + 8), (x0 + w * fx, bottom - h * 0.1)], fill=lerpc(color, NAVY, 0.3), width=4)
    for fx in (0.2, 0.8):
        d.ellipse([x0 + w * fx - 7, bottom - 14, x0 + w * fx + 7, bottom], fill=NAVY)


def cloud(d, x, y, s=1.0, color=WHITE):
    d.ellipse([x - 50 * s, y - 20 * s, x + 10 * s, y + 25 * s], fill=color)
    d.ellipse([x - 20 * s, y - 42 * s, x + 40 * s, y + 20 * s], fill=color)
    d.ellipse([x + 15 * s, y - 25 * s, x + 70 * s, y + 25 * s], fill=color)
    rr(d, (x - 50 * s, y, x + 70 * s, y + 25 * s), 12 * s, fill=color)


@lru_cache(maxsize=None)
def plane_img(L):
    im = Image.new("RGBA", (L, L // 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = L
    d.polygon([(0.06 * u, 0.27 * u), (0.02 * u, 0.05 * u), (0.11 * u, 0.05 * u), (0.24 * u, 0.27 * u)], fill=SKY)
    rr(d, (0.03 * u, 0.25 * u, 0.97 * u, 0.385 * u), 0.065 * u, fill=WHITE, outline=(170, 180, 195), width=max(1, L // 150))
    d.polygon([(0.03 * u, 0.25 * u), (0.12 * u, 0.25 * u), (0.12 * u, 0.30 * u), (0.03 * u, 0.32 * u)], fill=WHITE)
    d.line([(0.10 * u, 0.355 * u), (0.94 * u, 0.355 * u)], fill=SKY, width=max(2, L // 60))
    for i in range(18):
        wx = 0.24 * u + i * 0.034 * u
        r = 0.009 * u
        d.ellipse([wx - r, 0.29 * u - r, wx + r, 0.29 * u + r], fill=(70, 120, 180))
    d.polygon([(0.88 * u, 0.275 * u), (0.935 * u, 0.275 * u), (0.955 * u, 0.30 * u), (0.88 * u, 0.30 * u)], fill=NAVY)
    d.polygon([(0.07 * u, 0.31 * u), (0.19 * u, 0.31 * u), (0.07 * u, 0.36 * u), (0.03 * u, 0.36 * u)], fill=(120, 170, 220))
    d.ellipse([0.42 * u, 0.375 * u, 0.53 * u, 0.43 * u], fill=(140, 150, 165))
    d.polygon([(0.40 * u, 0.34 * u), (0.60 * u, 0.34 * u), (0.42 * u, 0.48 * u), (0.34 * u, 0.48 * u)], fill=(195, 205, 220))
    return im


def draw_plane(img, cx, cy, L, angle=0.0):
    p = plane_img(int(L))
    if angle:
        p = p.rotate(angle, expand=True, resample=Image.BICUBIC)
    img.paste(p, (int(cx - p.width / 2), int(cy - p.height / 2)), p)


def no_sign(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=RED, width=max(4, int(r * 0.15)))
    k = r * 0.7
    d.line([(cx - k, cy - k), (cx + k, cy + k)], fill=RED, width=max(4, int(r * 0.15)))


def check_mark(d, cx, cy, r, color=GREEN):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    d.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)], fill=WHITE,
           width=max(3, int(r * 0.22)), joint="curve")


def qr(d, x, y, size, seed=1):
    rnd = random.Random(seed)
    n = 9
    c = size / n
    d.rectangle([x, y, x + size, y + size], fill=WHITE)
    for i in range(n):
        for j in range(n):
            corner = (i < 3 and j < 3) or (i > 5 and j < 3) or (i < 3 and j > 5)
            if corner:
                on = not (i % 3 == 1 and j % 3 == 1) if (i in (0, 1, 2, 6, 7, 8) and j in (0, 1, 2, 6, 7, 8)) else False
            else:
                on = rnd.random() < 0.5
            if on:
                d.rectangle([x + i * c, y + j * c, x + (i + 1) * c - 1, y + (j + 1) * c - 1], fill=NAVY)


def phone(d, cx, cy, w, h, screen=(235, 245, 255)):
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), w * 0.16, fill=NAVY)
    rr(d, (cx - w / 2 + 7, cy - h / 2 + 16, cx + w / 2 - 7, cy + h / 2 - 16), w * 0.08, fill=screen)
    return (cx - w / 2 + 7, cy - h / 2 + 16, cx + w / 2 - 7, cy + h / 2 - 16)


def callout(cimg, box, p, fill=WHITE, border=SKY):
    """ポップアップするカード。p=0..1 の出現度。描画先 ImageDraw とスケール済み box を返す。"""
    if p <= 0:
        return None
    s = ease_back(p)
    x0, y0, x1, y1 = box
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    bx = (mx - (mx - x0) * s, my - (my - y0) * s, mx + (x1 - mx) * s, my + (y1 - my) * s)
    d = ImageDraw.Draw(cimg)
    rr(d, (bx[0] + 5, bx[1] + 7, bx[2] + 5, bx[3] + 7), 18, fill=(200, 210, 225))
    rr(d, bx, 18, fill=fill, outline=border, width=4)
    return d, s


# ---------------------------------------------------------------- 各シーンのイラスト
SKY_CARD = gradient(CW, CH, (120, 185, 240), (215, 236, 252))
TITLE_BG = gradient(W, H, (90, 165, 230), (225, 242, 255))


def illus_prep(cimg, d, t, S):
    items = [
        (1, 125, 230, "eチケット"),
        (2, 300, 220, "パスポート"),
        (3, 470, 150, "時間に余裕を"),
        (3, 465, 390, "荷物"),
    ]
    for k, x, y, label in items:
        p = S.since(k) / 0.55
        if p <= 0:
            d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=LIGHT)
            continue
        s = ease_back(p)
        if label == "eチケット":
            sc = phone(d, x, y, 120 * s, 230 * s)
            if s > 0.5:
                text(d, (x, sc[1] + 22 * s), "eチケット", int(18 * s), NAVY, "mm", True)
                qr(d, x - 40 * s, y - 30 * s, 80 * s)
                text(d, (x, y + 70 * s), "AB 123", int(16 * s), TEXT, "mm")
        elif label == "パスポート":
            rr(d, (x - 70 * s, y - 95 * s, x + 70 * s, y + 95 * s), 12 * s, fill=(125, 30, 45))
            gold = (230, 190, 90)
            d.ellipse([x - 30 * s, y - 50 * s, x + 30 * s, y + 10 * s], outline=gold, width=max(1, int(4 * s)))
            for i in range(8):
                a = i * math.pi / 4
                d.line([(x, y - 20 * s), (x + math.cos(a) * 26 * s, y - 20 * s + math.sin(a) * 26 * s)],
                       fill=gold, width=max(1, int(2 * s)))
            if s > 0.5:
                text(d, (x, y + 45 * s), "PASSPORT", int(20 * s), gold, "mm", True)
        elif label == "時間に余裕を":
            r = 68 * s
            d.ellipse([x - r, y - r, x + r, y + r], fill=WHITE, outline=NAVY, width=max(1, int(8 * s)))
            for i in range(12):
                a = i * math.pi / 6
                d.line([(x + math.cos(a) * r * 0.78, y + math.sin(a) * r * 0.78),
                        (x + math.cos(a) * r * 0.9, y + math.sin(a) * r * 0.9)], fill=NAVY, width=max(1, int(3 * s)))
            am = t * 2.0 - math.pi / 2
            ah = t * 0.17 - math.pi / 2
            d.line([(x, y), (x + math.cos(ah) * r * 0.45, y + math.sin(ah) * r * 0.45)], fill=NAVY, width=max(1, int(7 * s)))
            d.line([(x, y), (x + math.cos(am) * r * 0.7, y + math.sin(am) * r * 0.7)], fill=ORANGE, width=max(1, int(4 * s)))
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=NAVY)
        else:
            suitcase(d, x, y + 70 * s, 115 * s, 150 * s)
        if s > 0.8 and label != "荷物":
            ly = {"eチケット": y + 140, "パスポート": y + 120, "時間に余裕を": y + 95}[label]
            text(d, (x, ly), label, 20, NAVY, "mm", True)


def illus_checkin(cimg, d, t, S):
    d.rectangle([0, 440, CW, CH], fill=(215, 222, 232))
    # 自動チェックイン機
    rr(d, (330, 90, 500, 440), 16, fill=(232, 238, 246), outline=NAVY, width=4)
    rr(d, (350, 112, 480, 232), 8, fill=(40, 110, 190))
    text(d, (415, 150), "チェックイン", 18, WHITE, "mm", True)
    rr(d, (370, 180, 460, 212), 6, fill=ORANGE)
    text(d, (415, 196), "スタート", 16, WHITE, "mm", True)
    rr(d, (360, 260, 470, 290), 6, fill=(200, 210, 222))
    d.rectangle([370, 318, 460, 326], fill=NAVY)
    text(d, (415, 72), "自動チェックイン機", 20, NAVY, "mm", True)
    # 搭乗券が出てくる
    pe = clamp((S.since(0) - 3.6) / 1.0)
    if pe > 0:
        rr(d, (378, 322, 452, 322 + 70 * ease_out(pe)), 4, fill=WHITE, outline=SKY, width=2)
    # 人が歩いてくる
    pw = clamp(t / 3.0)
    x = lerp(-40, 255, ease_out(pw))
    person(d, x, 440, 1.5, phase=t * 9 if pw < 0.95 else None)
    # スマホで事前チェックイン
    p = S.since(1) / 0.5
    if p > 0:
        s = ease_back(p)
        sc = phone(d, 110, 160, 110 * s, 200 * s)
        if s > 0.6:
            text(d, (110, sc[1] + 24), "オンライン", 15, NAVY, "mm", True)
            text(d, (110, sc[1] + 44), "チェックイン", 15, NAVY, "mm", True)
            check_mark(d, 110, 185, 30 * s)
    # 搭乗券の拡大
    r = callout(cimg, (30, 235, 570, 475), S.since(2) / 0.5, border=NAVY)
    if r:
        dd, s = r
        if s > 0.8:
            rr(dd, (34, 239, 566, 285), 14, fill=NAVY)
            dd.rectangle([34, 270, 566, 285], fill=NAVY)
            text(dd, (60, 262), "搭乗券  BOARDING PASS", 22, WHITE, "lm", True)
            fields = [("便名", "AB 123", 60, 305), ("行き先", "札幌", 230, 305), ("出発", "9:50", 400, 305),
                      ("ゲート", "15", 60, 385), ("座席", "23A", 230, 385), ("搭乗開始", "9:30", 400, 385)]
            pulse = 0.5 + 0.5 * math.sin(t * 6)
            for name, val, fx, fy in fields:
                if name in ("便名", "ゲート", "座席"):
                    rr(dd, (fx - 12, fy - 8, fx + 140, fy + 72), 10, fill=lerpc((255, 244, 225), (255, 228, 190), pulse),
                       outline=ORANGE, width=3)
                text(dd, (fx, fy), name, 17, GRAY)
                text(dd, (fx, fy + 24), val, 34, NAVY, bold=True)
            qr(dd, 505, 300, 50, seed=7)


def illus_baggage(cimg, d, t, S):
    # 壁と荷物の入口
    d.rectangle([470, 120, CW, 335], fill=(170, 180, 195))
    d.rectangle([492, 185, CW, 335], fill=(55, 60, 75))
    # 係員
    person(d, 390, 348, 1.3, color=NAVY)
    # スーツケース
    u = t % 7.0
    if u < 1.5:
        x = lerp(-90, 235, ease_out(u / 1.5))
    elif u < 3.5:
        x = 235
    elif u < 6.0:
        x = lerp(235, 720, ease_in_out((u - 3.5) / 2.5))
    else:
        x = 900
    suitcase(d, x, 330, 100, 130)
    if 2.3 < u < 6.0:
        d.line([(x, 205), (x + 18, 235)], fill=NAVY, width=2)
        rr(d, (x + 8, 232, x + 40, 280), 4, fill=WHITE, outline=GRAY)
        d.rectangle([x + 8, 245, x + 40, 252], fill=ORANGE)
    # のれん（ゴムのカーテン）
    for i in range(6):
        sx = 494 + i * 18
        d.rectangle([sx, 187, sx + 14, 333], fill=(80, 88, 105))
    # ベルトとカウンター
    d.rectangle([0, 330, CW, 348], fill=(80, 85, 95))
    for i in range(0, CW, 30):
        d.ellipse([i + 10, 334, i + 20, 344], fill=(130, 135, 145))
    d.rectangle([0, 348, CW, CH], fill=(200, 212, 228))
    d.rectangle([165, 330, 305, 334], fill=ORANGE)
    rr(d, (180, 370, 290, 410), 8, fill=NAVY)
    if 1.5 <= u < 3.5:
        w = 18.0 * ease_out((u - 1.5) / 0.6)
    else:
        w = 0.0
    text(d, (235, 390), f"{w:4.1f} kg", 22, (120, 255, 160), "mm", True)
    text(d, (420, 430), "カウンター", 22, NAVY, "mm", True)
    # NG カード
    r = callout(cimg, (15, 15, 290, 185), S.since(1) / 0.5, border=RED)
    if r:
        dd, s = r
        if s > 0.8:
            text(dd, (152, 40), "預け荷物に入れない", 20, RED, "mm", True)
            rr(dd, (50, 85, 120, 150), 8, fill=(90, 100, 120))
            dd.rectangle([120, 105, 128, 130], fill=(90, 100, 120))
            dd.polygon([(90, 92), (72, 120), (86, 120), (78, 144), (100, 112), (86, 112), (96, 92)], fill=(255, 220, 60))
            rr(dd, (190, 100, 225, 155), 5, fill=(80, 150, 220))
            dd.rectangle([195, 92, 220, 102], fill=GRAY)
            dd.polygon([(207, 64), (199, 82), (207, 90), (215, 82)], fill=ORANGE)
            no_sign(dd, 88, 118, 50)
            no_sign(dd, 207, 118, 50)
    r = callout(cimg, (310, 15, 585, 185), S.since(2) / 0.5, border=GREEN)
    if r:
        dd, s = r
        if s > 0.8:
            text(dd, (447, 40), "手元に持っておく", 20, GREEN, "mm", True)
            rr(dd, (345, 85, 435, 145), 10, fill=(150, 95, 60))
            dd.rectangle([405, 105, 440, 125], fill=(120, 75, 45))
            text(dd, (390, 160), "財布", 16, TEXT, "mm")
            rr(dd, (470, 80, 540, 145), 10, fill=WHITE, outline=GREEN, width=3)
            dd.rectangle([498, 92, 512, 133], fill=GREEN)
            dd.rectangle([484, 106, 526, 119], fill=GREEN)
            text(dd, (505, 160), "薬", 16, TEXT, "mm")


def illus_security(cimg, d, t, S):
    d.rectangle([0, 0, CW, CH], fill=(245, 248, 252))
    # 上段: X線検査機
    u = (t % 6.0) / 6.0
    tx = lerp(-160, 760, u)
    d.rectangle([tx - 60, 182, tx + 60, 200], fill=(170, 175, 185))
    rr(d, (tx - 40, 138, tx + 20, 182), 8, fill=(80, 130, 200))
    d.rectangle([tx + 26, 168, tx + 42, 182], fill=NAVY)
    d.ellipse([tx + 44, 172, tx + 54, 182], fill=(230, 190, 90))
    rr(d, (190, 50, 410, 200), 12, fill=(150, 160, 175))
    d.rectangle([200, 120, 400, 200], fill=(105, 115, 130))
    rr(d, (240, 64, 360, 104), 6, fill=(30, 40, 60))
    text(d, (300, 84), "X線検査", 18, (120, 255, 160), "mm", True)
    for i in range(5):
        d.rectangle([195 + i * 3, 122, 197 + i * 3, 200], fill=(70, 75, 85))
        d.rectangle([399 + i * 3, 122, 401 + i * 3, 200], fill=(70, 75, 85))
    d.rectangle([0, 200, CW, 214], fill=(80, 85, 95))
    # 下段: 金属探知機ゲート
    d.rectangle([0, 470, CW, CH], fill=(205, 212, 225))
    v = (t % 6.0) / 6.0
    px = lerp(-40, 650, v)
    inside = 280 < px < 380
    d.rectangle([270, 290, 288, 470], fill=(170, 178, 192))
    rr(d, (262, 272, 398, 298), 6, fill=(150, 158, 172))
    lamp = GREEN if inside else (120, 130, 140)
    d.ellipse([318, 252, 342, 276], fill=lamp)
    person(d, px, 470, 1.25, phase=t * 9)
    d.rectangle([372, 290, 390, 470], fill=(170, 178, 192))
    text(d, (330, 485 - 10), "金属探知機", 18, NAVY, "mm", True)
    # 液体
    k3, k4, k5 = S.since(3), S.since(4), S.since(5)
    if k4 < 0:
        r = callout(cimg, (60, 240, 540, 465), k3 / 0.5)
        if r:
            dd, s = r
            if s > 0.8:
                rr(dd, (85, 270, 255, 440), 14, fill=(225, 240, 252), outline=(120, 170, 220), width=3)
                dd.rectangle([85, 270, 255, 285], fill=(120, 170, 220))
                cols = [(120, 200, 230), (240, 170, 190), (170, 220, 160)]
                for i, c in enumerate(cols):
                    bx = 110 + i * 48
                    rr(dd, (bx, 320, bx + 34, 420), 6, fill=c)
                    dd.rectangle([bx + 9, 302, bx + 25, 320], fill=GRAY)
                text(dd, (290, 300), "液体（国際線）", 22, NAVY, bold=True)
                text(dd, (290, 345), "・100ml以下の容器", 20, TEXT)
                text(dd, (290, 380), "・透明な袋にまとめる", 20, TEXT)
                text(dd, (290, 415), "・保安検査で取り出す", 20, TEXT)
    elif k5 < 0:
        r = callout(cimg, (60, 240, 540, 465), k4 / 0.5, border=RED)
        if r:
            dd, s = r
            if s > 0.8:
                text(dd, (300, 270), "持ち込めない物の例", 22, RED, "mm", True)
                dd.polygon([(120, 330), (230, 330), (230, 350), (120, 352)], fill=(200, 205, 215))
                rr(dd, (230, 325, 280, 356), 8, fill=(60, 60, 70))
                rr(dd, (370, 320, 420, 420), 10, fill=(230, 90, 90))
                dd.rectangle([385, 302, 405, 320], fill=GRAY)
                no_sign(dd, 200, 360, 70)
                no_sign(dd, 395, 360, 70)
                text(dd, (200, 445), "刃物", 18, TEXT, "mm")
                text(dd, (395, 445), "一部のスプレー", 18, TEXT, "mm")
    else:
        r = callout(cimg, (60, 240, 540, 465), k5 / 0.5)
        if r:
            dd, s = r
            if s > 0.8:
                rr(dd, (100, 280, 200, 420), 10, fill=(125, 30, 45))
                text(dd, (150, 400), "PASSPORT", 14, (230, 190, 90), "mm", True)
                dd.ellipse([125, 310, 175, 360], outline=(230, 190, 90), width=3)
                text(dd, (240, 310), "国際線は", 22, NAVY, bold=True)
                text(dd, (240, 350), "このあと出国審査", 26, NAVY, bold=True)
                text(dd, (240, 395), "パスポートを見せます", 20, TEXT)


def illus_gate(cimg, d, t, S):
    # 窓の外の飛行機
    cimg.paste(SKY_CARD.crop((0, 0, CW, 250)), (0, 0))
    d.rectangle([0, 200, CW, 250], fill=(150, 160, 170))
    d.line([(0, 225), (CW, 225)], fill=(255, 230, 120), width=3)
    draw_plane(cimg, 300, 170, 420)
    for x in (0, 150, 300, 450, 597):
        d.rectangle([x - 3, 0, x + 3, 250], fill=(90, 100, 115))
    d.rectangle([0, 250, CW, 262], fill=(90, 100, 115))
    d.rectangle([0, 262, CW, CH], fill=(238, 241, 246))
    d.rectangle([0, 450, CW, CH], fill=(205, 212, 225))
    # ゲート番号の看板
    rr(d, (30, 280, 150, 350), 8, fill=(255, 210, 50))
    text(d, (90, 300), "ゲート", 16, NAVY, "mm", True)
    text(d, (90, 330), "15", 34, NAVY, "mm", True)
    # 出発案内表示
    rr(d, (320, 280, 580, 440), 10, fill=(25, 30, 40))
    text(d, (450, 298), "出発  Departures", 16, WHITE, "mm", True)
    rows = [("9:10", "福岡", "12", "出発済"), ("9:50", "札幌", "15", "定刻"), ("10:20", "那覇", "18", "定刻")]
    for i, (tm, dest, g, st) in enumerate(rows):
        y = 330 + i * 34
        hl = i == 1 and S.since(2) >= 0
        if hl and math.sin(t * 6) > -0.3:
            d.rectangle([326, y - 14, 574, y + 14], fill=(60, 70, 95))
        if i == 1 and S.since(3) >= 0:
            st = "搭乗中"
        c = (255, 220, 80)
        text(d, (335, y), tm, 16, c, "lm")
        text(d, (390, y), dest, 16, WHITE, "lm")
        text(d, (450, y), g, 16, c, "lm")
        text(d, (500, y), st, 16, (120, 255, 160) if st == "搭乗中" else WHITE, "lm")
    # 人がゲートへ
    pw = clamp(S.since(0) / 3.0)
    x = lerp(-30, 230, ease_out(pw))
    person(d, x, 450, 1.3, phase=t * 9 if pw < 0.95 else None)
    # 読み取り機
    r = callout(cimg, (150, 285, 310, 470), S.since(3) / 0.5, border=GREEN)
    if r:
        dd, s = r
        if s > 0.8:
            rr(dd, (190, 320, 270, 440), 8, fill=(200, 208, 220))
            rr(dd, (200, 330, 260, 370), 6, fill=GREEN if math.sin(t * 5) > 0 else (40, 60, 80))
            text(dd, (230, 350), "OK", 18, WHITE, "mm", True)
            bob = math.sin(t * 3) * 6
            phone(dd, 230, 400 + bob, 46, 70)
            qr(dd, 214, 386 + bob, 32, seed=3)
            text(dd, (230, 305), "QRをかざす", 16, NAVY, "mm", True)


def illus_seat(cimg, d, t, S):
    d.rectangle([0, 0, CW, CH], fill=(245, 248, 252))
    rr(d, (45, 15, 395, 478), 70, fill=(250, 250, 252), outline=NAVY, width=4)
    cols = [("A", 80), ("B", 125), ("C", 170), ("D", 255), ("E", 300), ("F", 345)]
    for name, x in cols:
        text(d, (x + 20, 45), name, 20, NAVY, "mm", True)
    rows = list(range(20, 27))
    hl = S.since(1) >= 0
    blink = math.sin(t * 7) > -0.2
    for i, row in enumerate(rows):
        y = 65 + i * 56
        row_hl = S.since(2) >= 0 and row == 23
        text(d, (232, y + 21), str(row), 18, ORANGE if row_hl else GRAY, "mm", True)
        for name, x in cols:
            target = hl and row == 23 and name == "A"
            fill = (ORANGE if blink else (255, 200, 140)) if target else (120, 160, 210)
            rr(d, (x, y, x + 40, y + 42), 8, fill=fill)
            rr(d, (x + 3, y + 32, x + 37, y + 42), 4, fill=lerpc(fill, NAVY, 0.3))
        d.rectangle([56, y + 8, 62, y + 34], fill=(150, 200, 240))
        d.rectangle([386, y + 8, 391, y + 34], fill=(150, 200, 240))
    text(d, (30, 250), "窓", 18, SKY, "mm", True)
    text(d, (30, 272), "側", 18, SKY, "mm", True)
    text(d, (412, 250), "窓", 18, SKY, "mm", True)
    text(d, (412, 272), "側", 18, SKY, "mm", True)
    # 通路を歩く人（上から見た図）
    k = S.since(1) - 0.5
    pa = clamp(k / 3.0)
    pb = clamp((k - 3.0) / 1.2)
    px = lerp(235, 100, ease_in_out(pb))
    py = lerp(30, 65 + 3 * 56 + 21, ease_in_out(pa))
    d.ellipse([px - 15, py - 15, px + 15, py + 15], fill=(70, 110, 190))
    d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(70, 50, 40))
    # 頭上の棚
    r = callout(cimg, (410, 30, 590, 230), S.since(3) / 0.5)
    if r:
        dd, s = r
        if s > 0.8:
            text(dd, (500, 52), "頭上の棚", 18, NAVY, "mm", True)
            rr(dd, (430, 75, 570, 150), 10, fill=(225, 232, 242), outline=NAVY, width=3)
            text(dd, (545, 92), "23", 14, ORANGE, "mm", True)
            bx = lerp(600, 500, ease_out((S.since(3) - 0.5) / 1.0))
            rr(dd, (bx - 35, 105, bx + 25, 145), 8, fill=(80, 130, 200))
            text(dd, (500, 180), "または", 16, GRAY, "mm")
            text(dd, (500, 205), "前の座席の下", 16, NAVY, "mm", True)
    # シートベルト
    r = callout(cimg, (410, 250, 590, 470), S.since(4) / 0.5, border=ORANGE)
    if r:
        dd, s = r
        if s > 0.8:
            text(dd, (500, 275), "シートベルト", 18, NAVY, "mm", True)
            c = ease_in_out(((S.since(4) - 0.4) % 3.0) / 1.2)
            lx = lerp(430, 470, c)
            rx = lerp(570, 530, c)
            dd.rectangle([415, 345, lx + 20, 375], fill=(90, 100, 120))
            dd.rectangle([rx - 20, 345, 585, 375], fill=(90, 100, 120))
            rr(dd, (lx, 335, lx + 50, 385), 6, fill=(200, 205, 215), outline=GRAY, width=2)
            dd.polygon([(rx, 350), (rx - 30, 350), (rx - 40, 360), (rx - 30, 370), (rx, 370)], fill=(180, 186, 198))
            if c >= 0.99:
                text(dd, (500, 410), "カチッ！", 22, ORANGE, "mm", True)
            text(dd, (500, 445), "腰の低い位置で", 16, TEXT, "mm")


def illus_takeoff(cimg, d, t, S):
    d.rectangle([0, 0, CW, CH], fill=(245, 248, 252))
    # スマホの機内モード
    sc = phone(d, 140, 210, 170, 330)
    text(d, (140, sc[1] + 30), "設定", 20, NAVY, "mm", True)
    on = clamp((S.since(0) - 1.2) / 0.4)
    rr(d, (sc[0] + 8, 120, sc[2] - 8, 175), 10, fill=WHITE)
    text(d, (sc[0] + 16, 147), "機内モード", 16, TEXT, "lm")
    tx0 = sc[2] - 58
    rr(d, (tx0, 136, tx0 + 44, 158), 11, fill=lerpc((200, 205, 215), GREEN, on))
    kx = lerp(tx0 + 11, tx0 + 33, ease_out(on))
    d.ellipse([kx - 9, 138, kx + 9, 156], fill=WHITE)
    for i in range(3):
        y = 195 + i * 50
        rr(d, (sc[0] + 8, y, sc[2] - 8, y + 38), 8, fill=WHITE)
        d.rectangle([sc[0] + 20, y + 14, sc[0] + 80, y + 24], fill=LIGHT)
    if on > 0.5:
        rr(d, (78, 300, 202, 334), 17, fill=NAVY)
        text(d, (140, 317), "✈ 機内モード ON", 13, WHITE, "mm")
    # 座席の背もたれとテーブル
    k1 = S.since(1)
    up = ease_in_out((k1 - 0.6) / 1.2)
    tbl = ease_in_out((k1 - 2.0) / 1.2)
    d.rectangle([280, 300, 590, 310], fill=(205, 212, 225))
    rr(d, (300, 220, 430, 262), 12, fill=(80, 130, 200))
    d.rectangle([340, 262, 390, 300], fill=(120, 130, 145))
    ang = math.radians(lerp(28, 8, up))
    px, py = 305, 240
    L = 190
    hw = 20
    tip = (px - math.sin(ang) * L, py - math.cos(ang) * L)
    nx, ny = math.cos(ang) * hw, -math.sin(ang) * hw
    d.polygon([(px, py), (px + nx * 2, py + ny * 2), (tip[0] + nx * 2, tip[1] + ny * 2), (tip[0], tip[1])],
              fill=(70, 120, 190))
    # 前の座席の背面とテーブル
    rr(d, (520, 50, 560, 300), 12, fill=(70, 120, 190))
    ta = math.radians(lerp(90, 0, tbl))
    hx, hy = 520, 175
    tl = 100
    ex, ey = hx - math.sin(ta) * tl, hy + math.cos(ta) * tl - tl
    d.line([(hx, hy), (ex, ey if tbl < 1 else hy - tl * 0)], fill=(180, 186, 198), width=10)
    if tbl >= 0.99:
        rr(d, (505, 90, 518, 190), 4, fill=(180, 186, 198))
    text(d, (420, 30), "背もたれ・テーブルを戻す", 18, NAVY, "mm", True)
    # 安全のビデオ
    k2, k3 = S.since(2), S.since(3)
    if k3 < 0:
        r = callout(cimg, (290, 325, 585, 475), k2 / 0.5)
        if r:
            dd, s = r
            if s > 0.8:
                rr(dd, (305, 340, 570, 460), 8, fill=(30, 40, 60))
                if (k2 % 4.0) < 2.0:
                    rr(dd, (330, 360, 430, 400), 6, fill=GREEN)
                    text(dd, (380, 380), "EXIT", 20, WHITE, "mm", True)
                    text(dd, (380, 430), "非常口", 16, WHITE, "mm")
                else:
                    dd.ellipse([350, 355, 410, 405], fill=(240, 220, 120))
                    dd.line([(380, 355), (380, 345)], fill=WHITE, width=2)
                    text(dd, (380, 430), "酸素マスク", 16, WHITE, "mm")
                text(dd, (500, 380), "安全の", 18, WHITE, "mm", True)
                text(dd, (500, 405), "ビデオ", 18, WHITE, "mm", True)
    else:
        p = ease_out(k3 / 0.6)
        if p > 0:
            sky = SKY_CARD.copy()
            sd = ImageDraw.Draw(sky)
            for i, (cx, cy) in enumerate([(100, 90), (380, 60), (520, 150)]):
                cloud(sd, (cx - k3 * 40 * (i + 1)) % 760 - 80, cy, 0.8)
            sd.rectangle([0, 400, CW, CH], fill=(120, 175, 110))
            sd.rectangle([0, 395, CW, 430], fill=(110, 115, 125))
            for i in range(0, CW, 80):
                sd.rectangle([i + (-k3 * 200) % 80, 410, i + (-k3 * 200) % 80 + 40, 415], fill=WHITE)
            rise = ease_in_out((k3 - 0.8) / 3.0)
            draw_plane(sky, lerp(150, 450, rise), lerp(370, 160, rise), 300, lerp(0, 14, clamp(rise * 3)))
            mask = Image.new("L", (CW, CH), 0)
            ImageDraw.Draw(mask).rectangle([0, 0, CW, int(CH * p)], fill=255)
            cimg.paste(sky, (0, 0), mask)


def illus_flight(cimg, d, t, S):
    d.rectangle([0, 0, CW, CH], fill=(238, 241, 246))
    # 窓
    win = SKY_CARD.resize((340, 260))
    wd = ImageDraw.Draw(win)
    for i, (cx, cy, s) in enumerate([(60, 170, 0.9), (220, 200, 1.2), (330, 150, 0.7), (150, 230, 1.0)]):
        cloud(wd, (cx - t * 25 * (1 + i * 0.4)) % 480 - 60, cy, s)
    wd.polygon([(340, 190), (200, 255), (340, 260)], fill=(200, 208, 222))
    mask = Image.new("L", (340, 260), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 339, 259], radius=110, fill=255)
    rr(d, (120, 15, 480, 295), 125, fill=(210, 216, 228))
    cimg.paste(win, (130, 25), mask)
    # アイコン
    cur = S.current()
    icons = [("ベルトサイン", (0, 1)), ("飲み物", (2,)), ("耳ぬき", (3,)), ("呼び出し", (4,))]
    for i, (label, ks) in enumerate(icons):
        x = 80 + i * 147
        y = 395
        active = cur in ks
        p = max([clamp(S.since(k) / 0.4) for k in ks])
        bg = lerpc(WHITE, (255, 236, 205), 1.0 if active else 0.0)
        rr(d, (x - 62, y - 70, x + 62, y + 75), 16, fill=bg, outline=ORANGE if active else LIGHT, width=4)
        text(d, (x, y + 55), label, 16, NAVY if p > 0 else GRAY, "mm", True)
        dim = p <= 0
        if i == 0:
            lit = S.since(0) < 1.5 or S.since(1) >= 0 and S.since(1) < 0.0
            rr(d, (x - 45, y - 50, x + 45, y + 15), 8, fill=(40, 45, 55))
            c = (255, 200, 60) if lit else (90, 95, 105)
            d.rectangle([x - 32, y - 22, x - 6, y - 12], fill=c)
            d.rectangle([x + 6, y - 22, x + 32, y - 12], fill=c)
            rr(d, (x - 10, y - 28, x + 10, y - 6), 4, fill=c)
            text(d, (x, y + 2), "ON" if lit else "OFF", 14, c, "mm", True)
        elif i == 1:
            c = GRAY if dim else (90, 150, 210)
            d.polygon([(x - 28, y - 40), (x + 28, y - 40), (x + 20, y + 15), (x - 20, y + 15)], fill=c)
            d.rectangle([x - 26, y - 32, x + 26, y - 28], fill=WHITE)
            if not dim:
                for j in range(3):
                    sx = x - 15 + j * 15
                    off = math.sin(t * 4 + j) * 4
                    d.line([(sx + off, y - 50), (sx - off, y - 62)], fill=GRAY, width=3)
        elif i == 2:
            c = GRAY if dim else SKIN
            d.ellipse([x - 38, y - 55, x + 38, y + 20], fill=c)
            d.arc([x - 22, y - 30, x - 6, y - 20], 180, 360, fill=NAVY, width=3)
            d.arc([x + 6, y - 30, x + 22, y - 20], 180, 360, fill=NAVY, width=3)
            m = 6 + (8 * (0.5 + 0.5 * math.sin(t * 3)) if not dim else 0)
            d.ellipse([x - 10, y - 5, x + 10, y - 5 + m], fill=(150, 60, 60))
        else:
            glow = 0.5 + 0.5 * math.sin(t * 6) if active else 0
            d.ellipse([x - 40, y - 52, x + 40, y + 20], fill=lerpc((200, 205, 215), (255, 200, 120), glow))
            d.ellipse([x - 28, y - 40, x + 28, y + 8], fill=GRAY if dim else (70, 120, 190))
            d.ellipse([x - 7, y - 32, x + 7, y - 18], fill=WHITE)
            d.rectangle([x - 9, y - 16, x + 9, y + 0], fill=WHITE)


def _illus_landing(img, t):
    d = ImageDraw.Draw(img)
    img.paste(SKY_CARD, (0, 0))
    cloud(d, (420 - t * 20) % 700 - 50, 80, 0.8)
    cloud(d, (150 - t * 15) % 700 - 50, 140, 0.6)
    d.rectangle([0, 380, CW, CH], fill=(120, 175, 110))
    d.rectangle([0, 375, CW, 420], fill=(110, 115, 125))
    for i in range(0, CW + 80, 80):
        d.rectangle([i, 395, i + 40, 400], fill=WHITE)
    p = clamp(t / 5.0)
    x = lerp(-120, 300, ease_out(p))
    y = lerp(150, 355, clamp(p * 1.4))
    ang = lerp(4, 0, clamp((p - 0.6) / 0.3))
    draw_plane(img, x, y, 300, ang)


def _illus_carousel(img, t, S):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, CW, CH], fill=(238, 241, 246))
    rr(d, (40, 30, 300, 80), 10, fill=(255, 210, 50))
    text(d, (170, 55), "手荷物受取所  AB 123", 20, NAVY, "mm", True)
    d.ellipse([50, 170, 550, 430], fill=(90, 95, 105))
    d.ellipse([110, 215, 490, 385], fill=(205, 212, 225))
    bags = [((80, 130, 200), False), (ORANGE, True), ((120, 120, 130), False), ((60, 160, 120), False),
            ((180, 80, 90), False), ((80, 130, 200), False)]
    n = len(bags)
    items = []
    for i, (c, mine) in enumerate(bags):
        a = t * 0.35 + i * 2 * math.pi / n
        bx = 300 + math.cos(a) * 220
        by = 300 + math.sin(a) * 105
        items.append((by, bx, c, mine))
    for by, bx, c, mine in sorted(items):
        suitcase(d, bx, by + 20, 60, 70, c)
        if mine:
            rr(d, (bx + 18, by - 40, bx + 44, by - 16), 4, fill=(255, 240, 60), outline=NAVY, width=2)
            if S.since(3) > 1.0:
                text(d, (bx, by - 70), "わたしの荷物！", 16, ORANGE, "mm", True)
    person(d, 520, 480, 1.1)


def illus_arrive(cimg, d, t, S):
    k2 = S.since(2)
    sw = ease_in_out(k2 / 0.7) if k2 > 0 else 0.0
    if sw < 1:
        a = Image.new("RGB", (CW, CH))
        _illus_landing(a, t)
        if S.since(1) >= 0:
            r = callout(a, (330, 20, 585, 150), S.since(1) / 0.5, border=ORANGE)
            if r:
                dd, s = r
                if s > 0.8:
                    text(dd, (457, 55), "忘れ物チェック", 20, NAVY, "mm", True)
                    text(dd, (457, 95), "座席ポケット", 18, TEXT, "mm")
                    text(dd, (457, 122), "頭上の棚", 18, TEXT, "mm")
        cimg.paste(a, (int(-sw * CW), 0))
    if sw > 0:
        b = Image.new("RGB", (CW, CH))
        _illus_carousel(b, t, S)
        if S.since(4) >= 0:
            r = callout(b, (300, 20, 585, 150), S.since(4) / 0.5)
            if r:
                dd, s = r
                if s > 0.8:
                    text(dd, (442, 55), "国際線は", 18, NAVY, "mm", True)
                    text(dd, (442, 90), "入国審査 → 税関", 22, NAVY, "mm", True)
                    text(dd, (442, 125), "→ 到着ロビー", 18, TEXT, "mm")
        cimg.paste(b, (int((1 - sw) * CW), 0))


ILLUS = dict(prep=illus_prep, checkin=illus_checkin, baggage=illus_baggage, security=illus_security,
             gate=illus_gate, seat=illus_seat, takeoff=illus_takeoff, flight=illus_flight, arrive=illus_arrive)


# ---------------------------------------------------------------- 画面レイアウト
def draw_subtitle(img, d, S, scene):
    k = S.current()
    if k < 0:
        return
    s = scene["lines"][k]["t"]
    size = 30
    lines = wrap(s, size, 1160)
    if len(lines) > 2:
        size = 26
        lines = wrap(s, size, 1180)
    rr(d, (20, 606, W - 20, 712), 14, fill=(20, 30, 50))
    lh = size + 12
    y0 = 659 - (len(lines) - 1) * lh / 2
    for i, ln in enumerate(lines):
        text(d, (W / 2, y0 + i * lh), ln, size, WHITE, "mm")


def draw_header(d, scene, gt, total):
    d.rectangle([0, 0, W, 80], fill=NAVY)
    if scene["step"]:
        rr(d, (30, 18, 150, 62), 22, fill=ORANGE)
        text(d, (90, 40), f"STEP {scene['step']}", 24, WHITE, "mm", True)
        text(d, (175, 40), scene["title"], 36, WHITE, "lm", True)
    else:
        text(d, (40, 40), scene["title"], 36, WHITE, "lm", True)
    text(d, (W - 30, 40), "はじめての飛行機ガイド", 20, (180, 200, 230), "rm")
    d.rectangle([0, 80, W, 86], fill=(50, 70, 110))
    d.rectangle([0, 80, int(W * gt / total), 86], fill=ORANGE)


def draw_points(d, scene, S, t):
    rr(d, (670, 100, 1240, 590), 22, fill=WHITE)
    text(d, (700, 132), "ポイント", 24, ORANGE, "lm", True)
    d.line([(700, 155), (1210, 155)], fill=LIGHT, width=2)
    y = 180
    cur = S.current()
    size, lh, gap = 28, 40, 26
    bullets = [ln["b"] for ln in scene["lines"] if ln.get("b")]
    if sum(len(wrap(b, size, 470)) * lh + gap for b in bullets) > 400:
        size, lh, gap = 25, 34, 16
    for k, ln in enumerate(scene["lines"]):
        b = ln.get("b")
        if not b:
            continue
        p = ease_out(S.since(k) / 0.45)
        rows = wrap(b, size, 470)
        h = len(rows) * lh
        if p > 0:
            if k == cur:
                rr(d, (688, y - 10, 1222, y + h + 2), 12, fill=lerpc(WHITE, (232, 243, 255), p))
            off = (1 - p) * 30
            d.ellipse([705 + off, y + 8, 721 + off, y + 24], fill=lerpc(WHITE, ORANGE, p))
            for i, r in enumerate(rows):
                text(d, (735 + off, y + i * lh), r, size, lerpc(WHITE, TEXT, p))
        y += h + gap


def draw_title(img, d, S, t):
    img.paste(TITLE_BG, (0, 0))
    for i, (cx, cy, s) in enumerate([(200, 150, 1.4), (700, 110, 1.0), (1050, 220, 1.6), (450, 480, 1.2),
                                     (1100, 500, 0.9)]):
        cloud(d, (cx - t * 18 * (1 + i * 0.3)) % 1500 - 120, cy, s)
    p = clamp(t / 8.0)
    draw_plane(img, lerp(-200, 1500, p), lerp(520, 120, p), 360, 14)
    a = ease_out(t / 1.0)
    rr(d, (190, 205, 1090, 455), 36, fill=lerpc((200, 225, 245), WHITE, a))
    text(d, (640, 290), "はじめての飛行機", 84, lerpc(WHITE, NAVY, a), "mm", True)
    text(d, (640, 385), "空港から到着まで やさしい乗り方ガイド", 36, lerpc(WHITE, ORANGE, a), "mm", True)


def draw_summary(img, d, S, t):
    rr(d, (40, 100, 1240, 590), 22, fill=WHITE)
    k1 = S.since(1)
    n_on = 0 if k1 < 0 else int(clamp(k1 / (S.dur(1) * 0.95)) * len(STEP_NAMES) + 0.999)
    pos = [(70 + i * 235, 140) for i in range(5)] + [(187 + i * 235, 270) for i in range(4)]
    for i, (name, (x, y)) in enumerate(zip(STEP_NAMES, pos)):
        on = i < n_on or S.since(2) >= 0
        fill = (60, 130, 210) if on else (236, 240, 246)
        rr(d, (x, y, x + 200, y + 90), 18, fill=fill)
        d.ellipse([x + 12, y + 25, x + 52, y + 65], fill=ORANGE if on else (205, 212, 225))
        text(d, (x + 32, y + 45), str(i + 1), 22, WHITE, "mm", True)
        text(d, (x + 128, y + 45), name, 22 if len(name) < 6 else 19, WHITE if on else GRAY, "mm", True)
        nxt = pos[i + 1] if i + 1 < len(pos) else None
        if nxt and nxt[1] == y:
            ax = x + 212
            d.polygon([(ax, y + 35), (ax + 12, y + 45), (ax, y + 55)], fill=ORANGE if on else LIGHT)
    if S.since(2) >= 0:
        c = lerpc(WHITE, (190, 90, 20), ease_out(S.since(2) / 0.5))
        text(d, (640, 410), "※時間や持ち込みのルールは航空会社・路線によって異なります", 24, c, "mm", True)
    if S.since(3) >= 0:
        c = lerpc(WHITE, TEXT, ease_out(S.since(3) / 0.5))
        text(d, (640, 455), "困ったら、空港スタッフや客室乗務員に聞いてみよう", 24, c, "mm")
    k4 = S.since(4)
    if k4 >= 0:
        s = ease_back(k4 / 0.6)
        text(d, (640, 530), "よい空の旅を！", max(1, int(54 * s)), ORANGE, "mm", True)
        p = clamp(k4 / 4.0)
        draw_plane(img, lerp(60, 1350, p), lerp(560, 470, p), 150, 6)


def render_frame(scene, S, t, gt, total):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    if scene["key"] == "title":
        draw_title(img, d, S, t)
    else:
        draw_header(d, scene, gt, total)
        if scene["key"] == "summary":
            draw_summary(img, d, S, t)
        else:
            cimg = Image.new("RGB", (CW, CH), WHITE)
            ILLUS[scene["key"]](cimg, ImageDraw.Draw(cimg), t, S)
            mask = Image.new("L", (CW, CH), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, CW - 1, CH - 1], radius=22, fill=255)
            img.paste(cimg, (CX, CY), mask)
            draw_points(d, scene, S, t)
    draw_subtitle(img, d, S, scene)
    fade = clamp(t / 0.35)
    if fade < 1:
        img = Image.blend(Image.new("RGB", (W, H), BG if scene["key"] != "title" else WHITE), img, fade)
    return img


# ---------------------------------------------------------------- 音声
def chime():
    """空港のアナウンス風「ポーン」。"""
    out = []
    for f, dur in ((659.25, 0.45), (523.25, 0.9)):
        n = int(SR * dur)
        tt = np.arange(n) / SR
        env = np.exp(-tt * 4.0) * np.minimum(1, tt * 200)
        out.append((np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * env * 0.18)
    return np.concatenate(out)


def build_timeline():
    """全セリフを音声合成し、シーンごとの開始時刻と音声トラックを作る。"""
    LEAD, GAP, TAIL = 1.0, 0.45, 1.0
    audio = []
    timeline = []
    cur = 0.0
    ch = chime()

    def put(samples, at):
        audio.append((int(at * SR), samples))

    for si, sc in enumerate(SCENES):
        start = cur
        lead = 1.6 if sc["key"] == "title" else LEAD
        if sc["key"] != "title":
            put(ch, start + 0.05)
        pos = start + lead
        starts, durs = [], []
        for ln in sc["lines"]:
            x, sr = pyopenjtalk.tts(ln.get("r", ln["t"]), speed=0.95)
            x = x.astype(np.float64)
            if sr != SR:
                idx = np.arange(0, len(x), sr / SR)
                x = np.interp(idx, np.arange(len(x)), x)
            x = x / (np.abs(x).max() + 1e-9) * 0.85
            starts.append(pos - start)
            durs.append(len(x) / SR)
            put(x, pos)
            pos += len(x) / SR + GAP
        end = pos + (2.5 if si == len(SCENES) - 1 else TAIL)
        timeline.append((start, end - start, starts, durs))
        cur = end
        print(f"  {sc['title'] or 'タイトル'}: {end - start:.1f}秒", flush=True)
    total = cur
    track = np.zeros(int(total * SR) + SR)
    for at, s in audio:
        track[at:at + len(s)] += s
    track = np.clip(track, -1, 1)
    return timeline, total, (track * 32767).astype(np.int16)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "airplane_boarding_guide.mp4")
    print("音声を合成中…")
    timeline, total, track = build_timeline()
    wav_path = os.path.splitext(out)[0] + "_audio.wav"
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(track.tobytes())
    nframes = int(math.ceil(total * FPS))
    print(f"映像を生成中… 全{total:.1f}秒 / {nframes}フレーム")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav_path, "-c:v", "libx264", "-preset", "medium", "-crf", "22",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    si = 0
    for fi in range(nframes):
        gt = fi / FPS
        while si + 1 < len(timeline) and gt >= timeline[si + 1][0]:
            si += 1
        start, _, starts, durs = timeline[si]
        S = Timer(starts, durs)
        S.t = gt - start
        frame = render_frame(SCENES[si], S, S.t, gt, total)
        proc.stdin.write(frame.tobytes())
        if fi % (FPS * 20) == 0:
            print(f"  {gt:6.1f}秒", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav_path)
    print("完成:", out)


if __name__ == "__main__":
    main()
