# PyInstaller hook for vispy
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas, binaries, hiddenimports = collect_all('vispy')

# Include shader files and other data
datas += collect_data_files('vispy', include_py_files=False)

hiddenimports += [
    'vispy.scene',
    'vispy.visuals',
    'vispy.color',
    'vispy.app',
    'vispy.gloo',
    'vispy.glsl',
]
