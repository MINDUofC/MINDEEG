# PyInstaller hook for brainflow
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_data_files

datas, binaries, hiddenimports = collect_all('brainflow')

# Ensure all shared libraries are included
binaries += collect_dynamic_libs('brainflow')

# Add data files if any
datas += collect_data_files('brainflow', include_py_files=False)

hiddenimports += [
    'brainflow.board_shim',
    'brainflow.data_filter',
    'brainflow.ml_model',
]
