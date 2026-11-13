"""从明确的文件白名单导出公开源码；从不复制 .git、权重或数据集。"""

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'app_paths.py', 'desktop_app.py',
    'fishing_bot.py', 'config.py', 'requirements.txt', 'requirements-build.txt',
    'resources/default_config.json', 'resources/windows.manifest',
    'scripts/build_app.py', 'scripts/export_public.py',
    'scripts/build_windows.bat', 'scripts/build_macos.command',
    'docs/USER_GUIDE.md', 'docs/WINDOWS_HANDOFF.md',
)
# 仅代码文件；即使有人把 .pt 改名放进其他目录，也不会扩大导出范围。
MODULES = (
    'utils/dataset_collector.py', 'utils/enhanced_detector.py', 'utils/image_io.py',
    'utils/logger.py', 'utils/platform_setup.py', 'utils/window_utils.py',
    'utils/windows_window.py', 'utils/yolo_detector.py',
    'tests/test_core.py', '.github/workflows/test.yml',
)
PUBLIC_IGNORE = '*.pt\n*.onnx\n*.zip\n*.tar.gz\nmodels/\ndataset*/\noutput/\nlogs/\nbuild/\ndist/\nrelease/\n.venv/\n__pycache__/\n*.pyc\n.DS_Store\nconfig.json\n'


def export(destination):
    """目标必须不存在或为空，防止遗留权重混入公开提交。"""
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('公开导出目标必须为空目录；不会清空或覆盖已有仓库。')
    sources = []
    for relative in FILES + MODULES:
        source = ROOT / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError(f'缺少公开源文件或检测到符号链接: {relative}')
        sources.append((source, relative))
    destination.mkdir(parents=True, exist_ok=True)
    for source, relative in sources:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (destination / '.gitignore').write_text(PUBLIC_IGNORE, encoding='utf-8')
    print(f'已导出 {len(sources) + 1} 个公开文件，无权重、数据集或提交历史: {destination}')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    export(parser.parse_args().output)
