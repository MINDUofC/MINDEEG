# PyInstaller hook for gpt4all
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas, binaries, hiddenimports = collect_all('gpt4all')

# Ensure all DLLs are included
binaries += collect_dynamic_libs('gpt4all')

# Add specific hidden imports
hiddenimports += [
    'gpt4all.gpt4all',
    'gpt4all.pyllmodel',
]
