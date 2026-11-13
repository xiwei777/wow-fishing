#!/usr/bin/env python3
"""
魔兽世界自动钓鱼机器人（增强版）
整合 YOLO + 帧差分检测，支持配置文件和防检测机制

使用方法：
1. 在游戏中站在水边，按建议设置环境
2. 运行脚本: python fishing_bot.py
3. 首次运行创建用户配置；按 C 打开配置文件，保存后重启
4. 按设置的开始键（默认 F11）开始/停止钓鱼
5. 按 ESC 退出程序

游戏内宏示例（放在动作条上）：
#showtooltip 钓鱼
/equip 塞瑟的石墨鱼杆
/use 锐利的鱼钩
/use 16
/cast 钓鱼
/use 雕文卷轴盒
"""

import sys
import os
import time
import threading
import random
import signal
import subprocess
from datetime import datetime
from app_paths import ensure_user_config, output_path
from utils.platform_setup import setup_dpi_awareness

setup_dpi_awareness()

# 添加utils到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 带时间戳的打印函数
def ts_print(*args, **kwargs):
    """带时间戳的打印"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}]", *args, **kwargs)

import cv2
import numpy as np
import pyautogui
from pynput import keyboard
from pynput.mouse import Controller, Button

# 导入配置和检测器
from config import get_config, FishingConfig
from utils.enhanced_detector import EnhancedBiteDetector
from utils.window_utils import GameWindow, WindowUnavailable
from utils.dataset_collector import DatasetCollector
from utils.yolo_detector import YOLOFloatDetector
from utils.logger import FishingLogger


class FishingBot:
    """增强版钓鱼机器人主类"""
    
    def __init__(self, config_path=None, model_path=None):
        # 加载配置
        self.config = get_config(config_path or ensure_user_config())
        
        # 初始化日志器
        self.logger = FishingLogger(self.config)
        
        # 初始化游戏窗口
        print("\n🔍 初始化游戏窗口...")
        self.logger.info("初始化游戏窗口...")
        self.game_window = GameWindow(self.config)
        self.game_window.find()
        
        # 初始化检测器
        # 1. YOLO 检测器（鱼漂位置检测）
        self.yolo_detector = YOLOFloatDetector(model_path)
        if not self.yolo_detector.is_available():
            raise RuntimeError("模型加载失败，请检查安装包或所指定的权重。")
        
        # 2. 咬钩检测器（像素差异检测，无轮廓检测）
        self.bite_detector = EnhancedBiteDetector(
            pixel_threshold=self.config.get("detection.bite_threshold"),
            consecutive_frames=self.config.get("detection.consecutive_frames"),
            trigger_ratio=self.config.get("detection.bite_trigger_ratio"),
            min_ratio=self.config.get("detection.bite_min_ratio"),
            output_dir=(output_path(self.config.get("general.screenshot_dir")) / "roi"
                        if self.config.get("general.debug_mode") else None)
        )
        
        # 数据集收集器（用于保存训练数据）
        self.dataset_collector = (DatasetCollector(
            base_dir=output_path(self.config.get("general.screenshot_dir")),
            model_info=self.yolo_detector.model_info,
            config=self.config.get("detection"),
        ) if self.config.get("general.save_screenshots") else None)
        
        # 鼠标控制器
        self.mouse = Controller()
        
        # 状态
        self.running = True
        self.fishing = False
        self.stop_event = threading.Event()
        self.auto_close_event = threading.Event()
        self.worker = None
        self.bait_worker = None
        self.listener = None
        self.last_toggle_time = 0.0
        
        # 屏幕尺寸
        self.screen_width, self.screen_height = pyautogui.size()
        
        # 统计
        self.stats = {
            'casts': 0,
            'catches': 0,
            'misses': 0,
            'start_time': None,
            'session_catches': 0
        }
        
        # 防检测计数
        self.anti_detection_stats = {
            'jumps': 0,
            'delays': 0
        }
        
        # 安全设置
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
    
    def print_banner(self):
        """打印启动横幅"""
        print("\n" + "="*70)
        print("🎣  魔兽世界自动钓鱼机器人（增强版）")
        print("="*70)
        
        # 输出屏幕和窗口信息
        print(f"📺 屏幕大小: {self.screen_width}x{self.screen_height}")
        if self.game_window.enabled:
            rect = self.game_window.get_window_rect()
            if rect:
                print(f"🪟 窗口位置: ({rect[0]}, {rect[1]})")
                print(f"🪟 窗口大小: {rect[2]}x{rect[3]}")
                print(f"🔍 缩放因子: {self.game_window.scale}x")
        print(f"🎮 控制按键:")
        print(f"   [{self.config.get('keys.toggle_fishing').upper()}] - 开始/停止钓鱼")
        print(f"   [{self.config.get('keys.cast').upper()}] - 甩竿按键")
        macro_key = self.config.get('keys.macro')
        if macro_key:
            print(f"   [{macro_key.upper()}] - 一键宏按键")
        print(f"   [C] - 进入配置界面")
        print(f"   [ESC] - 退出程序")
        print("-"*70)
        print(f"🔍 检测模式: YOLO + 像素差异咬钩检测")
        print(f"🛡️  防检测: {'开启' if self.config.get('anti_detection.enabled') else '关闭'}")
        
        # 打印上鱼饵设置
        bait_key = self.config.get('keys.bait')
        bait_interval = self.config.get('bait.interval_minutes')
        bait_enabled = self.config.get('bait.enabled')
        print(f"🎣 上鱼饵: {'开启' if bait_enabled else '关闭'} | 按键: {bait_key} | 间隔: {bait_interval}分钟")
        
        # 打印其他主要设置
        print(f"⚙️  主要设置:")
        yolo_status = "✅ 可用" if self.yolo_detector.is_available() else "❌ 不可用"
        print(f"   YOLO 检测: {yolo_status}")
        print(f"   YOLO 置信度: {self.config.get('detection.yolo_conf')}")
        print(f"   像素变化阈值: {self.config.get('detection.bite_threshold')}")
        print(f"   最大等待时间: {self.config.get('detection.max_wait_time')}秒")
        print(f"   鱼漂大小范围: 20-60像素")
        print("="*70)
        print()
        
        # 环境建议
        self.print_environment_tips()
    
    def print_environment_tips(self):
        """打印环境设置建议"""
        print("📋 游戏内设置建议（重要！）:")
        ts_print("   1. 按 ALT+Z 屏蔽所有UI和插件元素")
        ts_print("   2. 在人烟稀少的地方钓鱼")
        ts_print("   3. 视角拉到最近，避免身体挡住鱼漂")
        ts_print("   4. 视野内避免水草、瀑布等动态元素")
        ts_print("   5. 背对太阳，避免波光粼粼影响识别")
        ts_print("   6. 建议开启游戏声音，可以听到鱼上钩的水声")
        print()
    
    def start(self):
        """启动键盘监听"""
        self.print_banner()
        
        # 启动自动关闭线程（如果启用）
        if self.config.get("anti_detection.auto_close"):
            self.start_auto_close_timer()
        
        # 设置键盘监听
        try:
            with keyboard.Listener(on_press=self.on_key_press) as listener:
                self.listener = listener
                if not self.running:
                    listener.stop()
                listener.join()
        except Exception as e:
            print(f"键盘监听错误: {e}")
    
    def on_key_press(self, key):
        """键盘事件处理"""
        try:
            # 处理字符键
            if hasattr(key, 'char') and key.char:
                char = key.char.lower()
                if char == 'c':
                    self.open_config()
                    return True
            
            # 处理功能键
            toggle_key = self.config.get("keys.toggle_fishing")
            
            # 检查是否是开始/停止键
            if self._match_key(key, toggle_key):
                now = time.monotonic()
                if now - self.last_toggle_time > 0.4:
                    self.last_toggle_time = now
                    self.toggle_fishing()
            elif key == keyboard.Key.esc:
                print("\n👋 退出程序...")
                self.stop()
                return False
                
        except Exception as e:
            print(f"键盘处理错误: {e}")
        return True
    
    def _match_key(self, key, target):
        """匹配按键"""
        if target.startswith('f') and target[1:].isdigit():
            # F1-F12
            f_num = int(target[1:])
            return key == getattr(keyboard.Key, f'f{f_num}', None)
        elif hasattr(key, 'char') and key.char:
            return key.char.lower() == target.lower()
        return False
    
    def open_config(self):
        """打开配置界面"""
        if self.fishing:
            print("\n⚠️ 请先停止钓鱼再进入配置")
            return
        path = str(self.config.config_path)
        if sys.platform == 'win32':
            os.startfile(path)
        else:
            subprocess.Popen(['open', path])
        ts_print('⚙️ 配置文件已打开，保存后请重启程序使修改生效。')
    
    def toggle_fishing(self):
        """切换钓鱼状态"""
        if self.fishing:
            print("\n⏹️  停止钓鱼")
            self.fishing = False
            self.stop_event.set()
        else:
            if not self.running:
                return
            if ((self.worker and self.worker.is_alive()) or
                    (self.bait_worker and self.bait_worker.is_alive())):
                ts_print('⚠️ 上一次操作正在结束，请稍后再按 F11。')
                return
            if not self.game_window.find():
                return
            self.game_window.require_foreground()
            print("\n▶️  开始钓鱼...")
            ts_print("   提示: 脚本运行后观察1分钟，能正常钓就可以离开了")
            self.fishing = True
            self.stop_event.clear()
            self.stats['start_time'] = time.time()
            
            # 在新线程中运行钓鱼循环
            self.worker = threading.Thread(target=self.fishing_loop, daemon=True)
            self.worker.start()
            
            # 启动定时上鱼饵线程
            if self.config.get('bait.enabled'):
                self.bait_worker = threading.Thread(target=self.bait_timer_loop, daemon=True)
                self.bait_worker.start()
    
    def start_auto_close_timer(self):
        """启动自动关闭计时器"""
        minutes = self.config.get("anti_detection.close_after_minutes")
        print(f"⏰ 自动关闭已设置: {minutes} 分钟后关闭")
        
        def auto_close_worker():
            if not self.auto_close_event.wait(minutes * 60):
                print(f"\n⏰ 自动关闭时间到（{minutes}分钟）")
                self.stop()
                # 尝试关闭游戏（可选）
                # pyautogui.keyDown('alt')
                # pyautogui.keyDown('f4')
                # pyautogui.keyUp('f4')
                # pyautogui.keyUp('alt')
        
        threading.Thread(target=auto_close_worker, daemon=True).start()
    
    def stop(self):
        """停止机器人"""
        self.running = False
        self.fishing = False
        self.stop_event.set()
        self.auto_close_event.set()
        if self.listener is not None:
            self.listener.stop()
        self.print_stats()

    def pause(self):
        """停止本轮及上饵线程，仍保留快捷键监听。"""
        self.fishing = False
        self.stop_event.set()

    def _check_input(self):
        """每次发送输入前确认未停止且游戏仍位于前台。"""
        if self.stop_event.is_set() or not self.running or not self.fishing:
            raise WindowUnavailable('操作已停止。')
        self.game_window.require_foreground()

    def _press(self, key):
        self._check_input()
        pyautogui.press(key)
    
    def bait_timer_loop(self):
        """定时上鱼饵循环，每10分钟按一次按键"""
        bait_interval = self.config.get('bait.interval_minutes')
        bait_key = self.config.get('keys.bait')
        
        # 首次等待10分钟
        ts_print(f"   🎣 上鱼饵定时器已启动，{bait_interval}分钟后首次上饵...")
        
        while self.fishing and not self.stop_event.is_set():
            # 等待指定分钟
            if self.stop_event.wait(bait_interval * 60):
                return
            
            # 按下鱼饵键
            if self.fishing and not self.stop_event.is_set():
                ts_print(f"   🎣 自动上鱼饵...")
                self.logger.log_fishing_event("bait", key=bait_key)
                try:
                    self._press(bait_key)
                except (WindowUnavailable, pyautogui.FailSafeException) as error:
                    ts_print(f'⚠️ {error}')
                    self.pause()
                    return
    
    def fishing_loop(self):
        """钓鱼主循环"""
        # 执行一键宏（如果设置）
        macro_key = self.config.get("keys.macro")
        if macro_key:
            print(f"   执行一键宏 [{macro_key.upper()}]...")
            try:
                self._press(macro_key)
            except (WindowUnavailable, pyautogui.FailSafeException) as error:
                ts_print(f'⚠️ {error}')
                self.pause()
                return
            time.sleep(2)
        
        while self.fishing and not self.stop_event.is_set():
            try:
                success = self.do_one_cast()
                if not success:
                    ts_print("   本次未成功，继续...")
                    time.sleep(1)
                
                # 防检测：随机跳跃
                self.do_anti_detection()
                
            except (WindowUnavailable, pyautogui.FailSafeException) as e:
                ts_print(f'⚠️ {e}')
                self.pause()
            except Exception as e:
                print(f"   错误: {e}")
                self.pause()
        
        print("\n✅ 钓鱼循环已停止")
        self.print_stats()
    
    def do_one_cast(self):
        """执行一次完整的钓鱼流程"""
        print("\n" + "-"*60)
        self.stats['casts'] += 1
        cast_num = self.stats['casts']
        
        # 防检测：随机延迟
        if self.config.get("anti_detection.random_delay"):
            delay = random.uniform(
                self.config.get("anti_detection.delay_min"),
                self.config.get("anti_detection.delay_max")
            )
            time.sleep(delay)
        
        # 1. 甩竿
        cast_key = self.config.get("keys.cast")
        ts_print(f"[{cast_num}] 🎣 甩竿...")
        self.logger.log_fishing_event("cast", cast_num=cast_num)
        self._press(cast_key)
        time.sleep(2)  # 等待2秒让鱼漂从透明变成实心
        
        # 3. 寻找鱼漂
        ts_print("   🔍 寻找鱼漂...")
        float_pos = self.find_float()
        
        if float_pos is None:
            ts_print("   ❌ 未找到鱼漂")
            self.logger.log_fishing_event("miss")
            self.stats['misses'] += 1
            return False
        
        x, y, w, h, conf, method = float_pos
        ts_print(f"   ✅ 找到鱼漂: 截图内位置({x}, {y}), 大小{w}x{h}, 置信度{conf:.2f} [YOLO]")
        self.logger.log_fishing_event("float_found", method='yolo', conf=conf)
        
        # 输出坐标转换信息
        if self.game_window.enabled:
            rect = self.game_window.get_window_rect()
            if rect:
                center_x, center_y = x + w//2, y + h//2
                screen_x, screen_y = self.game_window.window_to_screen(center_x, center_y)
                ts_print(f"   📐 坐标转换:")
                ts_print(f"      窗口偏移: ({rect[0]}, {rect[1]})")
                ts_print(f"      鱼漂中心(截图内): ({center_x}, {center_y})")
                ts_print(f"      屏幕坐标(鼠标): ({screen_x}, {screen_y})")
        
        # 4. 将鼠标移开，避免干扰检测
        if self.config.get("anti_detection.mouse_flee"):
            self._check_input()
            # 鼠标避让 - 移到屏幕右下角（远离游戏窗口）
            flee_x = self.screen_width - 50
            flee_y = self.screen_height - 50
            pyautogui.moveTo(flee_x, flee_y, duration=0.1)
            ts_print(f"   🖱️ 鼠标避让到屏幕右下角: ({flee_x:.0f}, {flee_y:.0f})")
        
        # 5. 等待3秒后开始检测咬钩（给鱼漂充分落水时间）
        ts_print("   ⏱️  等待3秒后开始检测鱼漂晃动...")
        time.sleep(3)
        
        # 6. 等待咬钩
        ts_print("   👀 等待鱼上钩...")
        caught = self.wait_for_bite(float_pos)
        
        if caught:
            # 7. 检测到咬钩后等待0.5-1.0秒再点击
            delay = random.uniform(0.5, 1.0)
            ts_print(f"   🐟 鱼上钩了! 等待{delay:.1f}秒后收杆...")
            self.logger.log_fishing_event("bite")
            time.sleep(delay)
            
            # 推理时已保存对应原图和标注，不对新的截图复用旧预测框。
            self.click_float(x + w//2, y + h//2)
            self.stats['catches'] += 1
            self.stats['session_catches'] += 1
            duration = 0  # 可以统计实际耗时
            self.logger.log_fishing_event("catch", duration=delay)
            time.sleep(self.config.get("general.loop_delay"))
            
            # 销毁劣质鱼（可选）
            destroy_key = self.config.get("keys.destroy_fish")
            if destroy_key:
                self._press(destroy_key)
                time.sleep(0.5)
            
            return True
        else:
            ts_print("   ⏱️  等待超时，重新甩竿")
            self.stats['misses'] += 1
            return False
    
    def find_float(self):
        """
        寻找鱼漂位置 - 使用 YOLO 检测
        """
        timeout = self.config.get("detection.search_timeout")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.stop_event.is_set():
                return None
            
            screenshot = self.take_screenshot()
            
            # 使用 YOLO 检测鱼漂
            if self.yolo_detector.is_available():
                result = self.yolo_detector.detect(
                    screenshot,
                    conf_threshold=self.config.get("detection.yolo_conf")
                )
                if self.dataset_collector:
                    try:
                        self.dataset_collector.save_sample(
                            screenshot, result, self.game_window.last_capture_rect,
                            self.stats['casts'])
                    except (OSError, ValueError) as error:
                        self.logger.warning(f'保存推理记录失败: {error}')
                if result:
                    x, y, w, h, conf = result
                    full_result = (x, y, w, h, conf, 'yolo')
                    ts_print(f"   🎯 YOLO 检测到鱼漂: ({x}, {y}), 置信度{conf:.2f}")
                    return full_result
            
            time.sleep(0.2)
        
        return None
    
    def wait_for_bite(self, float_pos, timeout=None):
        """
        等待鱼上钩
        当 bite_detector.detect() 返回 True 时认为鱼上钩
        """
        if timeout is None:
            timeout = self.config.get("detection.max_wait_time")
        
        self.bite_detector.reset()
        expected_rect = self.game_window.last_capture_rect
        start_time = time.time()
        last_debug_time = 0
        
        while time.time() - start_time < timeout:
            if self.stop_event.is_set():
                return False
            
            screenshot = self.take_screenshot()
            if self.game_window.last_capture_rect != expected_rect:
                raise WindowUnavailable('游戏窗口移动或缩放，请按 F11 重新识别。')
            
            # 检测是否咬钩
            is_bite = self.bite_detector.detect(
                screenshot, 
                float_pos,
                self.screen_width,
                self.screen_height
            )
            
            # 获取调试信息
            metrics = self.bite_detector.get_debug_info()
            trigger_count = metrics.get('trigger_count') if metrics else 0
            
            if is_bite:
                ts_print(f"      ✅ 检测到咬钩！(触发数:{trigger_count})")
                return True
            
            # 调试输出
            if time.time() - last_debug_time > 3:
                ts_print(f"      监测中... 触发数: {trigger_count}")
                last_debug_time = time.time()
            
            time.sleep(0.05)  # 20 FPS
        
        return False
    
    def click_float(self, x, y):
        """点击鱼漂位置（支持窗口坐标转换）"""
        self._check_input()
        ts_print(f"      [CLICK_FLOAT] 被调用，参数: ({x}, {y})")
        
        # 将窗口内坐标转换为屏幕坐标
        screen_x, screen_y = self.game_window.window_to_screen(x, y)
        
        # 保存当前鼠标位置
        original_pos = self.mouse.position
        
        # 点击检测框中心；平台坐标转换不依赖历史固定偏移。
        offset_x = 0
        offset_y = 0
        
        target_x = screen_x + offset_x
        target_y = screen_y + offset_y
        
        ts_print(f"      🖱️ 点击位置:")
        ts_print(f"         截图内: ({x}, {y})")
        ts_print(f"         屏幕坐标: ({screen_x}, {screen_y})")
        ts_print(f"         加随机偏移: ({target_x}, {target_y})")
        ts_print(f"         当前鼠标位置: {original_pos}")
        
        # 移动鼠标并点击
        import pyautogui
        pyautogui.moveTo(target_x, target_y, duration=0.1)
        time.sleep(0.2)
        
        # 右键点击（魔兽钓鱼通常是右键收杆）
        self._check_input()
        self.game_window.window_to_screen(x, y)
        pyautogui.rightClick()
        
        time.sleep(0.2)
        
        # 恢复鼠标位置
        if not self.stop_event.is_set() and self.game_window.is_foreground():
            pyautogui.moveTo(original_pos[0], original_pos[1], duration=0.1)
    
    def do_anti_detection(self):
        """执行防检测措施"""
        if not self.config.get("anti_detection.enabled"):
            return
        
        # 随机跳跃
        if (self.config.get("anti_detection.random_jump") and 
            random.randint(1, 100) <= self.config.get("anti_detection.jump_chance")):
            ts_print("   🦘 随机跳跃（防检测）...")
            self._press('space')
            self.anti_detection_stats['jumps'] += 1
            time.sleep(0.5)
    
    def take_screenshot(self):
        """截取屏幕/游戏窗口"""
        return self.game_window.screenshot()
    
    def print_stats(self):
        """打印统计信息"""
        print("\n" + "="*60)
        print("📊 钓鱼统计")
        print("="*60)
        print(f"   甩竿次数: {self.stats['casts']}")
        print(f"   成功钓起: {self.stats['catches']}")
        print(f"   失败次数: {self.stats['misses']}")
        
        if self.stats['casts'] > 0:
            success_rate = self.stats['catches'] / self.stats['casts'] * 100
            print(f"   成功率: {success_rate:.1f}%")
        
        if self.stats['start_time']:
            duration = time.time() - self.stats['start_time']
            print(f"   运行时间: {duration/60:.1f} 分钟")
        
        if self.anti_detection_stats['jumps'] > 0:
            print(f"   随机跳跃: {self.anti_detection_stats['jumps']} 次")
        
        print("="*60)


def main():
    """命令行调试入口；最终用户双击 desktop_app 打包程序。"""
    import argparse
    parser = argparse.ArgumentParser(description='魔兽世界自动钓鱼')
    parser.add_argument('--model', help='指定本地 .pt 权重文件')
    parser.add_argument('--config', help='指定完整配置文件')
    args = parser.parse_args()
    bot = FishingBot(config_path=args.config, model_path=args.model)
    try:
        bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        bot.stop()


if __name__ == "__main__":
    main()
