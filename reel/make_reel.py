#!/usr/bin/env python3
"""福山市の美容サロン「ルースビューティー」向け Instagram リール動画を生成するスクリプト。

縦 1080×1920 / 30fps / 約16秒。保存・シェアされやすい「キレイが続く人の3つの習慣」型の構成で、
最後にフォローと予約（プロフィールのリンク・DM）へ誘導します。

必要なもの: Python 3, Pillow, numpy, ffmpeg, IPAゴシックフォント
使い方:    python3 make_reel.py [出力ファイル名]
"""
import math
import os
import random
import subprocess
import sys
import wave
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
SR = 48000
FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
HERE = os.path.dirname(os.path.abspath(__file__))

SALON = "ルースビューティー"
AREA = "福山"

IVORY = (251, 245, 239)
BLUSH = (244, 215, 210)
ROSE = (214, 150, 150)
GOLD = (184, 145, 106)
BROWN = (74, 59, 56)
WHITE = (255, 255, 255)

# 台本。t0/t1 はシーンの開始・終了（秒）
SCENES = [
    {"key": "hook", "t0": 0.0, "t1": 2.6},
    {"key": "tip", "t0": 2.6, "t1": 5.6, "no": "01", "title": "こすらない",
     "sub": "洗顔もタオルもメイク落としも\nやさしく“押さえる”が正解"},
    {"key": "tip", "t0": 5.6, "t1": 8.6, "no": "02", "title": "お風呂上がり\n1分以内に保湿",
     "sub": "肌が乾く前のひと手間で\nうるおいが続く"},
    {"key": "tip", "t0": 8.6, "t1": 11.6, "no": "03", "title": "月1回は\nプロに任せる",
     "sub": "自己流では届かないケアを\nプロの手で"},
    {"key": "salon", "t0": 11.6, "t1": 14.0},
    {"key": "cta", "t0": 14.0, "t1": 16.5},
]
TOTAL = SCENES[-1]["t1"]


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


@lru_cache(maxsize=None)
def text_img(s, size, fill=BROWN, bold=True, spacing=0.25):
    """複数行テキストを中央揃えで描いた RGBA 画像（キャッシュ）。"""
    font = F(size)
    sw = max(1, size // 30) if bold else 0
    lines = s.split("\n")
    lh = int(size * (1 + spacing))
    widths = [font.getlength(ln) for ln in lines]
    w = int(max(widths)) + sw * 2 + 8
    h = lh * (len(lines) - 1) + size + sw * 2 + int(size * 0.25)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        d.text((w / 2, sw + i * lh), ln, font=font, fill=fill, anchor="ma",
               stroke_width=sw, stroke_fill=fill)
    return im


def place(img, layer, cx, cy, alpha=1.0, scale=1.0):
    """layer を中心 (cx, cy) に不透明度・拡大率つきで合成する。"""
    if alpha <= 0.01:
        return
    if abs(scale - 1.0) > 0.005:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))),
                             Image.BILINEAR)
    if alpha < 0.999:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer = layer.copy()
        layer.putalpha(a)
    img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def appear(t, start, dur=0.4):
    """start 秒から dur 秒かけて 0→1。"""
    return ease_out((t - start) / dur)


@lru_cache(maxsize=None)
def pill(s, size, bg, fg, padx=40, pady=20):
    t = text_img(s, size, fg, bold=True)
    w, h = t.width + padx * 2, t.height + pady * 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=bg)
    im.alpha_composite(t, (padx, pady + 4))
    return im


@lru_cache(maxsize=None)
def card(w, h, fill=(255, 255, 255, 235), radius=48, shadow=True):
    pad = 40
    im = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 14, pad + w, pad + h + 14], radius=radius,
                                             fill=(150, 100, 90, 60))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    ImageDraw.Draw(im).rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=fill)
    return im


# ---------- 背景 ----------

def _gradient(top, bottom):
    t = np.linspace(0, 1, H)[:, None, None]
    arr = np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t
    arr = np.repeat(arr, W, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


BG_A = _gradient(IVORY, BLUSH)
BG_B = _gradient((247, 232, 226), (236, 200, 196))


@lru_cache(maxsize=None)
def bokeh(r, color, a):
    pad = int(r * 0.8) + 20
    size = r * 2 + pad * 2
    # 透明部分も同じ色にしておくと、ぼかしたときに縁が黒ずまない
    im = Image.new("RGBA", (size, size), color + (0,))
    ImageDraw.Draw(im).ellipse([pad, pad, pad + r * 2, pad + r * 2], fill=color + (a,))
    return im.filter(ImageFilter.GaussianBlur(r * 0.35))


random.seed(7)
DOTS = [(random.uniform(0, W), random.uniform(0, H), random.choice([40, 60, 90, 130]),
         random.choice([WHITE, (255, 236, 220), (240, 190, 185)]), random.randint(50, 110),
         random.uniform(0.2, 0.6), random.uniform(0, 6.28)) for _ in range(11)]

SPARKS = [(random.uniform(60, W - 60), random.uniform(200, H - 300), random.uniform(0, 3),
           random.uniform(10, 22)) for _ in range(14)]


def sparkle(d, x, y, r, a):
    c = GOLD + (int(255 * a),)
    d.polygon([(x, y - r), (x + r * 0.22, y - r * 0.22), (x + r, y), (x + r * 0.22, y + r * 0.22),
               (x, y + r), (x - r * 0.22, y + r * 0.22), (x - r, y), (x - r * 0.22, y - r * 0.22)], fill=c)


def background(t, mix):
    img = Image.blend(BG_A, BG_B, mix) if mix > 0 else BG_A.copy()
    for x, y, r, col, a, sp, ph in DOTS:
        yy = (y - t * 40 * sp) % (H + 300) - 150
        xx = x + math.sin(t * sp + ph) * 30
        b = bokeh(r, col, a)
        img.alpha_composite(b, (int(xx - b.width / 2), int(yy - b.height / 2)))
    d = ImageDraw.Draw(img)
    for x, y, ph, r in SPARKS:
        a = max(0.0, math.sin(t * 2.2 + ph * 2)) ** 3
        if a > 0.05:
            sparkle(d, x, y, r * (0.6 + 0.4 * a), a * 0.8)
    return img


# ---------- 各シーン ----------

def progress(img, t, active):
    """上部の 1/3・2/3・3/3 インジケーター。"""
    d = ImageDraw.Draw(img)
    for i in range(3):
        x0 = 300 + i * 170
        d.rounded_rectangle([x0, 230, x0 + 140, 242], radius=6, fill=(255, 255, 255, 170))
        if i < active:
            p = 1.0 if i < active - 1 else clamp(t / 0.5)
            d.rounded_rectangle([x0, 230, x0 + int(140 * p), 242], radius=6, fill=GOLD)


def scene_hook(img, t, out):
    # 1フレーム目から読めるように、メインのコピーは最初から表示して少しだけ弾ませる
    place(img, pill("保存して見返してね", 40, (255, 255, 255, 220), ROSE), W / 2, 330, alpha=out)
    place(img, text_img(f"{AREA}で", 80, ROSE), W / 2, 560, alpha=out)
    s = lerp(0.9, 1.0, ease_back(t / 0.4))
    place(img, text_img("キレイが\n続く人", 190, BROWN), W / 2, 850, alpha=out, scale=s)
    p = appear(t, 0.35)
    place(img, text_img("がやってる", 84, BROWN), W / 2, 1140 + 30 * (1 - p), alpha=p * out)
    p = appear(t, 0.55)
    place(img, text_img("3つのこと", 140, GOLD), W / 2, 1300 + 30 * (1 - p), alpha=p * out,
          scale=lerp(0.8, 1.0, ease_back((t - 0.55) / 0.5)))


def scene_tip(img, t, out, sc, idx):
    progress(img, t, idx)
    p = appear(t, 0.0, 0.45)
    c = card(860, 980)
    place(img, c, W / 2, 900 + 60 * (1 - p), alpha=p * out)
    dy = 60 * (1 - p)
    place(img, text_img(sc["no"], 200, GOLD), W / 2, 560 + dy, alpha=appear(t, 0.1) * out,
          scale=lerp(0.6, 1.0, ease_back((t - 0.1) / 0.45)))
    ImageDraw.Draw(img).line([(W / 2 - 60, 690 + dy), (W / 2 + 60, 690 + dy)],
                             fill=GOLD + (int(255 * appear(t, 0.2) * out),), width=6)
    p2 = appear(t, 0.25)
    place(img, text_img(sc["title"], 110 if "\n" in sc["title"] else 130, BROWN),
          W / 2, 860 + dy + 30 * (1 - p2), alpha=p2 * out)
    p3 = appear(t, 0.7)
    place(img, text_img(sc["sub"], 50, (120, 98, 92), bold=False, spacing=0.5),
          W / 2, 1150 + dy + 20 * (1 - p3), alpha=p3 * out)


def scene_salon(img, t, out):
    place(img, text_img(f"{AREA}で\nキレイを続けたいなら", 92, BROWN), W / 2, 560,
          alpha=appear(t, 0.0) * out)
    p = appear(t, 0.45, 0.5)
    place(img, card(880, 520), W / 2, 1050 + 50 * (1 - p), alpha=p * out)
    dy = 50 * (1 - p)
    place(img, text_img("BEAUTY SALON", 40, GOLD, bold=False), W / 2, 870 + dy, alpha=p * out)
    place(img, text_img(SALON, 88, BROWN), W / 2, 990 + dy, alpha=appear(t, 0.6) * out,
          scale=lerp(0.85, 1.0, ease_back((t - 0.6) / 0.5)))
    p2 = appear(t, 0.95)
    ImageDraw.Draw(img).line([(W / 2 - 220 * p2, 1080 + dy), (W / 2 + 220 * p2, 1080 + dy)],
                             fill=GOLD + (int(255 * out),), width=4)
    place(img, text_img("あなたの肌・悩みに合わせた\nケアをご提案します", 48, (120, 98, 92), bold=False,
                        spacing=0.5), W / 2, 1180 + dy, alpha=appear(t, 1.05) * out)


def scene_cta(img, t, out):
    place(img, text_img("フォローして", 100, BROWN), W / 2, 500, alpha=appear(t, 0.0) * out)
    place(img, text_img("キレイ習慣を\nチェック", 130, ROSE), W / 2, 740, alpha=appear(t, 0.15) * out,
          scale=lerp(0.8, 1.0, ease_back((t - 0.15) / 0.5)))
    # フォローボタン（軽く脈打つ）
    pulse = 1.0 + 0.04 * math.sin(max(0.0, t - 0.8) * 7) * (t > 0.8)
    place(img, pill("＋ フォローする", 64, ROSE + (255,), WHITE, padx=80, pady=34), W / 2, 1040,
          alpha=appear(t, 0.5) * out, scale=pulse * lerp(0.7, 1.0, ease_back((t - 0.5) / 0.4)))
    place(img, text_img("ご予約は プロフィールのリンク から", 46, BROWN), W / 2, 1200,
          alpha=appear(t, 0.85) * out)
    place(img, pill("DMで「相談」と送ってね", 44, (255, 255, 255, 230), GOLD), W / 2, 1310,
          alpha=appear(t, 1.1) * out)


def render_frame(gt):
    si = max(i for i, sc in enumerate(SCENES) if gt >= sc["t0"])
    sc = SCENES[si]
    t = gt - sc["t0"]
    out = 1.0 - clamp((gt - (sc["t1"] - 0.25)) / 0.25) if si < len(SCENES) - 1 else 1.0
    mix = 0.0 if sc["key"] in ("hook", "cta") else 1.0
    img = background(gt, mix)
    if sc["key"] == "hook":
        scene_hook(img, t, out)
    elif sc["key"] == "tip":
        scene_tip(img, t, out, sc, int(sc["no"]))
    elif sc["key"] == "salon":
        scene_salon(img, t, out)
    else:
        scene_cta(img, t, out)
    return img.convert("RGB")


# ---------- 音 ----------

def note_freq(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def pop():
    """テキストが出るときの小さな「ポン」。"""
    n = int(0.18 * SR)
    tt = np.arange(n) / SR
    f = 900 + 600 * np.exp(-tt * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 28) * 0.22


def bgm(total):
    """明るく軽いBGM（F - G - Em - Am、約120BPM）。左右2ch を返す。"""
    n = int(total * SR) + SR
    left, right = np.zeros(n), np.zeros(n)
    beat = 0.5
    bar = beat * 4
    chords = [(65, 69, 72), (67, 71, 74), (64, 67, 71), (69, 72, 76)]
    bl = int(bar * SR)
    tt = np.arange(bl) / SR
    pad_env = np.minimum(1, tt / 0.3) * np.minimum(1, (bar - tt) / 0.3)
    sl = int(beat * 1.5 * SR)
    ts = np.arange(sl) / SR
    pluck_env = np.exp(-ts * 7.0) * np.minimum(1, ts * 400)
    kl = int(0.25 * SR)
    tk = np.arange(kl) / SR
    kick = np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-tk * 25)) / SR) * np.exp(-tk * 14) * 0.35
    i = 0
    while i * bl < n:
        ch = chords[i % len(chords)]
        a = i * bl
        seg = sum(np.sin(2 * np.pi * note_freq(m - 12) * tt) for m in ch) * pad_env * 0.045
        seg += np.sin(2 * np.pi * note_freq(ch[0] - 24) * tt) * pad_env * 0.06
        e = min(n, a + bl)
        left[a:e] += seg[:e - a]
        right[a:e] += seg[:e - a]
        arp = [ch[0], ch[1], ch[2], ch[1] + 12, ch[2], ch[1], ch[0] + 12, ch[2]]
        for j, m in enumerate(arp):
            b = a + int(j * beat / 2 * SR)
            if b >= n:
                break
            f = note_freq(m)
            tone = (np.sin(2 * np.pi * f * ts) + 0.3 * np.sin(4 * np.pi * f * ts)) * pluck_env * 0.05
            e = min(n, b + sl)
            pan = 0.4 if j % 2 else -0.4
            left[b:e] += tone[:e - b] * (1 - pan)
            right[b:e] += tone[:e - b] * (1 + pan)
        for j in range(4):
            b = a + int(j * beat * SR)
            if b + kl < n:
                left[b:b + kl] += kick
                right[b:b + kl] += kick
        i += 1
    fade = np.ones(n)
    end = int(total * SR)
    k = int(0.3 * SR)
    fade[:k] = np.linspace(0, 1, k)
    fade[end - 4 * k:end] = np.linspace(1, 0, 4 * k)
    fade[end:] = 0
    return left * fade, right * fade


def build_audio():
    left, right = bgm(TOTAL)
    p = pop()
    hits = [0.0, 0.55]
    for sc in SCENES[1:]:
        hits += [sc["t0"] + 0.1]
    hits += [SCENES[-1]["t0"] + 0.5]
    for at in hits:
        a = int(at * SR)
        left[a:a + len(p)] += p
        right[a:a + len(p)] += p
    stereo = np.clip(np.stack([left, right], axis=1), -1, 1)
    return (stereo * 32767).astype(np.int16)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "beauty_reel.mp4")
    wav_path = os.path.splitext(out)[0] + "_audio.wav"
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(build_audio().tobytes())
    nframes = int(math.ceil(TOTAL * FPS))
    print(f"映像を生成中… 全{TOTAL:.1f}秒 / {nframes}フレーム")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav_path, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-c:a", "aac",
           "-b:a", "192k", "-movflags", "+faststart", "-shortest", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(nframes):
        proc.stdin.write(render_frame(fi / FPS).tobytes())
        if fi % (FPS * 4) == 0:
            print(f"  {fi / FPS:5.1f}秒", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav_path)
    # カバー画像（フックの完成状態）
    cover = os.path.join(os.path.dirname(out), "cover.png")
    render_frame(2.2).save(cover)
    print("完成:", out, "/", cover)


if __name__ == "__main__":
    main()
