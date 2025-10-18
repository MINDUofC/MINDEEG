# PyInstaller hook for PyQt5
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('PyQt5')

hiddenimports += [
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtPrintSupport',
    'PyQt5.uic',
]
