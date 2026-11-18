"""Render a TikTok-'Classic'-style caption PNG (1080x1920 canvas) with optional trailing emoji."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import sys, re
FONT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
W, H = 1080, 1920
def render(text, out, size=57, y_center=0.62, max_w=900):
    font = ImageFont.truetype(FONT, size)
    # split trailing emoji
    m = re.search(r"\s*([\U0001F300-\U0001FAFF☀-➿]+)$", text)
    emoji = m.group(1) if m else ""
    text = text[:m.start()] if m else text
    # word wrap
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(), ""
        for w in words:
            t = (cur + " " + w).strip()
            if font.getlength(t) <= max_w: cur = t
            else: lines.append(cur); cur = w
        if cur: lines.append(cur)
    if emoji:
        # emoji goes on the last line
        pass
    lh = int(size * 1.42)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    total = lh * len(lines)
    y0 = int(H * y_center - total / 2)
    em_img = None
    if emoji:
        ef = ImageFont.truetype(EMOJI, 109)
        e = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
        ImageDraw.Draw(e).text((5, 5), emoji, font=ef, embedded_color=True)
        bb = e.getbbox(); e = e.crop(bb)
        es = int(size * 1.08); em_img = e.resize((es, es), Image.LANCZOS)
    for i, line in enumerate(lines):
        lw = font.getlength(line)
        extra = (em_img.width + int(size * 0.28)) if (em_img and i == len(lines) - 1) else 0
        x = (W - lw - extra) / 2
        y = y0 + i * lh
        d.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        if extra:
            asc, desc = font.getmetrics()
            ey = y + (asc + desc) // 2 - em_img.height // 2 - int(size * 0.06)
            txt.alpha_composite(em_img, (int(x + lw + size * 0.28), int(ey)))
    # soft shadow like TikTok classic
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = txt.split()[3].filter(ImageFilter.GaussianBlur(2.2))
    sh.putalpha(a.point(lambda v: int(v * 0.55)))
    img.alpha_composite(sh, (0, 3))
    img.alpha_composite(txt)
    img.save(out)
if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2], y_center=float(sys.argv[3]) if len(sys.argv) > 3 else 0.62)

def slate(note, out):
    """Preview placeholder for a bait clip that still has to be dropped in."""
    img = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(img)
    for yy in range(0, H, 4):
        v = 18 + int(22 * yy / H); d.line([(0, yy), (W, yy)], fill=(v, v, v + 6), width=4)
    f1 = ImageFont.truetype(FONT, 44); f2 = ImageFont.truetype(FONT, 38)
    d.text((W / 2, 300), "DROP CLIP HERE", font=f1, fill=(255, 80, 80), anchor="mm")
    lines, cur = [], ""
    for w in note.split():
        t = (cur + " " + w).strip()
        if f2.getlength(t) <= 940: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    for i, l in enumerate(lines):
        d.text((W / 2, 400 + i * 54), l, font=f2, fill=(230, 230, 230), anchor="mm")
    img.save(out)
