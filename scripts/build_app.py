"""在目标平台构建自包含程序，并运行不操作游戏的离线自检。"""

import argparse
import hashlib
import json
import importlib.metadata
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_paths import VERSION


def build(model):
    model = Path(model).expanduser().resolve()
    if not model.is_file() or model.suffix.lower() != '.pt':
        raise ValueError('请通过 --model 指定存在的 .pt 权重文件。')
    if sys.platform not in ('win32', 'darwin'):
        raise RuntimeError('请在 Windows 或 macOS 上构建对应平台程序。')
    label = ('windows' if sys.platform == 'win32' else 'macos') + '-' + platform.machine().lower()
    stage = ROOT / 'build' / label
    stage.mkdir(parents=True, exist_ok=True)
    staged_model = stage / 'best.pt'
    shutil.copyfile(model, staged_model)
    fingerprint = hashlib.sha256(staged_model.read_bytes()).hexdigest()
    licenses = stage / 'licenses'
    licenses.mkdir(exist_ok=True)
    for distribution in importlib.metadata.distributions():
        for file in distribution.files or []:
            if any(word in file.name.lower() for word in ('license', 'copying', 'notice')):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    target = licenses / distribution.metadata['Name'] / Path(str(file))
                    # 不接受包含父目录跳转的安装记录。
                    if '..' not in Path(str(file)).parts:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, target)
    datas = [(str(staged_model), 'models'), (str(ROOT / 'resources/default_config.json'), 'resources'),
             (str(ROOT / 'THIRD_PARTY_NOTICES.md'), '.'), (str(licenses), 'licenses')]
    mac = sys.platform == 'darwin'
    hidden = ['ultralytics.nn.tasks', 'ultralytics.nn.modules', 'PIL._tkinter_finder']
    hidden += (['pynput.keyboard._darwin', 'pynput.mouse._darwin', 'Quartz', 'AppKit'] if mac
               else ['pynput.keyboard._win32', 'pynput.mouse._win32'])
    spec = f'''
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
assets = {datas!r} + collect_data_files('ultralytics') + copy_metadata('ultralytics')
a = Analysis([{str(ROOT / 'desktop_app.py')!r}], pathex=[{str(ROOT)!r}],
    binaries=[], datas=assets, hiddenimports={hidden!r},
    excludes=['IPython', 'jupyter', 'pytest', 'tensorboard', 'tensorflow'], noarchive=False)
pyz = PYZ(a.pure)
'''
    if mac:
        spec += '''
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='WoWFishing',
    console=False, debug=False, strip=False, upx=False, argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='WoWFishing')
app = BUNDLE(coll, name='WoWFishing.app', bundle_identifier='fun.amast.wowfishing',
    info_plist={'CFBundleShortVersionString': ''' + repr(VERSION) + ''',
                'NSHighResolutionCapable': True,
                'NSAppleEventsUsageDescription': '用于用户请求的游戏窗口操作。',
                'NSScreenCaptureUsageDescription': '识别魔兽世界窗口中的鱼漂。'})
'''
    else:
        spec += f'''
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='WoWFishing',
    console=False, debug=False, strip=False, upx=False,
    manifest={str(ROOT / 'resources/windows.manifest')!r})
'''
    spec_path = stage / 'WoWFishing.spec'
    spec_path.write_text(spec, encoding='utf-8')
    destination = ROOT / 'dist' / label
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                    '--distpath', str(destination), '--workpath', str(stage / 'work'), str(spec_path)], check=True, cwd=ROOT)
    app = destination / ('WoWFishing.app' if mac else 'WoWFishing.exe')
    if mac:
        # 仅清理刚在本机生成的包的扩展属性，随后重新签名；不修改下载应用或源文件。
        subprocess.run(['/usr/bin/xattr', '-cr', str(app)], check=True)
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', '--timestamp=none', str(app)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    executable = app / 'Contents/MacOS/WoWFishing' if mac else app
    # macOS 单目录构建还生成一个中间目录，不将它作为发布内容。
    with tempfile.TemporaryDirectory(prefix='wow-fishing-smoke-') as temporary:
        report = Path(temporary) / 'result.json'
        environment = dict(os.environ, WOW_FISHING_DATA_DIR=str(Path(temporary) / 'data'))
        subprocess.run([str(executable), '--self-test', '--result-file', str(report)],
                       check=True, timeout=240, cwd=temporary, env=environment)
        result = json.loads(report.read_text(encoding='utf-8'))
        if not result['ok'] or result['model']['sha256'] != fingerprint:
            raise RuntimeError('打包自检失败：模型指纹不匹配。')
    release = ROOT / 'release' / label
    release.mkdir(parents=True, exist_ok=True)
    if mac:
        artifact = release / f'WoWFishing-{VERSION}-{label}.zip'
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(artifact)], check=True)
    else:
        artifact = release / f'WoWFishing-{VERSION}-{label}.exe'
        shutil.copyfile(app, artifact)
    shutil.copyfile(ROOT / 'THIRD_PARTY_NOTICES.md', release / 'THIRD_PARTY_NOTICES.md')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (release / 'SHA256SUMS.txt').write_text(f'{digest}  {artifact.name}\n', encoding='utf-8')
    (release / 'build-info.json').write_text(json.dumps({
        'version': VERSION, 'platform': label, 'python': platform.python_version(),
        'model_sha256': fingerprint, 'artifact_sha256': digest,
        'self_test': 'passed', 'game_test': 'not_performed',
        'dependencies': {name: importlib.metadata.version(name) for name in
                         ('torch', 'torchvision', 'ultralytics', 'numpy', 'opencv-python', 'pyinstaller')},
    }, indent=2), encoding='utf-8')
    print(f'构建与离线自检完成: {artifact}')
    return artifact


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, help='构建时嵌入的本地 .pt 文件，公开仓库不附带权重')
    args = parser.parse_args()
    build(args.model)
