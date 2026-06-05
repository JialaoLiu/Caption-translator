# Bilibili 直播姬设置教程

Caption translator 是原生桌面应用。它会显示一个独立的 `Caption Translator Subtitle` 字幕窗口，直播姬可以把这个窗口当作素材捕捉。

## 推荐链路

```text
字幕工具 pinned 窗口
↓
Bilibili 直播姬
↓
窗口捕捉 / 截屏捕捉
```

## 方法一：窗口捕捉

1. 启动 Caption translator。
2. 在主窗口里选择音频输入设备。
3. 保持默认 `small + cpu + int8`，点击 `Start`。
4. 确认屏幕上出现 `Caption Translator Subtitle` 字幕窗口。
5. 打开 Bilibili 直播姬。
6. 添加直播素材。
7. 选择 `窗口捕捉`。
8. 在窗口列表中选择 `Caption Translator Subtitle`。
9. 在直播画面里调整字幕素材的位置和大小。

## 方法二：截屏捕捉

如果窗口捕捉不稳定：

1. 在直播姬中添加直播素材。
2. 选择 `截屏捕捉`。
3. 框选字幕窗口所在区域。
4. 直播过程中尽量不要移动字幕窗口。

## 字幕窗口设置建议

- 背景色：黑色
- 透明度：70% 到 90%
- 字体大小：按直播分辨率调整，一般 28 到 40
- 双语显示时窗口高度调大一些
- 需要拖动或调尺寸时可以开启边框，调好后再关闭边框

## PUBG 直播性能建议

- 优先 `small + cpu + int8`
- 卡顿时切换 `base` 或 `tiny`
- 不要默认用 CUDA
- 不要默认用 `large-v3`
- 先录制测试 5 到 10 分钟，确认游戏帧率和直播编码稳定

## 粤语转简体普通话

推荐设置：

- Source Language：`Cantonese / 粤语`
- Target Language：`Mandarin Simplified / 简体普通话`
- Display Mode：`Translation only` 或 `Bilingual`
- Translator Backend：`Ollama` 或 `OpenAI-compatible API`

不要使用 Mock 做真实直播翻译。Mock 只用于确认字幕流程是否跑通。
