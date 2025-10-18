# PyInstaller hook for rapidfuzz
# Fixes warning: "Failed to process hook entry point 'rapidfuzz.__pyinstaller:get_hook_dirs'"

from PyInstaller.utils.hooks import collect_all

# Collect all rapidfuzz components
datas, binaries, hiddenimports = collect_all('rapidfuzz')

# Ensure all submodules are included
hiddenimports += [
    'rapidfuzz.fuzz',
    'rapidfuzz.process',
    'rapidfuzz.distance',
    'rapidfuzz.utils',
]

