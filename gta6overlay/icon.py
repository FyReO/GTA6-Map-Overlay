from PyQt5 import QtCore, QtGui


def render_icon(size=256):
    img = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    img.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    s = size / 256.0
    grad = QtGui.QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QtGui.QColor("#8b5cf6"))
    grad.setColorAt(1, QtGui.QColor("#4f6bff"))
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(QtCore.QRectF(8 * s, 8 * s, 240 * s, 240 * s), 56 * s, 56 * s)

    pin = QtGui.QPainterPath()
    cx, cy, r = 128 * s, 104 * s, 54 * s
    pin.addEllipse(QtCore.QPointF(cx, cy), r, r)
    tip = QtGui.QPainterPath()
    tip.moveTo(cx - r * 0.86, cy + r * 0.5)
    tip.lineTo(cx, 206 * s)
    tip.lineTo(cx + r * 0.86, cy + r * 0.5)
    tip.closeSubpath()
    p.setBrush(QtGui.QColor("#ffffff"))
    p.drawPath(pin.united(tip))
    p.setBrush(QtGui.QColor("#5b5fe0"))
    p.drawEllipse(QtCore.QPointF(cx, cy), 21 * s, 21 * s)
    p.end()
    return img


def app_icon():
    icon = QtGui.QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QtGui.QPixmap.fromImage(render_icon(size)))
    return icon
