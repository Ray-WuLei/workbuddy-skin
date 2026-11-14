# 主题与壁纸素材说明

本仓库**不包含任何壁纸图片，也不包含配色 json**。两者都需要你在本机自备。

## 目录结构

WorkDaddy 从 `%APPDATA%\WorkDaddy\` 读取主题，实际布局是：

```
%APPDATA%\WorkDaddy\
  themes\
    moon-silhouette.json          <- 配色定义
    gojo-inverse.json
    neon-violet.json
    amber-eye.json
    moon-silhouette\
      background.webp             <- 壁纸
    gojo-inverse\
      background.webp
    neon-violet\
      background.webp
    amber-eye\
      background.webp
  current-theme.json
  ui-port.json
  .api-token
```

`skin-watch.py` 读取 `<id>\background.webp` 并转成 base64 注入页面；WorkDaddy 的 `/api/theme-apply` 读取根目录的 `<id>.json`。两者缺一不可，且 id 必须出现在 `skin-watch.py` 顶部的 `SKINS` 白名单里。

## 为什么素材不在仓库里

原始 4 套素材涉及动漫角色形象，版权归各自权利人，公开分发不合适。请换成自己拥有使用权的图片（建议 WebP，暗色构图对聊天区可读性更友好）。

配色 json 可以用 WorkDaddy 自带的主题编辑器导出，再按下面的格式改。

## 配色文件格式

```json
{
  "id": "moon-silhouette",
  "name": "月影剪影",
  "author": "me",
  "dark": true,
  "colors": {
    "--vscode-editor-background": "#0c0a10",
    "--vscode-editor-foreground": "#f2f2f4",
    "--vscode-sideBar-background": "#0e0c12",
    "--vscode-activityBar-background": "#0e0c12",
    "--vscode-button-background": "#5b4bb8"
  },
  "image": "background.webp"
}
```

`colors` 是 WorkBuddy 界面用到的 CSS 变量集合，完整变量列表请参考 WorkDaddy 自带主题；这里只列了几个关键项。新增主题时，记得同步改 `skin-watch.py` 的 `SKINS`。
