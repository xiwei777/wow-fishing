# WoW Fishing

Python 桌面钓鱼工具：YOLO 定位鱼漂、像素差分检测咬钩。Windows 和 macOS 共用源码，各自在本平台构建独立程序。最终用户不需要安装 Python 或 AI 软件。

## 使用发布程序

- Windows：双击 `WoWFishing-<版本>-windows-amd64.exe`。
- Apple Silicon Mac：解压对应 `macos-arm64.zip`，将 `WoWFishing.app` 拖到应用程序目录后双击。
- Intel Mac：使用独立构建的 `macos-x86_64.zip`，不混用 ARM 版本。
- 程序加载后切回游戏，按 **F11** 开始/暂停，**ESC** 退出。失去游戏焦点会暂停。
- 首次使用 macOS 需要在系统设置中允许屏幕录制、辅助功能/输入监控，随后重新打开程序。
- 当前构建脚本不配置开发者证书或 Apple 公证；未签名发行版可能需要系统确认，不能保证所有电脑首次无提示双击启动。

详细设置和保存位置见 [使用说明](docs/USER_GUIDE.md)。当前版本的验收结果以 `PROJECT_STATUS.md`（私有开发仓库）和每个发行包的 `build-info.json` 为准；源码中有 Windows 支持不等于已经完成 Windows 游戏实测。

## 源码运行

使用 Python 3.10，安装 `requirements.txt` 后运行：

```sh
python desktop_app.py --model /path/to/your-model.pt
```

公开源码**不附带权重和训练数据集**，需要自行提供兼容的单类别鱼漂检测 `.pt` 模型。私有开发仓库保存 `models/best_v4.pt`，不保存数据集。程序不会自动下载替代模型。

## 构建

```sh
python -m pip install -r requirements-build.txt
python scripts/build_app.py --model /path/to/your-model.pt
```

Windows 推荐先安装 CPU 版 PyTorch，或使用 `scripts/build_windows.bat models\best_v4.pt`。Mac 使用 `bash scripts/build_macos.command models/best_v4.pt`。打包脚本必须在目标系统执行，不能在 macOS 原生生成 Windows EXE。

权重通过构建参数指定并嵌入程序资源。Windows 输出单文件 EXE；Mac 输出带内置运行时的 APP 压缩包。运行记录只写到用户数据目录，不写入应用包、临时解包目录或 Git 仓库。构建后自动执行离线模型推理自检，成功才生成 `release/` 中的交付文件和校验和。离线自检不验证游戏截图权限和实际点击。

## 推理记录

默认保存每次鱼漂定位推理的原始窗口截图、带框预览、YOLO 标签和 JSON 元数据。未检出时也保存原图和空预测；所有标签均标为待人工复核。记录模型 SHA-256、文件名、置信度、时间和检测配置，不导出 `.pt`。咬钩检测每帧 ROI 仅在调试模式额外保存。记录不自动上传。

## 开发和公开发布

开发者在同一个私有仓库中同步代码和模型；公开仓库接收白名单导出的源码快照，独立建立历史。不要把私有仓库设为公开，也不要向公开仓库推送私有分支或历史。导出命令：

```sh
python scripts/export_public.py --output build/public-source-v0.1.0
```

公开仓库的 Releases 用于发布内置权重的程序。内置权重仍可能从程序中提取，不提供防逆向保证。

## 测试

```sh
python -m unittest discover -s tests -v
python desktop_app.py --self-test --model /path/to/model.pt --result-file self-test.json
```

自检只对合成图推理，不截图或发送键鼠事件。跨平台开发交接见 [Windows Agent 说明](docs/WINDOWS_HANDOFF.md)。

## 许可

本项目自有源码沿用 MIT。第三方依赖和模型不由该许可覆盖，尤其 Ultralytics 的 AGPL-3.0 / Enterprise 许可需单独核实；见 [依赖说明](THIRD_PARTY_NOTICES.md)。
