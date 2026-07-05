from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

INK = "#1A1A2E"
INK_SOFT = "#5C5C75"
CREAM = "#FFF8E7"
PAPER = "#FFFDF7"
ORANGE = "#FF6B35"
TEAL = "#06A77D"
BLUE = "#3A86FF"
HONEY = "#FFB627"
MINT = "#D2F4E8"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


SERIF_BLACK = "/Library/Fonts/ACaslonPro-Bold.otf"
SANS = "/System/Library/Fonts/Supplemental/Trebuchet MS.ttf"
SANS_BOLD = "/System/Library/Fonts/Supplemental/Trebuchet MS Bold.ttf"
ROUND_BOLD = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=INK, width=4):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_icon():
    image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    rounded(draw, (26, 26, 462, 462), 140, ORANGE, width=20)
    dot_box = (376, 24, 500, 148)
    draw.ellipse(dot_box, fill=HONEY, outline=INK, width=16)
    draw.text((145, 110), "R", font=font(ROUND_BOLD, 240), fill=PAPER)

    image.save(PUBLIC / "icon.png")


def draw_dot_grid(draw: ImageDraw.ImageDraw, width: int, height: int):
    for x in range(24, width, 30):
        for y in range(24, height, 30):
            draw.ellipse((x, y, x + 2, y + 2), fill="#E6D6B4")


def draw_hero():
    width, height = 1097, 622
    image = Image.new("RGB", (width, height), CREAM)
    draw = ImageDraw.Draw(image)

    draw_dot_grid(draw, width, height)

    draw.rounded_rectangle((50, 18, 360, 49), radius=15, fill=PAPER, outline=INK, width=3)
    draw.ellipse((63, 28, 71, 36), fill=TEAL)
    draw.text((79, 21), "SPACED REPETITION · FOR ESL", font=font(SANS_BOLD, 17), fill=INK)

    serif = font(SERIF_BLACK, 74)
    serif_small = font(SERIF_BLACK, 60)
    sans = font(SANS, 22)
    sans_bold = font(SANS_BOLD, 22)
    monoish = font(SANS_BOLD, 18)

    draw.text((50, 76), "Words that", font=serif, fill=INK)
    draw.text((50, 152), "stick.", font=serif, fill=INK)
    draw.text((50, 226), "Memory that", font=serif, fill=INK)
    draw.rectangle((50, 300, 270, 340), fill=MINT)
    draw.text((50, 302), "grows.", font=serif_small, fill=INK)

    body = (
        "A pocket-sized vocabulary trainer\n"
        "that learns how you forget, then feeds\n"
        "you the right word at exactly the right moment."
    )
    draw.multiline_text((51, 381), body, font=sans, fill=INK_SOFT, spacing=10)

    rounded(draw, (50, 465, 210, 510), 18, ORANGE, outline=ORANGE, width=2)
    draw.text((79, 475), "Start learning  →", font=font(SANS_BOLD, 17), fill=PAPER)
    rounded(draw, (226, 463, 364, 512), 18, PAPER, outline=INK, width=3)
    draw.text((249, 475), "See the deck", font=font(SANS_BOLD, 17), fill=INK)

    legend_y = 558
    items = [("LLM-crafted examples", ORANGE, 50), ("SM-2 scheduling", TEAL, 240), ("Daily nudges", BLUE, 390)]
    for label, color, x in items:
        draw.ellipse((x, legend_y, x + 8, legend_y + 8), fill=color)
        draw.text((x + 16, legend_y - 8), label, font=font(SANS, 16), fill=INK_SOFT)

    shadow_offset = 14
    rounded(draw, (663 + shadow_offset, 147 + shadow_offset, 1028 + shadow_offset, 438 + shadow_offset), 30, INK, outline=INK, width=0)
    rounded(draw, (649, 145, 1014, 436), 30, PAPER, outline=INK, width=3)
    draw.polygon([(681, 143), (777, 139), (779, 169), (681, 175)], fill=HONEY)
    for stripe in range(0, 100, 14):
        draw.line((684 + stripe, 144, 660 + stripe, 174), fill="#FFD989", width=4)

    draw.text((683, 188), "ENGLISH · ADV.", font=monoish, fill=INK_SOFT)
    draw.text((682, 214), "ephemeral", font=font(SERIF_BLACK, 58), fill=INK)
    draw.text((685, 284), "Lasting for a very short time.", font=sans, fill=INK_SOFT)
    draw.text((686, 320), '"The cherry blossoms are', font=font(SANS, 18), fill="#8A88A4")
    draw.text((686, 346), "ephemeral —", font=font(SANS, 18), fill="#8D8BB8")

    buttons = [
        (("Again", HONEY), 686),
        (("Good", TEAL), 846),
        (("Easy", BLUE), 924),
    ]
    for (label, color), x in buttons:
        rounded(draw, (x, 375, x + 66, 405), 8, color, outline=INK, width=3)
        text_fill = PAPER if color != HONEY else INK
        draw.text((x + 17, 383), label, font=font(SANS_BOLD, 14), fill=text_fill)

    rounded(draw, (642 + 10, 339 + 10, 822 + 10, 469 + 10), 24, INK, outline=INK, width=0)
    rounded(draw, (640, 337, 820, 467), 24, PAPER, outline=INK, width=3)
    draw.polygon([(667, 330), (761, 339), (761, 360), (667, 350)], fill=TEAL)
    for stripe in range(0, 100, 14):
        draw.line((670 + stripe, 332, 646 + stripe, 358), fill="#74D9C1", width=4)
    draw.text((666, 366), "STREAK", font=monoish, fill=INK_SOFT)
    draw.text((666, 390), "12", font=font(SERIF_BLACK, 34), fill=INK)
    draw.ellipse((722, 407, 730, 415), fill=HONEY)
    draw.text((668, 424), "days in a row", font=font(SANS, 16), fill=INK_SOFT)

    image.save(PUBLIC / "og.png")


if __name__ == "__main__":
    PUBLIC.mkdir(parents=True, exist_ok=True)
    draw_icon()
    draw_hero()
