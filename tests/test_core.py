"""无游戏、无键鼠操作的跨平台回归测试。"""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
import app_paths
from config import FishingConfig
from scripts import export_public
from utils.dataset_collector import DatasetCollector
from utils.enhanced_detector import EnhancedBiteDetector


class ConfigTests(unittest.TestCase):
    def test_comments_preserve_strings(self):
        parser = FishingConfig.__new__(FishingConfig)
        value = json.loads(parser._remove_comments(r'''{
          // 中文注释
          "url": "https://example.com/a/*literal*/", /* block */
          "path": "C:\\Users\\测试\\model.pt",
          "quote": "say \"//hello\""
        }'''))
        self.assertEqual(value['url'], 'https://example.com/a/*literal*/')
        self.assertEqual(value['path'], r'C:\Users\测试\model.pt')
        self.assertEqual(value['quote'], 'say "//hello"')

    def test_default_config_is_complete_and_user_config_preserved(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, WOW_FISHING_DATA_DIR=temporary):
            path = app_paths.ensure_user_config()
            config = FishingConfig(path)
            self.assertTrue(config.get('general.save_screenshots'))
            config.set('keys.cast', '7')
            config.save()
            self.assertEqual(FishingConfig(app_paths.ensure_user_config()).get('keys.cast'), '7')
            self.assertEqual(app_paths.output_path('output'), Path(temporary).resolve() / 'output')

    def test_resources_work_in_frozen_app_and_outside_cwd(self):
        with patch.object(app_paths.sys, '_MEIPASS', '/bundle', create=True):
            self.assertEqual(app_paths.resource_path('models/best.pt'), Path('/bundle/models/best.pt'))

    def test_missing_required_config_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config.json'
            path.write_text('{}')
            with self.assertRaises(KeyError):
                FishingConfig(path)


class RecordingTests(unittest.TestCase):
    def test_image_labels_confidence_and_model_match(self):
        with tempfile.TemporaryDirectory(prefix='中文目录-') as temporary:
            model = {'name': 'best.pt', 'sha256': 'abc123'}
            recorder = DatasetCollector(temporary, model)
            screenshot = np.zeros((100, 200, 3), dtype=np.uint8)
            screenshot[20:40, 30:70] = 200
            name = recorder.save_sample(screenshot, (30, 20, 40, 20, 0.91), (10, 20, 200, 100), 3)
            original = cv2.imdecode(np.frombuffer((recorder.images_dir / f'{name}.png').read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            np.testing.assert_array_equal(original, screenshot)
            label = (recorder.labels_dir / f'{name}.txt').read_text().split()
            self.assertEqual(label, ['0', '0.250000', '0.300000', '0.200000', '0.200000'])
            metadata = json.loads((recorder.labels_dir / f'{name}.json').read_text())
            self.assertEqual(metadata['predictions'][0]['confidence'], 0.91)
            self.assertEqual(metadata['model'], model)
            self.assertEqual(metadata['cast_number'], 3)
            self.assertTrue(metadata['requires_review'])
            self.assertEqual(list(Path(temporary).rglob('*.pt')), [])

    def test_no_detection_saved_as_empty_prediction_and_sessions_unique(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = DatasetCollector(temporary), DatasetCollector(temporary)
            self.assertNotEqual(first.base_dir, second.base_dir)
            name = first.save_sample(np.zeros((20, 20, 3), np.uint8), None)
            self.assertEqual((first.labels_dir / f'{name}.txt').read_text(), '')
            metadata = json.loads((first.labels_dir / f'{name}.json').read_text())
            self.assertEqual(metadata['predictions'], [])

    def test_out_of_bounds_label_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            recorder = DatasetCollector(temporary)
            with self.assertRaises(ValueError):
                recorder.save_sample(np.zeros((20, 20, 3), np.uint8), (19, 19, 5, 5, .5))


class BiteTests(unittest.TestCase):
    def test_shape_change_resets_baseline_and_consecutive_frames(self):
        detector = EnhancedBiteDetector(consecutive_frames=2)
        pos = (10, 10, 10, 10)
        black = np.zeros((50, 50, 3), np.uint8)
        white = np.full_like(black, 255)
        self.assertFalse(detector.detect(black, pos))
        self.assertFalse(detector.detect(white, pos))
        self.assertTrue(detector.detect(black, pos))
        self.assertFalse(detector.detect(black[:20, :20], pos))
        detector.reset()
        self.assertEqual(detector.get_debug_info(), {})


class PublicExportTests(unittest.TestCase):
    def test_no_weights_dataset_history_or_private_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = export_public.export(Path(temporary) / 'public')
            actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
            expected = set(export_public.FILES + export_public.MODULES) | {'.gitignore'}
            self.assertEqual(actual, expected)
            self.assertNotIn('config.json', actual)
            self.assertNotIn('.github/workflows/build-private.yml', actual)
            self.assertFalse(any(p.endswith(('.pt', '.zip', '.tar.gz')) for p in actual))
            self.assertFalse((destination / '.git').exists())
            with self.assertRaises(ValueError):
                export_public.export(destination)


class WindowCoordinateTests(unittest.TestCase):
    def setUp(self):
        import importlib.util
        import sys
        from unittest.mock import MagicMock
        self.windows = MagicMock()
        fake_modules = {'pyautogui': MagicMock(), 'Quartz': MagicMock(),
                        'utils.windows_window': self.windows,
                        'utils.platform_setup': MagicMock()}
        spec = importlib.util.spec_from_file_location('isolated_window_utils', Path(__file__).resolve().parents[1] / 'utils/window_utils.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, fake_modules):
            spec.loader.exec_module(self.module)
        self.module.WINDOWS, self.module.MACOS = True, False
        self.module.windows_window = self.windows
        config = FishingConfig(Path(__file__).resolve().parents[1] / 'resources/default_config.json')
        self.window = self.module.GameWindow(config)
        self.window.window_id = 123

    def test_client_coordinates_not_scaled_twice(self):
        self.windows.client_rect.return_value = (120, 80, 1920, 1080)
        self.window.last_capture_rect = (120, 80, 1920, 1080)
        self.assertEqual(self.window.window_to_screen(300, 200), (420, 280))
        self.assertEqual(self.window.screen_to_window(420, 280), (300, 200))

    def test_secondary_screen_negative_origin(self):
        self.windows.client_rect.return_value = (-1920, 20, 1920, 1080)
        self.window.last_capture_rect = (-1920, 20, 1920, 1080)
        self.assertEqual(self.window.window_to_screen(300, 200), (-1620, 220))

    def test_window_move_or_disappearance_blocks_click(self):
        self.window.last_capture_rect = (120, 80, 1920, 1080)
        self.windows.client_rect.return_value = (121, 80, 1920, 1080)
        with self.assertRaises(self.module.WindowUnavailable):
            self.window.window_to_screen(300, 200)
        self.windows.client_rect.return_value = None
        with self.assertRaises(self.module.WindowUnavailable):
            self.window.window_to_screen(300, 200)

    def test_no_foreground_blocks_capture(self):
        self.windows.is_foreground.return_value = False
        with self.assertRaises(self.module.WindowUnavailable):
            self.window.screenshot()


if __name__ == '__main__':
    unittest.main()
