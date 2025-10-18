# PyInstaller hook for scipy - additional coverage
from PyInstaller.utils.hooks import collect_submodules

# Collect all scipy submodules to ensure nothing is missed
hiddenimports = collect_submodules('scipy.special')
hiddenimports += collect_submodules('scipy.signal')
hiddenimports += collect_submodules('scipy.ndimage')
hiddenimports += collect_submodules('scipy.interpolate')
hiddenimports += collect_submodules('scipy._lib')

# CRITICAL: scipy._lib.array_api_compat - compatibility layer for array backends
# Include ALL backends to prevent ModuleNotFoundError
hiddenimports += [
    'scipy._lib.array_api_compat',
    'scipy._lib.array_api_compat.common',
    'scipy._lib.array_api_compat.numpy',
    'scipy._lib.array_api_compat.numpy.fft',
    'scipy._lib.array_api_compat.numpy.linalg',
    'scipy._lib.array_api_compat.cupy',
    'scipy._lib.array_api_compat.dask',
    'scipy._lib.array_api_compat.torch',
]

# Add specific C extension modules
hiddenimports += [
    'scipy.special._ufuncs',
    'scipy.special._ufuncs_cxx',
    'scipy.linalg.cython_blas',
    'scipy.linalg.cython_lapack',
    'scipy._lib.messagestream',
]

