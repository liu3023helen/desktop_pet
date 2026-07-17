# Desktop Pet - 桌面电子宠物 MVP

> 小新风格透明窗口宠物，配置驱动的下班打卡提醒

## 快速开始

### 1. 安装依赖

```powershell
cd desktop_pet
python -m pip install -r requirements.txt
```

如遇网络问题，使用清华镜像：
```powershell
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

### 2. 运行程序

```powershell
python main.py
```

### 3. 配置文件

首次运行时会自动将 `config.yaml` 复制到 `%APPDATA%\DesktopPet\config.yaml`。

修改该文件可自定义：
- 提醒时间
- 提醒文案
- 打卡URL
- 静音开关

### 4. 打包为exe

```powershell
pip install nuitka
python build.py
```

输出在 `dist/` 目录。

## 项目结构

```
desktop_pet/
├── main.py              # 主入口
├── config_manager.py    # 配置管理
├── pet_window.py        # 宠物窗口（旧版，已合并到main）
├── animation_player.py  # 序列帧动画播放器
├── reminder_engine.py   # 提醒引擎
├── dingtalk_handler.py  # 钉钉跳转处理器
├── generate_assets.py   # 占位素材生成脚本
├── build.py             # Nuitka打包脚本
├── config.yaml          # 默认配置模板
├── requirements.txt     # 依赖清单
└── assets/
    └── animations/
        ├── idle/        # 发呆动画 (8帧)
        ├── walk/        # 走动动画 (12帧)
        └── cheer/       # 欢呼动画 (16帧)
```

## 扩展提醒

在 `%APPDATA%\DesktopPet\config.yaml` 中添加新提醒：

```yaml
reminders:
  - name: "运动提醒"
    enabled: true
    time: "20:00"
    action_type: "notify_only"
    animation: "walk"
    message: "该起来动一动了！"
    sound: true
```

无需修改代码，重启程序即可生效。
