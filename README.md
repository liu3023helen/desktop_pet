# Desktop Pet - 桌面电子宠物 v2

> 小新风格透明窗口宠物，配置驱动的打卡提醒助手。支持闹钟管理面板、网络时间校准、天气信息、贪睡/跳过交互。

## 功能特性

### 基础功能（一期）
- 🐾 **透明窗口宠物** — 无边框透明置顶，可拖拽移动
- 🎬 **序列帧动画** — 发呆、走动、欢呼等动画播放
- ⏰ **可扩展提醒引擎** — YAML 配置驱动，支持多场景提醒
- 🔗 **钉钉打卡跳转** — 客户端协议 + 网页版双通道
- 🔊 **音效提示** — 提醒触发时播放提示音
- 🔌 **开机自启** — 注册表方式，托盘菜单一键开关
- 🖥️ **多显示器适配** — 自动限制在主屏范围内
- 📦 **便携打包** — 单文件 exe，所有数据在 exe 同级 `data/` 目录

### 增强功能（二期）
- 📋 **闹钟管理面板** — GUI 表格化增删改查提醒任务，无需手动编辑 YAML
- ⏱️ **网络时间校准** — NTP 自动同步，防止本地时钟漂移导致打卡不准
- 🌤️ **天气信息** — 支持和风天气 / OpenWeatherMap，托盘气泡展示
- 😴 **贪睡/跳过** — 提醒触发时可延迟 5/10 分钟或今天跳过
- 📅 **工作日识别** — 打卡提醒仅在工作日触发，周末和法定假日自动跳过
- 🔕 **安静模式** — 一键静音，宠物静止不播放动画和音效

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

程序启动后会在系统托盘显示图标，宠物出现在桌面右下角。

### 3. 配置文件

首次运行时会自动将 `config.yaml` 复制到 `data/config.yaml`（exe 同级目录）。

修改该文件可自定义：
- 提醒时间、文案、动作类型
- 打卡 URL
- 工作日限定
- 网络时间校准设置
- 天气 API 配置

### 4. 管理提醒任务

右键点击托盘图标 → **"管理提醒"**，打开 GUI 管理面板：
- 查看所有提醒任务列表
- 新增/编辑/删除任务
- 启用/禁用切换
- 修改保存后实时生效，无需重启程序

### 5. 网络时间校准

右键点击托盘图标 → **"校准网络时间"**，从阿里云 NTP 服务器获取标准时间并自动校正提醒引擎的基准时间。

### 6. 查看天气

右键点击托盘图标 → **"查看天气"**，获取指定城市的实时天气信息（需在配置中设置 API Key）。

### 7. 打包为 exe

```powershell
pip install pyinstaller
python build.py
```

输出在 `dist/` 目录，单文件约 60MB。

## 项目结构

```
desktop_pet/
├── main.py              # 主入口（窗口+托盘+集成）
├── config_manager.py    # 配置管理（YAML读写+原子保存）
├── animation_player.py  # 序列帧动画播放器
├── reminder_engine.py   # 提醒引擎（QThread轮询+信号触发）
├── reminder_dialog.py   # 闹钟管理GUI面板（表格+表单）
├── snooze_handler.py    # 贪睡/跳过/完成状态管理器
├── workday_utils.py     # 工作日判断工具（含节假日扩展接口）
├── time_sync.py         # NTP网络时间校准服务
├── weather_service.py   # 天气信息获取服务
├── dingtalk_handler.py  # 钉钉跳转处理器
├── generate_assets.py   # 占位素材生成脚本
├── build.py             # PyInstaller打包脚本
├── DesktopPet.spec      # PyInstaller规格文件
├── config.yaml          # 默认配置模板
├── requirements.txt     # 依赖清单
└── assets/
    └── animations/
        ├── idle/        # 发呆动画
        ├── walk/        # 走动动画
        └── cheer/       # 欢呼动画
```

## 提醒配置格式

```yaml
# data/config.yaml - 电子宠物提醒配置

pet:
  name: "小新"
  style: "shinchan"
  default_animation: "cheer"

reminders:
  - name: "下班打卡"
    enabled: true
    time: "18:30"           # 24小时制 HH:MM
    weekdays_only: false    # 仅工作日触发
    action_type: "open_url" # open_url / play_animation / notify_only
    action_target: "dingtalk://..."
    animation: "cheer"      # 专属动画
    message: "下班啦！快去打卡~"
    sound: true
    snooze_enabled: true    # 允许贪睡
    snooze_minutes: 5       # 贪睡延迟分钟数

# 网络时间校准配置
time_sync:
  enabled: true
  ntp_server: "ntp.aliyun.com"
  tolerance_seconds: 30

# 天气配置
weather:
  enabled: false
  city: "北京"
  api_provider: "qweather"  # qweather / openweathermap
  api_key: ""               # 用户自行填入
  update_interval_minutes: 60
```

## 扩展提醒示例

通过管理面板添加，或直接编辑配置文件：

```yaml
reminders:
  - name: "晨间提醒"
    enabled: true
    time: "09:00"
    weekdays_only: true
    action_type: "notify_only"
    animation: "cheer"
    message: "早上好！开始工作吧~"
    sound: true

  - name: "喝水提醒"
    enabled: true
    time: "15:00"
    weekdays_only: true
    action_type: "play_animation"
    animation: "walk"
    message: "该起来喝杯水了！"
    sound: true
```

无需修改代码，保存后通过管理面板刷新或重启程序即可生效。

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI框架 | PyQt5 |
| 打包工具 | PyInstaller |
| 配置存储 | PyYAML |
| 时间同步 | NTP (socket) |
| 天气API | 和风天气 / OpenWeatherMap |
| 平台 | Windows 10/11 |

## 非功能性指标

| 指标 | 要求 | 当前状态 |
|------|------|----------|
| CPU占用（闲置） | ≤5% | ✅ 实测达标 |
| 内存占用 | ≤100MB | ✅ 实测达标 |
| 帧率 | 稳定30fps | ✅ |
| 包体积 | ≤70MB | ✅ ~60MB |
| 启动时间 | ≤3秒 | ✅ ~1.5秒 |
| 定时器精度 | 误差≤5秒 | ✅ 1秒轮询 |
| DPI适配 | 125%/150% | ✅ |

---

*最后更新：2026-07-18*
*版本：v2（二期开发完成）*
