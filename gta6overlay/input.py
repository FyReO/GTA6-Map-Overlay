import logging

from PyQt5 import QtCore

log = logging.getLogger(__name__)

HOTKEYS = (
    ("<ctrl>+<alt>+s", "settings", "Show / hide this window"),
    ("<ctrl>+<alt>+h", "overlay", "Show / hide the overlay"),
    ("<ctrl>+<alt>+m", "click", "Turn marker clicking on / off"),
    ("<ctrl>+<alt>+f", "found", "Show / hide collected markers"),
    ("<ctrl>+<alt>+z", "undo", "Undo the last marked item"),
)


def hotkey_label(spec):
    return " + ".join(part.strip("<>").capitalize() for part in spec.split("+"))


class InputHooks(QtCore.QObject):
    click = QtCore.pyqtSignal(str)
    hotkey = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.available = False
        self._mouse = None
        self._keys = None

    def start(self):
        try:
            from pynput import keyboard, mouse
        except Exception as exc:
            log.warning("pynput unavailable, clicks and hotkeys disabled: %s", exc)
            return False

        def on_click(x, y, button, pressed):
            if pressed:
                self.click.emit(getattr(button, "name", ""))

        try:
            self._mouse = mouse.Listener(on_click=on_click)
            self._mouse.daemon = True
            self._mouse.start()
            bindings = {spec: (lambda name=name: self.hotkey.emit(name)) for spec, name, _ in HOTKEYS}
            self._keys = keyboard.GlobalHotKeys(bindings)
            self._keys.daemon = True
            self._keys.start()
        except Exception as exc:
            log.warning("could not start input listeners: %s", exc)
            return False
        self.available = True
        return True

    def stop(self):
        for listener in (self._mouse, self._keys):
            if listener is not None:
                listener.stop()
