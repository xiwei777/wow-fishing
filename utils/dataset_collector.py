"""保存推理原图、自动标注和模型指纹，供用户复核后整理训练数据。"""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import cv2
from app_paths import VERSION
from utils.image_io import write_image


class DatasetCollector:
    """每次运行建立独立目录，不保存权重或上传用户截图。"""

    def __init__(self, base_dir="dataset", model_info=None, config=None):
        session = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:8]
        self.base_dir = Path(base_dir) / session
        self.images_dir = self.base_dir / 'images'
        self.labels_dir = self.base_dir / 'labels'
        self.annotated_dir = self.base_dir / 'annotated'
        for path in (self.images_dir, self.labels_dir, self.annotated_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.sample_count = 0
        self.model_info = dict(model_info or {})
        session_info = {
            'app_version': VERSION,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'model': self.model_info,
            'detection_config': config or {},
            'label_source': 'model_prediction',
            'requires_review': True,
        }
        (self.base_dir / 'session.json').write_text(json.dumps(session_info, ensure_ascii=False, indent=2), encoding='utf-8')

    def save_sample(self, screenshot, float_pos, window_rect=None, cast_number=None):
        """保存与本次预测严格对应的原图；未检出时写空标签。"""
        self.sample_count += 1
        name = f'frame_{self.sample_count:06d}'
        height, width = screenshot.shape[:2]
        annotated = screenshot.copy()
        predictions, label = [], ''
        if float_pos is not None:
            x, y, w, h = map(int, float_pos[:4])
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
                raise ValueError('预测框超出截图范围，拒绝保存错误标注。')
            confidence = float(float_pos[4])
            cx, cy, nw, nh = (x + w / 2) / width, (y + h / 2) / height, w / width, h / height
            label = f'0 {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n'
            predictions.append({'class_id': 0, 'bbox_xywh': [x, y, w, h], 'confidence': confidence})
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(annotated, f'float {confidence:.3f}', (x, max(15, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        write_image(self.images_dir / f'{name}.png', screenshot)
        write_image(self.annotated_dir / f'{name}.png', annotated)
        (self.labels_dir / f'{name}.txt').write_text(label, encoding='utf-8')
        metadata = {
            'image': f'images/{name}.png', 'width': width, 'height': height,
            'timestamp': datetime.now(timezone.utc).isoformat(), 'cast_number': cast_number,
            'predictions': predictions, 'model': self.model_info,
            'window_rect': window_rect, 'requires_review': True,
        }
        (self.labels_dir / f'{name}.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        return name

    def get_stats(self):
        return {'total_samples': self.sample_count, 'images_dir': str(self.images_dir), 'labels_dir': str(self.labels_dir)}
