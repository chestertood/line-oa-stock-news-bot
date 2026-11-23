"""Draw rich_menu.jpg and profile/profile_640.png (vector shapes, no emoji). python make_images.py"""
from PIL import Image, ImageDraw, ImageFont

F = "C:/Windows/Fonts/"
NAVY, SLATE, BG = (15, 23, 42), (100, 116, 139), (241, 245, 249)
BLUE, ORANGE, GREEN, RED = (37, 99, 235), (234, 88, 12), (5, 150, 105), (220, 38, 38)
S = 4  # supersample factor for smooth edges


def tint(c, k=0.85):
    return tuple(int(v + (255 - v) * k) for v in c)


def icon_news(d, cx, cy, r, c):  # page with headline block and text lines
    w, h = r * 1.1, r * 1.3
    x0, y0 = cx - w / 2, cy - h / 2
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), r * 0.12, outline=c, width=int(r * 0.09))
    p = r * 0.2
    d.rounded_rectangle((x0 + p, y0 + p, x0 + w - p, y0 + p + h * 0.25), r * 0.04, fill=c)
    for i in range(3):
        y = y0 + p + h * 0.42 + i * h * 0.16
        d.line((x0 + p, y, x0 + w - p - (i == 2) * w * 0.3, y), fill=c, width=int(r * 0.08))


def icon_movers(d, cx, cy, r, c):  # green up arrow + red down arrow
    def arrow(x, up, col):
        t, b = cy - r * 0.6, cy + r * 0.6
        tip, tail = (t, b) if up else (b, t)
        hw, hh = r * 0.32, r * 0.42
        d.line((x, tail, x, tip + (hh if up else -hh) * 0.6), fill=col, width=int(r * 0.16))
        d.polygon([(x, tip), (x - hw, tip + (hh if up else -hh)), (x + hw, tip + (hh if up else -hh))], fill=col)
    arrow(cx - r * 0.35, True, GREEN)
    arrow(cx + r * 0.35, False, RED)


def icon_index(d, cx, cy, r, c):  # axis + rising line with points
    x0, y0, x1, y1 = cx - r * 0.7, cy - r * 0.6, cx + r * 0.7, cy + r * 0.6
    d.line((x0, y0, x0, y1, x1, y1), fill=c, width=int(r * 0.08), joint="curve")
    pts = [(x0 + r * 0.25, y1 - r * 0.3), (cx - r * 0.1, cy), (cx + r * 0.2, cy + r * 0.2), (x1 - r * 0.05, y0 + r * 0.1)]
    d.line(pts, fill=c, width=int(r * 0.12), joint="curve")
    for x, y in pts:
        d.ellipse((x - r * 0.1, y - r * 0.1, x + r * 0.1, y + r * 0.1), fill=c)


def rich_menu():
    W, H = 2500 * S, 843 * S
    tw = W // 3
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    B, R = ImageFont.truetype(F + "LeelaUIb.ttf", 104 * S), ImageFont.truetype(F + "LeelawUI.ttf", 46 * S)
    tiles = [(icon_news, "วิเคราะห์ข่าว", "ข่าวตลาด & ตัวเลขเศรษฐกิจ", BLUE),
             (icon_movers, "หุ้นเด่นวันนี้", "บวกแรง • ลบแรง • ซื้อขายมาก", ORANGE),
             (icon_index, "ดัชนี US", "S&P 500 • Nasdaq • Dow", GREEN)]
    pad = 24 * S
    for i, (icon, title, sub, c) in enumerate(tiles):
        x, cx = i * tw, i * tw + tw // 2
        d.rounded_rectangle((x + pad, pad, x + tw - pad, H - pad), 44 * S, fill="white", outline=(226, 232, 240), width=4 * S)
        d.rounded_rectangle((x + pad, pad, x + tw - pad, pad + 28 * S), 14 * S, fill=c)
        d.rectangle((x + pad, pad + 14 * S, x + tw - pad, pad + 28 * S), fill=c)
        r, cy = 120 * S, 270 * S
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tint(c))
        icon(d, cx, cy, r * 0.78, c)
        d.text((cx, 540 * S), title, font=B, fill=NAVY, anchor="mm")
        d.text((cx, 660 * S), sub, font=R, fill=SLATE, anchor="mm")
    img.resize((2500, 843), Image.LANCZOS).save("rich_menu.jpg", quality=92)


def profile():
    N = 640 * S
    img = Image.new("RGB", (N, N), BLUE)
    d = ImageDraw.Draw(img)
    u = N / 640  # design units = px at 640
    # antenna
    d.line((320 * u, 175 * u, 320 * u, 120 * u), fill="white", width=int(14 * u))
    d.ellipse((300 * u, 92 * u, 340 * u, 132 * u), fill="white")
    # ears
    for x in (128, 476):
        d.rounded_rectangle((x * u, 270 * u, (x + 36) * u, 370 * u), 14 * u, fill="white")
    # head
    d.rounded_rectangle((160 * u, 170 * u, 480 * u, 470 * u), 70 * u, fill="white")
    # visor
    d.rounded_rectangle((195 * u, 220 * u, 445 * u, 420 * u), 48 * u, fill=NAVY)
    # eyes
    for x in (265, 375):
        d.ellipse(((x - 24) * u, 262 * u, (x + 24) * u, 310 * u), fill="white")
    # mouth = rising price line
    pts = [(235, 385), (285, 355), (325, 372), (370, 335), (405, 345)]
    d.line([(x * u, y * u) for x, y in pts], fill=(34, 197, 94), width=int(14 * u), joint="curve")
    d.polygon([(418 * u, 320 * u), (392 * u, 330 * u), (412 * u, 352 * u)], fill=(34, 197, 94))
    img.resize((640, 640), Image.LANCZOS).save("profile/profile_640.png")


if __name__ == "__main__":
    rich_menu()
    profile()
    print("ok")
