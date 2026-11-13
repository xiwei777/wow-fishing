# 依赖与模型说明

本项目原 README 声明的 MIT 许可仅适用于项目自己的源码，不重新许可第三方代码、模型权重或数据集。
公开源码不包含训练权重和数据集。权重可由构建者通过 `--model` 指定并嵌入发布程序；嵌入不构成防提取保护。

主要第三方组件包括 Python、Tcl/Tk、Ultralytics、PyTorch、torchvision、NumPy、OpenCV、Pillow、PyAutoGUI、pynput、PyObjC 和 PyInstaller，分别适用其自身许可证。

Ultralytics 使用 AGPL-3.0 / Enterprise 双许可。其官方说明将模型及闭源部署纳入许可考虑；不能仅凭本项目 MIT 声明，认定包含私有权重的完整发行包也可以按 MIT 分发。发布者应核实模型来源和已获得的授权，按适用许可提供对应源代码、许可证和通知，或取得相应 Enterprise 授权。

- Ultralytics：https://www.ultralytics.com/license
- Ultralytics 源码许可：https://github.com/ultralytics/ultralytics/blob/main/LICENSE
- PyTorch：https://github.com/pytorch/pytorch/blob/main/LICENSE
- PyInstaller：https://pyinstaller.org/en/stable/license.html

本文件是依赖索引，不替代各依赖的完整许可证。打包脚本将安装环境中各 Python distribution 的许可证文件一并收集到应用资源的 `licenses/` 中。
