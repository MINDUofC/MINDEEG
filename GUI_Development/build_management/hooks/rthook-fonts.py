# PyInstaller runtime hook: ensure bundled fonts load after QApplication is initialized
from pathlib import Path
import sys


def _font_loader():
    try:
        from PyQt5.QtGui import QFontDatabase, QFont
    except Exception:
        return

    search_dirs = []

    # 1) PyInstaller onefile temp dir
    try:
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            search_dirs.append(Path(meipass) / 'resources' / 'fonts')
    except Exception:
        pass

    # 2) Onedir distribution: next to executable
    try:
        exe_dir = Path(sys.executable).resolve().parent
        search_dirs.append(exe_dir / 'resources' / 'fonts')
    except Exception:
        pass

    # 3) Dev fallback (running from source)
    try:
        script_dir = Path(__file__).resolve().parent
        gui_root = script_dir.parent
        search_dirs.append(gui_root / 'resources' / 'fonts')
    except Exception:
        pass

    for d in search_dirs:
        try:
            if not d.exists():
                continue
            for ext in ('*.ttf', '*.otf'):
                for fp in d.glob(ext):
                    try:
                        QFontDatabase.addApplicationFont(str(fp))
                    except Exception:
                        pass
        except Exception:
            continue

    # Helpful substitutions so CSS like "Montserrat SemiBold" resolves
    try:
        QFont.insertSubstitution('Montserrat SemiBold', 'Montserrat')
        QFont.insertSubstitution('Montserrat Bold', 'Montserrat')
        QFont.insertSubstitution('Montserrat Medium', 'Montserrat')
        QFont.insertSubstitution('Montserrat Regular', 'Montserrat')
        QFont.insertSubstitution('Montserrat-Light', 'Montserrat')
        QFont.insertSubstitution('Montserrat Light', 'Montserrat')
        QFont.insertSubstitution('Montserrat-SemiBold', 'Montserrat')
        QFont.insertSubstitution('Montserrat-Bold', 'Montserrat')
    except Exception:
        pass


# Defer font loading until after QApplication is constructed
try:
    from PyQt5.QtWidgets import QApplication
    _orig_qapp_init = QApplication.__init__

    def _patched_init(self, *args, **kwargs):
        _orig_qapp_init(self, *args, **kwargs)
        try:
            _font_loader()
        except Exception:
            pass

    QApplication.__init__ = _patched_init
except Exception:
    pass
