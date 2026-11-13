# 给 Windows 端开发 Agent 的交接

这是 Windows/macOS 共用的 Python 3.10 桌面应用。私有开发仓库是唯一日常开发入口，包含 `models/best_v4.pt`；不要从公开仓库拉取开发权重。开始前先查看 Git 状态和远程更新，结束后提交、推送自己的修改，避免与 Mac 同时修改同一文件。

## 入口与约束

- 桌面入口：`desktop_app.py`；命令行调试：`fishing_bot.py`。
- 路径统一由 `app_paths.py` 提供；不要依赖当前工作目录，不能向 EXE 临时解包目录或 APP 包写配置/截图。
- Windows DPI 在导入 PyAutoGUI、pynput、Tk 前设置；打包 EXE 也声明 PerMonitorV2 manifest。
- Windows 窗口后端：`utils/windows_window.py`；通过客户区截图、ClientToScreen 将预测坐标映射到桌面。
- 发布模型构建时通过 `--model` 指定。不要将 `.pt`、数据集、历史模型压缩包或私有 Git 历史推到公开仓库。
- 用户数据只保存在本机；默认保存原图、自动标注和模型指纹，不复制权重到用户保存目录。

## 首次安装与构建

安装 64 位 Python 3.10，克隆私有仓库后执行：

```bat
scripts\build_windows.bat models\best_v4.pt
```

这会创建 `.venv`、安装 CPU 推理依赖、生成单文件 EXE 并对内置模型做离线推理自检。已有开发环境也可直接执行 `python scripts/build_app.py --model models/best_v4.pt`。

## 必须在 Windows 实机完成的验收

1. `python -m unittest discover -s tests -v`；随后确认打包内置模型 SHA-256 与私有权重一致。
2. 在没有 Python、没有 AI 软件的普通用户环境双击 EXE；能显示状态窗口和日志。
3. 测试包含中文、空格的路径，100%/125%/150% 显示缩放，主屏及副屏；预测框与实际鼠标位置一致。
4. 测试窗口模式、无边框模式；失去焦点、最小化、窗口移动/缩放后停止输入，不点击旧坐标。
5. F11 快速开关不产生并行钓鱼线程；ESC 和关闭窗口停止输入。
6. 记录与推理使用同一张原图，含框、置信度及模型指纹；未检出也有记录。记录保存在用户目录，重启/升级不丢失。
7. 在实际游戏中验证一次甩竿、识别、咬钩、收竿；将系统版本、缩放、截图方式和实测结果写回私有仓库的 `PROJECT_STATUS.md`。

Mac 上的单元测试或打包成功不能替代上述 Windows 实测。当前没有自动化游戏实测；不要把尚未验证的行为标为已完成。
