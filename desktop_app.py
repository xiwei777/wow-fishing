"""双击启动入口：桌面状态窗口、日志、配置和离线打包自检。"""

import argparse
import json
import multiprocessing
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import traceback
from app_paths import VERSION, data_dir, ensure_user_config
from utils.platform_setup import setup_dpi_awareness


def open_path(path):
    """使用系统默认应用打开文件或目录。"""
    if sys.platform == 'win32':
        os.startfile(str(path))
    else:
        subprocess.Popen(['open', str(path)])


def self_test(model_path=None, result_file=None):
    """只加载内置模型并推理合成图，不截图、不监听或发送键鼠事件。"""
    import numpy as np
    from config import FishingConfig
    from utils.yolo_detector import YOLOFloatDetector
    from utils.dataset_collector import DatasetCollector
    config = FishingConfig(ensure_user_config())
    detector = YOLOFloatDetector(model_path)
    if not detector.is_available():
        raise RuntimeError('模型自检失败')
    sample = np.zeros((480, 640, 3), dtype=np.uint8)
    # 直接调用 predict 让错误传播，而不是被运行时检测的容错分支吞掉。
    results = detector.model.predict(sample, device='cpu', verbose=False)
    if len(results) != 1:
        raise RuntimeError('模型没有返回预期推理结果')
    collector = DatasetCollector(data_dir() / 'self-test', detector.model_info, config.get('detection'))
    collector.save_sample(sample, None)
    report = {'ok': True, 'version': VERSION, 'platform': sys.platform,
              'model': detector.model_info, 'data_dir': str(data_dir())}
    if result_file:
        Path(result_file).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


class QueueWriter:
    """后台日志只写队列，所有 Tk 操作在主线程执行。"""
    def __init__(self, messages, log_file):
        self.messages, self.log_file = messages, log_file
        self.encoding = 'utf-8'
        self.lock = threading.Lock()

    def write(self, text):
        if text:
            with self.lock:
                self.log_file.write(text)
                self.log_file.flush()
            try:
                self.messages.put_nowait(text)
            except queue.Full:
                pass
        return len(text)

    def flush(self):
        with self.lock:
            self.log_file.flush()

    def isatty(self):
        return False


class DesktopApp:
    def __init__(self, root, config_path=None, model_path=None):
        import tkinter as tk
        from tkinter import ttk
        from tkinter.scrolledtext import ScrolledText
        self.root, self.bot = root, None
        self.closed = threading.Event()
        self.messages = queue.Queue(maxsize=2000)
        self.config_path = config_path or ensure_user_config()
        self.model_path = model_path
        root.title(f'魔兽世界钓鱼 · {VERSION}')
        root.geometry('780x540')
        root.minsize(600, 400)
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='魔兽世界钓鱼', font=('', 20)).pack(anchor='w')
        self.status = tk.StringVar(value='正在加载模型…')
        ttk.Label(frame, textvariable=self.status).pack(anchor='w', pady=(8, 4))
        ttk.Label(frame, text='切回游戏后按 F11 开始/暂停，ESC 退出。游戏失去焦点时自动暂停。').pack(anchor='w')
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=12)
        ttk.Button(row, text='暂停钓鱼', command=self.pause).pack(side='left', padx=(0, 8))
        ttk.Button(row, text='编辑配置', command=self.edit_config).pack(side='left', padx=(0, 8))
        ttk.Button(row, text='打开保存目录', command=lambda: open_path(data_dir())).pack(side='left')
        self.log = ScrolledText(frame, height=20, state='disabled', font=('TkFixedFont', 11))
        self.log.pack(fill='both', expand=True)
        ttk.Label(frame, text=f'本地数据：{data_dir()}').pack(anchor='w', pady=(8, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        log_dir = data_dir() / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = (log_dir / 'desktop.log').open('a', encoding='utf-8')
        self.original_streams = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = QueueWriter(self.messages, self.log_file)
        self.worker = threading.Thread(target=self.load_and_run, daemon=True)
        self.worker.start()
        root.after(100, self.poll)

    def load_and_run(self):
        try:
            from fishing_bot import FishingBot
            bot = FishingBot(self.config_path, self.model_path)
            self.bot = bot
            if self.closed.is_set():
                bot.stop()
                return
            bot.start()
        except Exception:
            print('❌ 启动失败，详细信息如下：')
            traceback.print_exc()

    def poll(self):
        if self.closed.is_set():
            return
        chunks = []
        for _ in range(200):
            try:
                chunks.append(self.messages.get_nowait())
            except queue.Empty:
                break
        if chunks:
            self.log.configure(state='normal')
            self.log.insert('end', ''.join(chunks))
            if int(self.log.index('end-1c').split('.')[0]) > 1500:
                self.log.delete('1.0', '500.0')
            self.log.see('end')
            self.log.configure(state='disabled')
        if self.bot:
            if not self.bot.running:
                self.close()
                return
            self.status.set('正在钓鱼' if self.bot.fishing else '已就绪：切回游戏，按 F11 开始')
        elif not self.worker.is_alive():
            self.status.set('启动失败，请查看下方日志')
        self.root.after(100, self.poll)

    def pause(self):
        if self.bot:
            self.bot.pause()

    def edit_config(self):
        self.pause()
        open_path(self.config_path)
        print('⚙️ 保存配置后，请关闭并重新打开程序。')

    def close(self):
        self.closed.set()
        if self.bot:
            self.bot.stop()
        self.root.destroy()


def main():
    multiprocessing.freeze_support()
    setup_dpi_awareness()
    parser = argparse.ArgumentParser(description='魔兽世界钓鱼桌面程序')
    parser.add_argument('--model', help='源码开发者指定本地权重；发布版默认使用内置模型')
    parser.add_argument('--config', help='指定配置文件')
    parser.add_argument('--self-test', action='store_true', help='离线自检，不操作键鼠')
    parser.add_argument('--ui-smoke-test', action='store_true', help='仅验证桌面界面，不初始化游戏控制')
    parser.add_argument('--result-file', help='自检结果 JSON 输出路径')
    args = parser.parse_args()
    if args.self_test:
        try:
            report = self_test(args.model, args.result_file)
            if sys.stdout:
                print(json.dumps(report, ensure_ascii=False))
            return 0
        except Exception as error:
            if args.result_file:
                Path(args.result_file).write_text(json.dumps({'ok': False, 'error': str(error)}), encoding='utf-8')
            if sys.stderr:
                traceback.print_exc()
            return 1
    import tkinter as tk
    root = tk.Tk()
    if args.ui_smoke_test:
        DesktopApp.load_and_run = lambda self: None
    DesktopApp(root, args.config, args.model)
    if args.ui_smoke_test:
        root.after(1200, root.destroy)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
