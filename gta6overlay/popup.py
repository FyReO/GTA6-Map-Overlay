import html
import re

from PyQt5 import QtCore, QtGui

from . import config as C

TITLE_FONT = ("Segoe UI", 13, QtGui.QFont.Bold)
SET_FONT = ("Segoe UI", 9, QtGui.QFont.Bold)
HINT_FONT = ("Segoe UI", 8, QtGui.QFont.Bold)
BODY_FONT = ("Segoe UI", 10)


def description_html(text):
    text = re.sub(r"\*\*|__", "", text or "").strip()
    if not text:
        return "<i style='color:#C9B3D1'>No description available for this location.</i>"
    m = re.match(r"(?is)\s*location:\s*(.*)", text)
    body = html.escape(m.group(1) if m else text)
    label = "<b style='color:#FFFFFF'>Location:</b> " if m else ""
    return f"<span style='color:#E8D8EE'>{label}{body}</span>"


class PopupRenderer:
    def __init__(self, media_dir):
        self.media_dir = media_dir
        self._pixmaps = {}

    def pixmap(self, name):
        pm = self._pixmaps.get(name)
        if pm is None:
            pm = QtGui.QPixmap(str(self.media_dir / name))
            self._pixmaps[name] = pm
        return pm

    @staticmethod
    def _cover(p, pm, target):
        tw, th = target.width(), target.height()
        sw, sh = pm.width(), pm.height()
        k = max(tw / sw, th / sh)
        cw, ch = tw / k, th / k
        p.drawPixmap(target, pm, QtCore.QRectF((sw - cw) / 2, (sh - ch) / 2, cw, ch))

    def paint(self, p, item, info, found, mark_button, anchor, marker_radius, bounds):
        mx, my = anchor
        pms = [pm for pm in (self.pixmap(f) for f in info.get("files", [])[:2]) if not pm.isNull()]
        W, pad = C.POPUP_WIDTH, 24
        inner = W - 2 * pad
        img_h = 125 if pms else 0
        title_font, set_font, hint_font = QtGui.QFont(*TITLE_FONT), QtGui.QFont(*SET_FONT), QtGui.QFont(*HINT_FONT)
        flags = QtCore.Qt.TextWordWrap
        title = item.get("title", "")
        set_name = str(item.get("set", "")).upper()
        title_h = QtGui.QFontMetrics(title_font).boundingRect(0, 0, inner, 1000, flags, title).height()
        set_h = QtGui.QFontMetrics(set_font).height()
        hint_h = QtGui.QFontMetrics(hint_font).height()
        doc = QtGui.QTextDocument()
        doc.setDefaultFont(QtGui.QFont(*BODY_FONT))
        doc.setTextWidth(inner)
        doc.setHtml(description_html(info.get("description", "")))
        doc_h = doc.size().height()

        H = img_h + pad + title_h + 10 + set_h + 10 + doc_h + 14 + hint_h + pad
        x = min(max(mx - W / 2, 8), bounds[0] - W - 8)
        above = my - marker_radius - 14 - H >= 8
        y = my - marker_radius - 14 - H if above else my + marker_radius + 14
        ax = min(max(mx, x + 30), x + W - 30)

        p.save()
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(122, 69, 119, 247))
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(x, y, W, H), 18, 18)
        p.drawPath(path)
        if above:
            tri = [QtCore.QPointF(ax - 10, y + H - 1), QtCore.QPointF(ax + 10, y + H - 1),
                   QtCore.QPointF(ax, y + H + 11)]
        else:
            tri = [QtCore.QPointF(ax - 10, y + 1), QtCore.QPointF(ax + 10, y + 1), QtCore.QPointF(ax, y - 11)]
        p.drawPolygon(QtGui.QPolygonF(tri))

        if pms:
            p.save()
            p.setClipPath(path)
            cw = W / len(pms)
            for k, pm in enumerate(pms):
                self._cover(p, pm, QtCore.QRectF(x + k * cw, y, cw, img_h))
            p.restore()

        ty = y + img_h + pad
        p.setPen(QtGui.QColor(255, 255, 255))
        p.setFont(title_font)
        p.drawText(QtCore.QRectF(x + pad, ty, inner, title_h), flags, title)
        ty += title_h + 10
        p.setPen(QtGui.QColor(255, 196, 120))
        p.setFont(set_font)
        p.drawText(QtCore.QRectF(x + pad, ty, inner, set_h), QtCore.Qt.AlignLeft, set_name)
        ty += set_h + 10
        p.save()
        p.translate(x + pad, ty)
        doc.drawContents(p)
        p.restore()
        ty += doc_h + 14
        p.setPen(QtGui.QColor(150, 230, 170) if found else QtGui.QColor(255, 190, 210))
        p.setFont(hint_font)
        verb = mark_button.upper()
        text = f"FOUND  ({verb}-CLICK MARKER TO UNDO)" if found else f"{verb}-CLICK MARKER TO MARK FOUND"
        p.drawText(QtCore.QRectF(x + pad, ty, inner, hint_h), QtCore.Qt.AlignHCenter, text)
        p.restore()
