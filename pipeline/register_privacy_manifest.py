"""Register PrivacyInfo.xcprivacy in the Xcode project so it is actually bundled.
Without a PBXBuildFile + Resources entry the file sits on disk and never ships."""
import re
import subprocess
import sys
from pathlib import Path

PBX = Path('ios/App/App.xcodeproj/project.pbxproj')
FILEREF = '9E1A7B4C2D3F4051627384A5'
BUILD = '8D3C6F1B5A2E4079685A3D2C'

s = PBX.read_text()
if 'PrivacyInfo.xcprivacy' in s:
    print('already registered — nothing to do')
    sys.exit(0)
for token in (FILEREF, BUILD):
    if token in s:
        sys.exit(f'id collision on {token}; pick another')

# 1. PBXBuildFile entry, next to the other bundled resources
anchor_build = '\t\t50379B232058CBB4000EE86E /* capacitor.config.json in Resources */ = {isa = PBXBuildFile; fileRef = 50379B222058CBB4000EE86E /* capacitor.config.json */; };\n'
assert anchor_build in s
s = s.replace(anchor_build, anchor_build +
    f'\t\t{BUILD} /* PrivacyInfo.xcprivacy in Resources */ = {{isa = PBXBuildFile; fileRef = {FILEREF} /* PrivacyInfo.xcprivacy */; }};\n')

# 2. PBXFileReference entry
anchor_ref = '\t\t504EC3131FED79650016851F /* Info.plist */ = {isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = Info.plist; sourceTree = "<group>"; };\n'
assert anchor_ref in s
s = s.replace(anchor_ref, anchor_ref +
    f'\t\t{FILEREF} /* PrivacyInfo.xcprivacy */ = {{isa = PBXFileReference; lastKnownFileType = text.xml; path = PrivacyInfo.xcprivacy; sourceTree = "<group>"; }};\n')

# 3. show it in the App group, beside Info.plist
anchor_group = '\t\t\t\t504EC3131FED79650016851F /* Info.plist */,\n'
assert anchor_group in s
s = s.replace(anchor_group, anchor_group + f'\t\t\t\t{FILEREF} /* PrivacyInfo.xcprivacy */,\n', 1)

# 4. add it to the Resources build phase
anchor_phase = '\t\t\t\t50379B232058CBB4000EE86E /* capacitor.config.json in Resources */,\n'
assert anchor_phase in s
s = s.replace(anchor_phase, anchor_phase + f'\t\t\t\t{BUILD} /* PrivacyInfo.xcprivacy in Resources */,\n', 1)

PBX.write_text(s)
print('registered in project.pbxproj')
print(subprocess.run(['plutil', '-lint', str(PBX)], capture_output=True, text=True).stdout.strip())
