# Caption translator

Caption translator 是一个 Windows 原生桌面实时语音字幕翻译工具，面向 Bilibili 直播姬 + PUBG 直播场景。它不是 localhost 网页 demo，而是 PyQt6 GUI 应用，可以打包成 Windows exe。

GitHub 仓库：[JialaoLiu/Caption-translator](https://github.com/JialaoLiu/Caption-translator)

## 已实现功能

- PyQt6 主控制窗口，安装 `pyqt-siliconui` 作为 UI 依赖，并保留 PyQt6 QSS fallback
- 独立置顶字幕窗口，适合直播姬“窗口捕捉”或“截屏捕捉”
- 音频模式：Mic only / System only / Mic + System
- Windows WASAPI loopback 捕捉电脑声音
- 默认 ASR：SenseVoiceSmall 234M
- 可选 ASR 引擎：Qwen3-ASR-0.6B、Qwen3-ASR-1.7B、Fun-ASR-Nano、vLLM/FunASR OpenAI-compatible ASR server
- 默认翻译后端：Ollama
- 备用翻译后端：Disabled、OpenAI-compatible API
- 默认配置：auto 源语言、简体普通话目标语言、只显示译文、CPU int8
- 同时输出 UTF-8 `subtitle.txt`

## 安装运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m realtime_subtitle.main
```

可选 ASR 引擎需要额外依赖：

```powershell
pip install -r requirements-asr.txt
```

然后在软件的 Advanced settings 里选择 ASR engine，点击 `下载 ASR 模型`。下载进度会显示在进度条里，模型保存到：

```text
models/asr/
```

默认推荐模型是 SenseVoiceSmall 234M。

## 可选 vLLM / FunASR Server ASR

高精度或高显存 ASR 不适合直接塞进普通 exe。更合理的方式是让 vLLM/FunASR 在本机启动 OpenAI-compatible 转写服务，Caption translator 只负责连接服务。

Qwen3-ASR via vLLM：

```powershell
vllm serve Qwen/Qwen3-ASR-1.7B
```

然后在高级设置里选择 `Qwen3-ASR vLLM server`：

```text
ASR 服务地址：http://127.0.0.1:8000/v1
ASR 服务模型：Qwen/Qwen3-ASR-1.7B
```

FunASR OpenAI-compatible server：

```powershell
funasr-server --model sensevoice --device cuda
```

然后在高级设置里选择 `FunASR/vLLM OpenAI-compatible ASR server`：

```text
ASR 服务地址：http://127.0.0.1:8000/v1
ASR 服务模型：sensevoice
```

Server ASR 模式不会在软件里下载本地 ASR 权重，模型加载和 GPU/CPU 占用由外部服务负责。

## Mock 是什么

Mock 是“假翻译器/测试翻译器”。它不会真的翻译，只用于开发时测试字幕流程是否连通。

普通用户不应该用 Mock 做直播翻译。当前主界面已经不显示 Mock，只保留 Ollama、Disabled、OpenAI-compatible。

## Ollama 默认翻译

默认真实翻译后端是 Ollama，默认模型是：

```text
qwen2.5:3b
```

程序会检测：

```text
GET http://localhost:11434/api/tags
```

如果 Ollama 没启动，GUI 不会崩溃，会禁用翻译并显示原文。如果 Ollama 已启动但缺少模型，请运行：

```powershell
ollama pull qwen2.5:3b
```

界面里也可以选择 `qwen3:4b` 或输入其他 Ollama 模型名。

## 音频模式

- `Mic only`：只录制麦克风
- `System only`：只录制电脑声音，Windows 下使用 WASAPI loopback
- `Mic + System`：麦克风和电脑声音同时录制，在程序内部混音后送入单路 ASR

默认是 `Mic + System`。WASAPI loopback 只负责电脑输出声音，不会自动包含麦克风。

## 粤语转简体普通话推荐设置

- Source Language：`Cantonese / 粤语` 或 `auto`
- Target Language：`Mandarin Simplified / 简体普通话`
- Display Mode：`Translation only`
- Translator Backend：`Ollama`

Whisper/faster-whisper 主要负责语音转文字。粤语转普通话属于语体转换和翻译，需要 translator backend 处理；应用会在最终输出到 `Mandarin Simplified` 时强制做简体规范化，避免字幕残留繁体。

## Windows 打包

```powershell
.\build_windows.ps1 -Clean
```

输出位置：

```text
dist/CaptionTranslator.exe
```

大型 ASR 模型不会被强行打包进 exe。用户可以在软件里按需下载。

## 免责声明

实时识别和翻译会受噪音、口音、游戏音效、多人说话影响。正式直播前请先测试 CPU/GPU 占用和字幕延迟。
