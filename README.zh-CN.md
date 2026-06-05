# Caption translator

Caption translator 是一个 Windows 原生桌面实时语音字幕翻译工具，面向 Bilibili 直播姬 + PUBG 直播场景。它不是 localhost 网页 demo，而是 PyQt6 GUI 应用，可以打包成 Windows exe。

GitHub 仓库：[JialaoLiu/Caption-translator](https://github.com/JialaoLiu/Caption-translator)

核心思路：

```text
麦克风 / 系统音频
↓
faster-whisper 识别原文
↓
translator.py 翻译
↓
pinned subtitle window / subtitle.txt
```

## 已实现功能

- PyQt6 主控制窗口，检测 PyQt-SiliconUI 可用性，不可用时自动 fallback
- 独立置顶字幕窗口，适合直播姬“窗口捕捉”或“截屏捕捉”
- 音频输入设备选择
- ASR 模型切换：`tiny/base/small/medium/large-v3`
- device：`cpu/cuda`
- compute_type：`int8/float16/float32`
- 源语言：`auto/yue/zh/en`
- 目标语言：`zh/en/yue`
- 显示模式：原文/翻译/双语
- 翻译后端：Mock/Ollama/OpenAI-compatible API
- 同时输出 UTF-8 `subtitle.txt`
- `config.json` 保存设置，配置损坏时自动恢复默认配置
- PyInstaller Windows 打包脚本

## 直播推荐配置

PUBG + 直播姬建议：

- 默认 `small + cpu + int8`
- CPU 占用高就换 `base` 或 `tiny`
- 不默认 CUDA，避免影响游戏帧率和直播编码
- 不建议直播打游戏时使用 `medium` 或 `large-v3`
- 字幕刷新间隔建议 `2` 到 `3` 秒

## 安装运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m realtime_subtitle.main
```

可选 PyQt-SiliconUI：

```powershell
pip install -r requirements-silicon.txt
```

如果 PyQt-SiliconUI 不兼容，应用会继续使用 PyQt6 fallback 样式。

## 直播姬捕捉方式

推荐使用：

```text
字幕工具 pinned 窗口
↓
Bilibili 直播姬
↓
窗口捕捉 / 截屏捕捉
```

详细教程见 [docs/bilibili_live_setup.zh-CN.md](docs/bilibili_live_setup.zh-CN.md)。

## Windows 打包

```powershell
.\build_windows.ps1 -Clean
```

输出位置：

```text
dist/CaptionTranslator.exe
```

模型不会被强行打包进 exe。首次使用某个 faster-whisper 模型时会下载并缓存，或者你可以提前在目标电脑上预缓存模型。

详细教程见 [docs/build_windows.zh-CN.md](docs/build_windows.zh-CN.md)。

## 翻译说明

Whisper/faster-whisper 只负责语音转文字，不负责任意语言互译。互译由 `translator.py` 完成。

当前后端：

- Mock：占位测试
- Ollama：本地 Ollama HTTP API
- OpenAI-compatible API：兼容 `/v1/chat/completions` 的接口

API key 不要写进代码，也不要提交到 GitHub。

## 免责声明

实时识别和翻译会受噪音、口音、游戏音效、多人说话影响。正式直播前请先测试 CPU/GPU 占用和字幕延迟。
