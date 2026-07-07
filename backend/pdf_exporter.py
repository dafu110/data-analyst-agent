from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import textwrap


CHINESE_FONT_NAME = "DataAnalystChinese"
CHINESE_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


def markdown_to_pdf(markdown: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PDF 导出需要安装 reportlab：pip install -e .[prod]") from exc

    font_path = find_chinese_font()
    if not font_path:
        raise RuntimeError("PDF 导出需要可用中文字体。请安装微软雅黑、黑体、宋体或 Noto Sans CJK 后重试。")
    if CHINESE_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(CHINESE_FONT_NAME, str(font_path)))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left = 48
    right = 48
    y = height - 48
    line_height = 17
    font_size = 10.5
    max_chars = max(24, int((width - left - right) / font_size))
    pdf.setTitle("数据分析报告")
    pdf.setFont(CHINESE_FONT_NAME, font_size)

    for raw_line in markdown.splitlines():
        text = normalize_markdown_line(raw_line)
        for line in wrap_cjk_line(text, max_chars):
            if y < 48:
                pdf.showPage()
                pdf.setFont(CHINESE_FONT_NAME, font_size)
                y = height - 48
            pdf.drawString(left, y, line)
            y -= line_height
    pdf.save()
    return buffer.getvalue()


def find_chinese_font() -> Path | None:
    for candidate in CHINESE_FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def normalize_markdown_line(line: str) -> str:
    text = line.strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^[-*]\s+", "- ", text)
    text = text.replace("**", "").replace("`", "")
    return text


def wrap_cjk_line(text: str, max_chars: int) -> list[str]:
    if not text:
        return [""]
    return textwrap.wrap(
        text,
        width=max_chars,
        break_long_words=True,
        break_on_hyphens=False,
        replace_whitespace=False,
        drop_whitespace=False,
    )
