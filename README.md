# WorkBuddy 换肤守护（skin-keeper）

给 WorkBuddy 桌面客户端加自定义皮肤，并在页面刷新、客户端重启、版本更新之后自动恢复。右下角一个按钮即可随机换肤，也可以右键选具体皮肤。

这是一个个人实验项目，不是 WorkBuddy 或 WorkDaddy 的官方产品。

## 为什么要单独写一层守护

直接在页面里注入一段 CSS 很快就会失效，实际踩到的几个问题：

- WorkDaddy 用 `background` 简写下发壁纸，Chromium 会把它解析成空的 `background-image: none !important`，壁纸根本不显示。改用 `background-image` 长属性并加 `!important` 才能压过去。
- WorkBuddy 更新或重载页面会清空 DOM，注入的 `<style>`、按钮、面板卡片一起消失。
- 从桌面图标正常启动的 WorkBuddy 不带 CDP 调试端口（只认环境变量 `WORKBUDDY_REMOTE_DEBUGGING_PORT`），此时无法注入。
- WorkDaddy 自带的主题面板会把主题悄悄换回内置款，皮肤"莫名其妙就没了"。
- WorkBuddy 更新后页签顺序会变，按固定下标定位面板必然错位。

所以这里做成一个每 2 秒巡检一次的常驻进程：缺什么补什么，并且只认白名单里的 4 套皮肤。

## 工作原理

三层结构：

1. **WorkDaddy daemon**：本地 HTTP 服务（默认 `127.0.0.1:47832`，端口读 `ui-port.json`），通过 `/api/theme-apply` 应用主题，鉴权用 `%APPDATA%\WorkDaddy\.api-token`，请求头 `x-workdaddy-token`。
2. **CDP**：连 WorkBuddy 页面（`127.0.0.1:9222`），注入壁纸 CSS、精简面板的 CSS，以及换肤 UI。`cdpmini.py` 是手写的 RFC6455 WebSocket 客户端，只用 Python 标准库，不依赖任何 pip 包。
3. **skin-watch.py**：常驻巡检（单实例锁 `127.0.0.1:47999`）。检查 daemon 是否存活（挂了就带 `WBSWITCH_PROFILE` 拉起）、主题是否漂移、页面标记 `data-wbs-theme-id` 是否还在、壁纸样式和换肤按钮是否被清掉。全部通过 CDP 重新注入。

换肤按钮不直接调 API：它只在 `<html>` 上写一个 `data-swx-want` 属性，由守护进程读取后执行真正的 `theme-apply`。这样绕开了页面内 `fetch` 的 CORS、token 暴露和后台标签页定时器节流问题。同时也保留页面内的即时应用路径，守护没开时点一下也能换。

自愈靠 Windows 计划任务：登录时启动，之后每 5 分钟检查一次进程是否还在，不在就拉起。

## 文件

| 文件 | 作用 |
| --- | --- |
| `skin-watch.py` | 主守护进程，巡检 / 自愈 / 注入 |
| `cdpmini.py` | 零依赖 CDP 客户端（stdlib 手写 WebSocket） |
| `skin-ui.js` | 注入到页面的换肤 UI：悬浮按钮、右键菜单、面板卡片、面板精简 CSS |
| `start-keeper.bat` | 手动启动入口 |
| `skin-watch-hidden.vbs` | 无控制台窗口的启动入口，可带一个主题 id 参数 |
| `theme.txt` | 当前主题 id，换肤时自动写入 |
| `themes/README.md` | 壁纸与配色素材的放置说明（素材需自备） |

本地开关（都不进版本库）：

- `no-restart.flag`：禁止守护自动重启 WorkBuddy
- `keep-all.flag`：恢复 WorkDaddy 面板的全部功能，不再精简
- `watch.log`：运行日志，超过 1 MB 自动轮转

## 环境与依赖

- Windows + WorkBuddy 桌面客户端
- WorkDaddy 已安装并能正常启动 daemon
- Python 3.10+（脚本只用标准库；默认找 WorkBuddy 自带的 `pythonw.exe`，可用环境变量 `WBSKIN_PYTHON` 覆盖）
- WorkBuddy 必须以 CDP 端口启动：设置环境变量 `WORKBUDDY_REMOTE_DEBUGGING_PORT=9222` 后再启动客户端。守护发现客户端在跑但没有 9222 端口时，会在 45 秒内自动带该变量重启一次（一小时内最多两次）。
- daemon 启动必须带 `WBSWITCH_PROFILE=workbuddy-cn`（或 `scripts/profile-id.txt` 里的值），否则严格目标归属判定会让 `theme-apply` 返回 500 "CDP 未连接"。`skin-watch.py` 已处理。

## 安装

1. 克隆本仓库到任意目录，例如 `%USERPROFILE%\workbuddy-skin`。
2. 按 [`themes/README.md`](themes/README.md) 把 4 套配色和壁纸放到 `%APPDATA%\WorkDaddy\themes\` 下。**壁纸图片不随仓库分发，需要自备。**
3. 确认 WorkBuddy 带 `WORKBUDDY_REMOTE_DEBUGGING_PORT=9222` 启动。
4. 双击 `start-keeper.bat`，或命令行运行 `pythonw.exe skin-watch.py`。看到右下角出现调色板按钮即成功。
5. 需要开机自启时，在「任务计划程序」里建一个任务：触发器为「登录时」并启用「每 5 分钟重复」，操作为启动 `pythonw.exe`，参数为 `skin-watch.py` 的完整路径。也可以直接用注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 指向 `skin-watch-hidden.vbs`（这种方式没有崩溃后复活能力）。

想改素材库：编辑 `skin-watch.py` 顶部的 `SKINS` 列表（id + 中文名），并同步准备对应的 `<id>.json` 和 `<id>\background.webp`。白名单之外的主题一律拒绝，WorkDaddy 内置主题顶不掉当前皮肤。

## 踩过的坑

| 现象 | 原因 / 处理 |
| --- | --- |
| 壁纸不显示，背景一片黑 | `background` 简写被解析成 `background-image: none`；用长属性 + `!important` 覆盖 |
| `theme-apply` 返回 500 "CDP 未连接" | daemon 缺 `WBSWITCH_PROFILE` |
| 按钮点击没反应 | 旧注入的闭包事件监听器；改为全局函数 + 每次注入重建节点 |
| 后台标签页定时器被节流 | 按钮只写 DOM 属性，实际切换交给常驻守护 |
| 面板卡片跑到错误页签 | WorkBuddy 更新会重排 pane；按 `.wbs-avatar-card` 或子节点数量动态定位 |
| 主题被悄悄换掉 | 同时校验 `current-theme.json` 和页面 `data-wbs-theme-id` 标记，二者都必须是白名单皮肤 |
| `/api/theme-bg` 顺带切主题 | 装多主题后需要重新 `theme-apply` |

## 已知限制

- 只在 Windows 上验证过，路径按 Windows 用户目录写死为 `AppData/Roaming/WorkDaddy`。
- 强依赖 WorkDaddy 的本地 API 和 WorkBuddy 页面 DOM。上游若大改 CSS 选择器、移除 `%APPDATA%\WorkDaddy` 素材目录，或改变 CDP 目标判定规则，注入会失效，需要跟着改。
- 换肤按钮的即时应用路径仍会调用页面内 `fetch`；守护进程在运行时以守护为准。
- 本仓库**不包含任何壁纸图片**。4 套原始素材涉及动漫角色，版权归各自权利人，公开分发不合适，请替换为自己拥有使用权的图片。

## 免责声明

非官方项目，仅为个人学习与界面定制实验。使用它会向本地客户端注入脚本、隐藏第三方插件的部分面板、并在特定条件下重启 WorkBuddy 进程。使用前请自行评估风险，作者不对数据丢失、客户端异常或第三方条款问题负责。

## License

[MIT](LICENSE)
