# Windows exe 打包教程

本项目使用 PyInstaller 打包 Windows exe。

## 环境准备

建议使用 Windows + Python 3.10 或更新版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 打包

在项目根目录运行：

```powershell
.\build_windows.ps1 -Clean
```

输出位置：

```text
dist/CaptionTranslator.exe
```

## 模型缓存说明

不要把 `medium`、`large-v3` 等大模型强行打包进 exe。这样会导致发布包非常大，也不适合用户按需选择模型。

推荐策略：

- exe 只包含应用代码和运行依赖
- 用户首次选择模型时由 faster-whisper 下载并缓存
- 发布说明里提醒用户首次运行需要联网下载模型
- 高级用户可以提前在目标机器预缓存模型

## API key

OpenAI-compatible API key 由用户在 GUI 中填写。不要写死在代码里，不要提交到 GitHub。

## 常见问题

如果打包后启动失败：

- 确认音频设备驱动正常
- 确认杀毒软件没有拦截 exe
- 重新使用 `.\build_windows.ps1 -Clean` 打包
- 在源码环境中先运行 `python -m realtime_subtitle.main` 确认依赖可用
