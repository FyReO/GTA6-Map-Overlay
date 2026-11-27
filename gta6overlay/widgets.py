from PyQt5 import QtCore, QtGui, QtWidgets

ACCENT = "#6d7cff"

QSS = """
QWidget { color: #e7e9ee; font-family: 'Segoe UI Variable Text', 'Segoe UI', 'Inter', sans-serif; font-size: 9pt; }
QWidget#root { background: #14161b; }
QLabel { background: transparent; }
QLabel#title { font-size: 13pt; font-weight: 600; }
QLabel#h2 { font-size: 10pt; font-weight: 600; }
QLabel#muted { color: #8b93a3; font-size: 8pt; }
QLabel#big { font-size: 20pt; font-weight: 600; }
QFrame#card, QFrame#group { background: #1b1e25; border: 1px solid #272b35; border-radius: 10px; }
QFrame#banner { background: #232a4a; border: 1px solid #3a4590; border-radius: 10px; }
QFrame#sep { background: #272b35; max-height: 1px; min-height: 1px; border: none; }
QPushButton { border-radius: 7px; padding: 6px 14px; border: 1px solid #2c303b; background: #1b1e25; color: #c9cdd8; }
QPushButton:hover { background: #242836; border-color: #3a4052; }
QPushButton:disabled { color: #596070; background: #181a20; }
QPushButton#primary { background: #6d7cff; border-color: #6d7cff; color: #ffffff; font-weight: 600; }
QPushButton#primary:hover { background: #8290ff; border-color: #8290ff; }
QPushButton#primary:disabled { background: #2c3358; border-color: #2c3358; color: #7b83ad; }
QPushButton#youtube { background: #e5453d; border-color: #e5453d; color: #ffffff; font-weight: 600; padding: 9px 14px; }
QPushButton#youtube:hover { background: #f05a52; border-color: #f05a52; }
QPushButton#donate { background: #f2b544; border-color: #f2b544; color: #20190a; font-weight: 600; padding: 9px 14px; }
QPushButton#donate:hover { background: #f7c565; border-color: #f7c565; }
QPushButton#danger { color: #ff8b8b; }
QPushButton#danger:hover { background: #2e1d22; border-color: #5a2b33; }
QPushButton#gbtn { text-align: left; border: none; background: transparent; font-weight: 600; padding: 2px 0; }
QPushButton#gbtn:hover { background: transparent; }
QComboBox { background: #14161b; border: 1px solid #2c303b; border-radius: 7px; padding: 5px 10px; min-height: 18px; }
QComboBox:hover { border-color: #3a4052; }
QComboBox QAbstractItemView { background: #1b1e25; border: 1px solid #2c303b; selection-background-color: #6d7cff;
                              outline: 0; padding: 2px; }
QSlider::groove:horizontal { height: 4px; background: #2a2e3a; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #6d7cff; border-radius: 2px; }
QSlider::handle:horizontal { background: #ffffff; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QSlider::sub-page:horizontal:disabled { background: #3a3f4b; }
QSlider::handle:horizontal:disabled { background: #6b7280; }
QProgressBar { background: #232733; border: none; border-radius: 4px; max-height: 8px; min-height: 8px;
               text-align: center; color: transparent; }
QProgressBar::chunk { background: #6d7cff; border-radius: 4px; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: #8b93a3; padding: 9px 4px; border: none;
               border-bottom: 2px solid #272b35; font-weight: 600; }
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #6d7cff; }
QTabBar::tab:hover:!selected { color: #c9cdd8; border-bottom: 2px solid #3a4052; }
QAbstractScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px 0; }
QScrollBar::handle:vertical { background: #333846; border-radius: 3px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #454c5e; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QToolTip { background: #1b1e25; color: #e7e9ee; border: 1px solid #2c303b; padding: 3px 6px; }
QMessageBox, QFileDialog, QColorDialog { background: #14161b; }
"""


def muted(text, wrap=True):
    label = QtWidgets.QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(wrap)
    return label


def separator():
    line = QtWidgets.QFrame()
    line.setObjectName("sep")
    return line


class Switch(QtWidgets.QAbstractButton):
    def __init__(self, checked=False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(32, 18)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._partial = False

    def setPartial(self, value):
        if value != self._partial:
            self._partial = value
            self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        if not self.isEnabled():
            track, cx = QtGui.QColor("#2a2e3a"), (self.width() - 9 if self.isChecked() else 9)
        elif self._partial:
            track, cx = QtGui.QColor("#454d99"), self.width() / 2
        elif self.isChecked():
            track, cx = QtGui.QColor(ACCENT), self.width() - 9
        else:
            track, cx = QtGui.QColor("#3a3f4b"), 9
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QtCore.QRectF(0, 0, self.width(), self.height()), 9, 9)
        p.setBrush(QtGui.QColor("#ffffff" if self.isEnabled() else "#7b8190"))
        p.drawEllipse(QtCore.QPointF(cx, 9), 6.5, 6.5)


class Card(QtWidgets.QFrame):
    def __init__(self, title=None, subtitle=None):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.body = QtWidgets.QVBoxLayout(self)
        self.body.setContentsMargins(14, 12, 14, 12)
        self.body.setSpacing(10)
        if title:
            head = QtWidgets.QLabel(title)
            head.setObjectName("h2")
            self.body.addWidget(head)
        if subtitle:
            self.body.addWidget(muted(subtitle))

    def add(self, widget):
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout):
        self.body.addLayout(layout)
        return layout


class ToggleRow(QtWidgets.QWidget):
    clicked = QtCore.pyqtSignal(bool)

    def __init__(self, title, subtitle=None, checked=False):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(0)
        self.title = QtWidgets.QLabel(title)
        col.addWidget(self.title)
        self.subtitle = None
        if subtitle:
            self.subtitle = muted(subtitle)
            col.addWidget(self.subtitle)
        self.switch = Switch(checked)
        self.switch.clicked.connect(self.clicked)
        lay.addLayout(col, 1)
        lay.addWidget(self.switch, 0, QtCore.Qt.AlignVCenter)

    def set_checked(self, value):
        if self.switch.isChecked() != value:
            self.switch.setChecked(value)

    def set_subtitle(self, text):
        if self.subtitle is not None:
            self.subtitle.setText(text)


class SliderRow(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(int)

    def __init__(self, title, lo, hi, value, fmt="{}", hint=None):
        super().__init__()
        self.fmt = fmt
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        top = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLabel(title)
        self.value = QtWidgets.QLabel(fmt.format(value))
        self.value.setObjectName("muted")
        top.addWidget(self.title)
        top.addStretch(1)
        top.addWidget(self.value)
        lay.addLayout(top)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setValue(value)
        self.slider.valueChanged.connect(self._moved)
        lay.addWidget(self.slider)
        if hint:
            lay.addWidget(muted(hint))

    def _moved(self, v):
        self.value.setText(self.fmt.format(v))
        self.changed.emit(v)

    def set_value(self, v):
        if self.slider.value() != v:
            self.slider.blockSignals(True)
            self.slider.setValue(v)
            self.slider.blockSignals(False)
            self.value.setText(self.fmt.format(v))

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.title.setStyleSheet("" if enabled else "color: #596070;")


class ComboRow(QtWidgets.QWidget):
    picked = QtCore.pyqtSignal(object)

    def __init__(self, title, items=(), extra=None, hint=None):
        super().__init__()
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(QtWidgets.QLabel(title))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.combo = QtWidgets.QComboBox()
        self.combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setMinimumContentsLength(12)
        row.addWidget(self.combo, 1)
        if extra is not None:
            row.addWidget(extra)
        lay.addLayout(row)
        if hint:
            lay.addWidget(muted(hint))
        self.set_items(items)
        self.combo.activated.connect(lambda i: self.picked.emit(self.combo.itemData(i)))

    def set_items(self, items, current=None):
        self.combo.blockSignals(True)
        self.combo.clear()
        for label, data in items:
            self.combo.addItem(label, data)
        self.set_current(current)
        self.combo.blockSignals(False)

    def set_current(self, data):
        i = self.combo.findData(data)
        if i >= 0:
            self.combo.setCurrentIndex(i)


class GroupSection(QtWidgets.QFrame):
    def __init__(self, engine, group, ids, collapsed, on_change, on_pick):
        super().__init__()
        self.engine, self.group, self.ids = engine, group, ids
        self.collapsed, self.on_change, self.on_pick = collapsed, on_change, on_pick
        self.setObjectName("group")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(head)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.setSpacing(8)
        self.btn = QtWidgets.QPushButton()
        self.btn.setObjectName("gbtn")
        self.btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn.clicked.connect(self.toggle_open)
        self.count = QtWidgets.QLabel("")
        self.count.setObjectName("muted")
        self.master = Switch()
        self.master.setToolTip("Show or hide this whole group")
        self.master.clicked.connect(self._master_clicked)
        hl.addWidget(self.btn, 1)
        hl.addWidget(self.count)
        hl.addWidget(self.master)
        lay.addWidget(head)

        self.body = QtWidgets.QWidget()
        bl = QtWidgets.QVBoxLayout(self.body)
        bl.setContentsMargins(12, 0, 12, 8)
        bl.setSpacing(0)
        self.dots, self.switches, self.counts = {}, {}, {}
        for i in ids:
            row = QtWidgets.QWidget()
            rl = QtWidgets.QHBoxLayout(row)
            rl.setContentsMargins(0, 3, 0, 3)
            rl.setSpacing(9)
            dot = QtWidgets.QPushButton()
            dot.setFixedSize(14, 14)
            dot.setCursor(QtCore.Qt.PointingHandCursor)
            dot.setToolTip("Change colour")
            dot.clicked.connect(lambda _=False, i=i: self.on_pick(i))
            cnt = QtWidgets.QLabel("")
            cnt.setObjectName("muted")
            sw = Switch(bool(engine.set_on[i]))
            sw.clicked.connect(lambda on, i=i: self._row_clicked(i, on))
            rl.addWidget(dot)
            rl.addWidget(QtWidgets.QLabel(engine.catalog.set_names[i]), 1)
            rl.addWidget(cnt)
            rl.addWidget(sw)
            bl.addWidget(row)
            self.dots[i], self.switches[i], self.counts[i] = dot, sw, cnt
            self.restyle(i)
        lay.addWidget(self.body)
        self._apply_open()

    def _apply_open(self):
        opened = self.group not in self.collapsed
        self.body.setVisible(opened)
        self.btn.setText(("▾  " if opened else "▸  ") + self.group)

    def toggle_open(self):
        if self.group in self.collapsed:
            self.collapsed.remove(self.group)
        else:
            self.collapsed.append(self.group)
        self._apply_open()
        self.on_change()

    def _row_clicked(self, i, on):
        self.engine.set_enabled(i, on)
        self.on_change()
        self.refresh(None)

    def _master_clicked(self, on):
        self.engine.set_many_enabled(self.ids, on)
        self.on_change()
        self.refresh(None)

    def restyle(self, i):
        self.dots[i].setStyleSheet(
            f"QPushButton {{ background: {self.engine.set_colors[i]}; padding: 0;"
            f" border: 1px solid rgba(255,255,255,70); border-radius: 7px; }}"
            f"QPushButton:hover {{ border: 1px solid #ffffff; }}")

    def refresh(self, got):
        on = [bool(self.engine.set_on[i]) for i in self.ids]
        for i, state in zip(self.ids, on):
            if self.switches[i].isChecked() != state:
                self.switches[i].setChecked(state)
        self.master.setChecked(all(on))
        self.master.setPartial(any(on) and not all(on))
        if got is not None:
            total = self.engine.catalog.set_totals()
            for i in self.ids:
                self.counts[i].setText(f"{got[i]}/{total[i]}")
            self.count.setText(f"{sum(got[i] for i in self.ids)}/{sum(total[i] for i in self.ids)}")
