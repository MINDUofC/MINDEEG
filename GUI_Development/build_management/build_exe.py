"""
Comprehensive Build Script for MINDStream EEG Application
==========================================================

This script creates a single-file executable with flexible dependency management.
It handles common PyInstaller issues and provides easy ways to add missing dependencies.

Usage:
    python build_exe.py                    # Build with config file
    python build_exe.py --debug            # Build with console window for debugging
    python build_exe.py --add-module XXX   # Add a specific module to hidden imports
    python build_exe.py --analyze          # Analyze dependencies without building
"""

import os
import sys
import json
import subprocess
import shutil
import argparse
from pathlib import Path
import site
import importlib.util


class BuildManager:
    def __init__(self, config_file="build_config.json"):
        self.script_dir = Path(__file__).parent.resolve()
        self.config_file = self.script_dir / config_file
        self.config = self.load_config()
        self.spec_file = self.script_dir / f"{self.config['app_name']}.spec"
        self.runtime_hooks = []
        
    def load_config(self):
        """Load build configuration from JSON file"""
        if not self.config_file.exists():
            print(f"❌ Error: Configuration file '{self.config_file}' not found!")
            sys.exit(1)
            
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_config(self):
        """Save updated configuration back to JSON file"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
        print(f"✅ Configuration saved to {self.config_file}")
    
    def add_hidden_import(self, module_name):
        """Add a module to hidden imports list"""
        if module_name not in self.config['hidden_imports']:
            self.config['hidden_imports'].append(module_name)
            self.save_config()
            print(f"✅ Added '{module_name}' to hidden imports")
        else:
            print(f"ℹ️  '{module_name}' already in hidden imports")
    
    def add_data_file(self, source, destination="."):
        """Add a data file to be included in the build"""
        data_entry = {"source": source, "destination": destination}
        if data_entry not in self.config['data_files']:
            self.config['data_files'].append(data_entry)
            self.save_config()
            print(f"✅ Added data file: {source} -> {destination}")
        else:
            print(f"ℹ️  Data file already configured")
    
    def add_binary_file(self, source, destination="."):
        """Add a binary/DLL file to be included"""
        binary_entry = {"source": source, "destination": destination}
        if binary_entry not in self.config['binary_files']:
            self.config['binary_files'].append(binary_entry)
            self.save_config()
            print(f"✅ Added binary file: {source} -> {destination}")
        else:
            print(f"ℹ️  Binary file already configured")
    
    def find_package_location(self, package_name):
        """Find the installation location of a package"""
        try:
            spec = importlib.util.find_spec(package_name)
            if spec and spec.origin:
                return Path(spec.origin).parent
        except (ImportError, AttributeError, ValueError):
            pass
        
        # Try site-packages
        for site_dir in site.getsitepackages():
            pkg_path = Path(site_dir) / package_name
            if pkg_path.exists():
                return pkg_path
        
        return None
    
    def auto_detect_gpt4all_dlls(self):
        """Automatically detect and add gpt4all DLLs"""
        print("🔍 Searching for gpt4all DLLs...")
        gpt4all_path = self.find_package_location("gpt4all")
        
        if not gpt4all_path:
            print("⚠️  Warning: Could not locate gpt4all package")
            return
        
        # Search for DLLs in gpt4all directory
        dll_patterns = ['.dll', '.so', '.dylib', '.pyd']
        found_dlls = []
        
        for pattern in dll_patterns:
            found_dlls.extend(list(gpt4all_path.rglob(f"*{pattern}")))
        
        if found_dlls:
            print(f"✅ Found {len(found_dlls)} gpt4all library files:")
            for dll in found_dlls:
                print(f"   - {dll.name}")
                # Add to binary files
                binary_entry = {
                    "source": str(dll),
                    "destination": "gpt4all"
                }
                if binary_entry not in self.config['binary_files']:
                    self.config['binary_files'].append(binary_entry)
            self.save_config()
        else:
            print("⚠️  No gpt4all library files found")
    
    def auto_detect_brainflow_libs(self):
        """Automatically detect and add brainflow libraries"""
        print("🔍 Searching for brainflow libraries...")
        brainflow_path = self.find_package_location("brainflow")
        
        if not brainflow_path:
            print("⚠️  Warning: Could not locate brainflow package")
            return
        
        # Search for library files
        lib_patterns = ['.dll', '.so', '.dylib']
        found_libs = []
        
        for pattern in lib_patterns:
            found_libs.extend(list(brainflow_path.rglob(f"*{pattern}")))
        
        if found_libs:
            print(f"✅ Found {len(found_libs)} brainflow library files:")
            for lib in found_libs:
                print(f"   - {lib.name}")
                binary_entry = {
                    "source": str(lib),
                    "destination": "brainflow"
                }
                if binary_entry not in self.config['binary_files']:
                    self.config['binary_files'].append(binary_entry)
            self.save_config()
        else:
            print("⚠️  No brainflow library files found")
    
    def auto_detect_vispy_shaders(self):
        """Automatically detect and add vispy shader files"""
        print("🔍 Searching for vispy shader files...")
        vispy_path = self.find_package_location("vispy")
        
        if not vispy_path:
            print("⚠️  Warning: Could not locate vispy package")
            return
        
        # Search for shader files
        shader_dirs = list(vispy_path.rglob("glsl"))
        
        if shader_dirs:
            for shader_dir in shader_dirs:
                print(f"✅ Found vispy shaders at: {shader_dir}")
                data_entry = {
                    "source": f"{shader_dir}/*",
                    "destination": f"vispy/{shader_dir.relative_to(vispy_path)}"
                }
                if data_entry not in self.config['data_files']:
                    self.config['data_files'].append(data_entry)
            self.save_config()
        else:
            print("⚠️  No vispy shader files found")
    
    def verify_dependencies(self):
        """Verify that all required packages are installed"""
        print("\nVerifying dependencies...")
        missing = []
        
        for module in self.config['hidden_imports']:
            base_module = module.split('.')[0]
            try:
                __import__(base_module)
                print(f"[OK] {base_module}")
            except ImportError:
                print(f"[MISSING] {base_module} - NOT FOUND")
                missing.append(base_module)
        
        if missing:
            print(f"\n[WARNING] Missing packages: {', '.join(set(missing))}")
            print("Install with: pip install " + " ".join(set(missing)))
            return False
        
        print("\n[OK] All dependencies verified!")
        return True
    
    def generate_spec_file(self, debug=False):
        """Generate PyInstaller .spec file with all configurations"""
        print("\nGenerating .spec file...")
        
        # Prepare data files list
        datas = []
        for data in self.config['data_files']:
            source = data['source']
            dest = data['destination']
            datas.append(f"(r'{source}', r'{dest}')")
        
        # Prepare binary files list
        binaries = []
        for binary in self.config['binary_files']:
            source = binary['source']
            dest = binary['destination']
            binaries.append(f"(r'{source}', r'{dest}')")
        
        # Prepare hidden imports
        hiddenimports = [f"'{imp}'" for imp in self.config['hidden_imports']]
        
        # Prepare excludes
        excludes = [f"'{exc}'" for exc in self.config['exclude_modules']]
        
        # Build options
        opts = self.config['pyinstaller_options']
        
        # Check if splash image exists
        splash_img_path = self.config.get('splash_image', '')
        splash_img_full = self.script_dir / splash_img_path if splash_img_path else None
        has_splash = splash_img_full and splash_img_full.exists()
        
        # Prepare runtime hooks
        runtime_hooks_entries = ",".join([f"r'{str(p)}'" for p in self.runtime_hooks])

        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# Auto-generated PyInstaller spec file
# Generated by build_exe.py

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    [r'{self.config["main_script"]}'],
    pathex=[r'{self.script_dir}'],
    binaries=[
        {','.join(binaries) if binaries else ''}
    ],
    datas=[
        {','.join(datas) if datas else ''}
    ],
    hiddenimports=[
        {','.join(hiddenimports)}
    ],
    hookspath=[r'{self.script_dir / "hooks"}'],
    hooksconfig={{}},
    runtime_hooks=[{runtime_hooks_entries}],
    excludes=[
        {','.join(excludes)}
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

{f"""
splash = Splash(
    r'{splash_img_full}',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    text_size=12,
    minify_script=True,
    always_on_top=True,
)
""" if has_splash else ""}

exe = EXE(
    pyz,
    a.scripts,
    {f'splash,' if has_splash else ''}
    {'a.binaries,' if opts['onefile'] else ''}
    {'a.zipfiles,' if opts['onefile'] else ''}
    {'a.datas,' if opts['onefile'] else ''}
    {'[],' if not opts['onefile'] else ''}
    {'exclude_binaries=True,' if not opts['onefile'] else ''}
    name='{self.config["app_name"]}',
    debug={str(debug or opts['debug'])},
    bootloader_ignore_signals=False,
    strip={str(opts['strip'])},
    upx={str(opts['upx'])},
    upx_exclude={self.config['upx_exclude']},
    runtime_tmpdir={repr(opts['runtime_tmpdir'])},
    console={str(debug or not opts['windowed'])},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'{self.config.get("icon", "")}',
)

{'"""' if opts['onefile'] else ''}
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    {f'splash.binaries,' if has_splash else ''}
    strip={str(opts['strip'])},
    upx={str(opts['upx'])},
    upx_exclude={self.config['upx_exclude']},
    name='{self.config["app_name"]}',
)
{'"""' if opts['onefile'] else ''}
'''
        
        with open(self.spec_file, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        print(f"[OK] Spec file generated: {self.spec_file}")
        return self.spec_file
    
    def create_hooks_directory(self):
        """Create hooks directory with custom hooks for problematic packages"""
        hooks_dir = self.script_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        
        # Hook for gpt4all
        gpt4all_hook = hooks_dir / "hook-gpt4all.py"
        with open(gpt4all_hook, 'w', encoding='utf-8') as f:
            f.write("""# PyInstaller hook for gpt4all
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas, binaries, hiddenimports = collect_all('gpt4all')

# Ensure all DLLs are included
binaries += collect_dynamic_libs('gpt4all')

# Add specific hidden imports
hiddenimports += [
    'gpt4all.gpt4all',
    'gpt4all.pyllmodel',
]
""")
        
        # Hook for brainflow
        brainflow_hook = hooks_dir / "hook-brainflow.py"
        with open(brainflow_hook, 'w', encoding='utf-8') as f:
            f.write("""# PyInstaller hook for brainflow
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
""")
        
        # Hook for vispy
        vispy_hook = hooks_dir / "hook-vispy.py"
        with open(vispy_hook, 'w', encoding='utf-8') as f:
            f.write("""# PyInstaller hook for vispy
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
""")
        
        # Hook for PyQt5
        pyqt5_hook = hooks_dir / "hook-PyQt5.py"
        with open(pyqt5_hook, 'w', encoding='utf-8') as f:
            f.write("""# PyInstaller hook for PyQt5
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('PyQt5')

hiddenimports += [
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtPrintSupport',
    'PyQt5.uic',
]
""")
        
        # Runtime hook: load bundled fonts (e.g., Montserrat) AFTER QApplication is created
        rthook_fonts = hooks_dir / "rthook-fonts.py"
        with open(rthook_fonts, 'w', encoding='utf-8') as f:
            f.write("""# PyInstaller runtime hook: ensure bundled fonts load after QApplication is initialized
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
""")
        # Register runtime hook for spec generation
        self.runtime_hooks.append(rthook_fonts)
        
        print(f"[OK] Created custom hooks in {hooks_dir}")
    
    def build(self, debug=False, clean=True):
        """Execute the build process"""
        print("\n" + "="*70)
        print("Starting build process for MINDStream EEG Application")
        print("="*70 + "\n")
        
        # Step 1: Verify dependencies
        if not self.verify_dependencies():
            response = input("\nContinue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Build cancelled.")
                return False
        
        # Step 2: Auto-detect package files
        print("\nAuto-detecting package files...")
        self.auto_detect_gpt4all_dlls()
        self.auto_detect_brainflow_libs()
        self.auto_detect_vispy_shaders()
        
        # Step 3: Create hooks
        self.create_hooks_directory()
        
        # Step 4: Generate spec file
        spec_file = self.generate_spec_file(debug=debug)
        
        # Step 5: Run PyInstaller
        print("\nRunning PyInstaller...")
        cmd = [
            sys.executable,
            "-m", "PyInstaller",
            str(spec_file),
            "--noconfirm"
        ]
        
        if clean:
            cmd.append("--clean")
        
        print(f"Command: {' '.join(cmd)}\n")
        
        try:
            result = subprocess.run(cmd, check=True, cwd=self.script_dir)
            
            print("\n" + "="*70)
            print("BUILD SUCCESSFUL!")
            print("="*70)
            
            # Find the output file
            if self.config['pyinstaller_options']['onefile']:
                output_file = self.script_dir / "dist" / f"{self.config['app_name']}.exe"
            else:
                output_file = self.script_dir / "dist" / self.config['app_name']
            
            if output_file.exists():
                print(f"\nExecutable location: {output_file}")
                print(f"File size: {output_file.stat().st_size / (1024*1024):.2f} MB")
            
            print("\nTips:")
            print("   - Test the executable in a fresh environment")
            print("   - If you get 'module not found' errors, use:")
            print("     python build_exe.py --add-module <module_name>")
            print("   - For DLL errors, copy the DLL to the same folder and use:")
            print("     python build_exe.py --add-dll <dll_path>")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print("\n" + "="*70)
            print("BUILD FAILED!")
            print("="*70)
            print(f"\nError: {e}")
            print("\nTroubleshooting:")
            print("   1. Check the error message above")
            print("   2. Try building with --debug flag to see console output")
            print("   3. Add missing modules with --add-module")
            print("   4. Check build_config.json for configuration")
            return False
    
    def analyze_imports(self):
        """Analyze and display all imports used in the project"""
        print("\n🔍 Analyzing project imports...")
        
        main_script = self.script_dir / self.config['main_script']
        project_dir = main_script.parent
        
        imports = set()
        
        # Recursively find all Python files
        for py_file in project_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('import '):
                            module = line.split()[1].split('.')[0]
                            imports.add(module)
                        elif line.startswith('from '):
                            module = line.split()[1].split('.')[0]
                            imports.add(module)
            except Exception:
                continue
        
        print(f"\n📦 Found {len(imports)} unique imported modules:")
        for imp in sorted(imports):
            status = "✅" if imp in [m.split('.')[0] for m in self.config['hidden_imports']] else "⚠️ "
            print(f"   {status} {imp}")
        
        # Suggest additions
        missing = imports - set(m.split('.')[0] for m in self.config['hidden_imports'])
        if missing:
            print(f"\n💡 Consider adding these to hidden_imports:")
            for module in sorted(missing):
                print(f"   - {module}")


def main():
    parser = argparse.ArgumentParser(
        description="Build MINDStream EEG Application to executable",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_exe.py                           # Normal build
  python build_exe.py --debug                   # Build with console for debugging
  python build_exe.py --add-module numpy        # Add numpy to hidden imports
  python build_exe.py --add-dll mydll.dll       # Add a DLL to the build
  python build_exe.py --analyze                 # Analyze project imports
        """
    )
    
    parser.add_argument('--debug', action='store_true',
                        help='Build with console window for debugging')
    parser.add_argument('--no-clean', action='store_true',
                        help='Don\'t clean previous build files')
    parser.add_argument('--add-module', metavar='MODULE',
                        help='Add a module to hidden imports')
    parser.add_argument('--add-data', nargs=2, metavar=('SOURCE', 'DEST'),
                        help='Add a data file (source destination)')
    parser.add_argument('--add-dll', nargs=2, metavar=('SOURCE', 'DEST'),
                        help='Add a DLL/binary file (source destination)')
    parser.add_argument('--analyze', action='store_true',
                        help='Analyze project imports without building')
    
    args = parser.parse_args()
    
    # Initialize build manager
    manager = BuildManager()
    
    # Handle special commands
    if args.add_module:
        manager.add_hidden_import(args.add_module)
        return
    
    if args.add_data:
        manager.add_data_file(args.add_data[0], args.add_data[1])
        return
    
    if args.add_dll:
        manager.add_binary_file(args.add_dll[0], args.add_dll[1])
        return
    
    if args.analyze:
        manager.analyze_imports()
        return
    
    # Normal build
    success = manager.build(debug=args.debug, clean=not args.no_clean)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

