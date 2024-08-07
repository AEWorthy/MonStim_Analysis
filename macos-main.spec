# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import subprocess

from PyInstaller.config import CONF

main_path = os.path.abspath('main.py')
base_path = os.path.dirname(main_path)

# Main Build
a = Analysis(
    ['main.py'],
    pathex=[base_path, os.path.join(base_path, 'monsit_gui'), os.path.join(base_path, 'monstim_analysis'), os.path.join(base_path, 'monstim_converter')],
    binaries=[],
    datas=[(os.path.join(base_path, 'src', 'icon.png'), 'src'), (os.path.join(base_path, 'src', 'icon.icns'), 'src'), (os.path.join(base_path, 'readme.md'), 'src')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='macos-monstim-analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=['PyQt6'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None, #'Andrew Worthy',
    entitlements_file=None, #'Entitlements.plist',
    icon='src/icon.icns',
)
app = BUNDLE(
    exe,
    name='MonStim Analyzer v1.0.app',
    icon='src/icon.icns',
    bundle_identifier=None,
    codesign_identity=None, #'Andrew Worthy',
    entitlements_file=None,#'Entitlements.plist',
)

# Copy the config/readme to the dist directory
os.makedirs(CONF['distpath'], exist_ok=True)
shutil.copy2('config.yml', os.path.join(CONF['distpath']))
shutil.copy2('readme.md', os.path.join(CONF['distpath']))

app_path = os.path.join(CONF['distpath'], 'MonStim Analyzer v1.0.app')
exe_path = os.path.join(app_path, 'Contents', 'MacOS', 'macos-monstim-analyzer')

# # Optionally, add LSUIElement to Info.plist
# info_plist_path = os.path.join(app_path, 'Contents', 'Info.plist')
# with open(info_plist_path, 'r') as f:
#     info_plist = f.read()

# if 'LSUIElement' not in info_plist:
#     info_plist = info_plist.replace('</dict>', '    <key>LSUIElement</key>\n    <string>1</string>\n</dict>')
#     with open(info_plist_path, 'w') as f:
#         f.write(info_plist)

# Sign the application with the entitlements
subprocess.call([
    'codesign', '--deep', '--force', '--verify', '--verbose',
    '--sign', 'Andrew Worthy',
    '--entitlements', 'Entitlements.plist',
    '--options', 'runtime',
    app_path
])

# Remove quarantine attribute (use with caution, not recommended for distribution)
# os.system(f'xattr -rd com.apple.quarantine "{app_path}"')

# Verify codesign
def verify_codesign(app_path):
    try:
        result = subprocess.run(['codesign', '--verify', '--verbose=2', app_path], capture_output=True, check=True, text=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Verification failed: {e}")
        print(e.stderr)

# verify_codesign(exe_path)
verify_codesign(app_path)

# # Optionally, you can also check the entitlements
# print("Entitlements for executable:")
# subprocess.call(['codesign', '-d', '--entitlements', ':-', exe_path])
# print("\nEntitlements for .app bundle:")
# subprocess.call(['codesign', '-d', '--entitlements', ':-', app_path])