# shell-hub P1-2 待办厚度 + 界面修改验收

时间（Asia/Shanghai）：2026-11-12 18:29:19 Asia/Shanghai

## 结论

- 总结果 `ok`：**通过**（见 `.smoke/p1_todo_depth_result.json`）
- A 左轨功能名常显：通过
- B 打开面板后左轨名称全文可见：通过
- C 收起对话 ≠ 收起 HUD：通过
- D 收起对话后岛面不重叠，再点可开舱：通过
- E 对话与功能并存、互不吞状态、中央可穿透：通过
- F 子待办 + 每日/每周周期（及日历）：通过

## 本轮 UI 修改

- 左轨取消 01/02/03 等编号主识别，改为常显短功能名：聊天、待办、笔记、剪贴板、便签、倒计时、启动、搜索、设置；轨宽按名称让出，面板从轨右缘铺开。
- 打开任一功能面板后，左轨名称仍全文可见，不再被卡片压成半截字（名称在轨内常显，不再靠悬停飞出标签）。
- 对话舱顶部将「收起对话」做成独立控件（data-collapse-chat），不再与「新会话 / 对话」同等权重并列；点它只收舱。
- 岛右侧 ▾ 仍只管 HUD 壳展收；收起对话后岛回到紧凑态，品牌区第二行改为「点击打开对话」作为会话提示，日衰% 与 ▾ 互不挤压。
- 对话舱与左侧功能面板可同时开：打开待办/笔记等不再关舱，收舱也不关面板；点左轨「聊天」或点岛是展开/聚焦对话舱。两面同时开时岛/舱自动让到面板右侧，避免挡住输入区和左轨。
- 待办厚度复用原版 TodoView：可建子待办并勾完（父项未完成时子项状态保留），可设每日/每周周期，完成一轮后到期再出现；侧旁日历可看出哪天有待办、点那天看当天列表。未做第二套仪表盘或布局编辑。
- 顺手：紧凑岛加宽到 360px，关键元素 flex-shrink:0，避免截图/录屏/齿轮把日衰和 ▾ 挤叠；Esc 分层为先收对话、再收 HUD 壳、最后贴顶。

## 截图

- `A_rail_names.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\A_rail_names.png`
- `B_notes_panel_rail.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\B_notes_panel_rail.png`
- `C1_chat_collapse_control.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\C1_chat_collapse_control.png`
- `D1_island_compact.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\D1_island_compact.png`
- `D2_reopen_chat.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\D2_reopen_chat.png`
- `E1_todo_and_chat.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\E1_todo_and_chat.png`
- `E2_typed_or_sent.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\E2_typed_or_sent.png`
- `E3_chat_and_clipboard.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\E3_chat_and_clipboard.png`
- `E4_chat_and_launch.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\E4_chat_and_launch.png`
- `E5_both_open_center.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\E5_both_open_center.png`
- `E6_idle_passthrough.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\E6_idle_passthrough.png`
- `F1_parent_and_sub.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\F1_parent_and_sub.png`
- `F2_sub_checked_parent_open.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\F2_sub_checked_parent_open.png`
- `F3_daily_created.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\F3_daily_created.png`
- `F4_weekly_created.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\F4_weekly_created.png`
- `F5_daily_rolled.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\F5_daily_rolled.png`
- `F6_calendar_day.png` → `C:\Users\wcy\projects\XXXX\.smoke\p1_todo_depth\F6_calendar_day.png`

## 分项记录

### A_rail_names（通过）

```json
{
  "ok": true,
  "opened": true,
  "names": [
    "聊天",
    "待办",
    "笔记",
    "剪贴板",
    "便签",
    "倒计时",
    "启动",
    "搜索",
    "设置"
  ],
  "want": [
    "聊天",
    "待办",
    "笔记",
    "剪贴板",
    "便签",
    "倒计时",
    "启动",
    "搜索",
    "设置"
  ],
  "has_numbers": false,
  "rail": {
    "rail": [
      14,
      64,
      86,
      939,
      72
    ],
    "panel": [
      94,
      64,
      914,
      939
    ],
    "overlapRailPanel": false,
    "items": [
      {
        "nav": "chat",
        "text": "聊天",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          112,
          62,
          129
        ]
      },
      {
        "nav": "todos",
        "text": "待办",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          150,
          62,
          167
        ]
      },
      {
        "nav": "notes",
        "text": "笔记",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          188,
          62,
          205
        ]
      },
      {
        "nav": "clipboard",
        "text": "剪贴板",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          32,
          226,
          68,
          243
        ]
      },
      {
        "nav": "sticky",
        "text": "便签",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          264,
          62,
          281
        ]
      },
      {
        "nav": "countdown",
        "text": "倒计时",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          32,
          302,
          68,
          319
        ]
      },
      {
        "nav": "launch",
        "text": "启动",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          340,
          62,
          357
        ]
      },
      {
        "nav": "search",
        "text": "搜索",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          378,
          62,
          395
        ]
      },
      {
        "nav": "settings",
        "text": "设置",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          431,
          62,
          448
        ]
      }
    ]
  }
}
```

### B_rail_visible_with_panel（通过）

```json
{
  "ok": true,
  "click": {
    "ok": true,
    "screen": [
      75,
      294
    ],
    "sel": "[data-nav=\"notes\"]"
  },
  "state": {
    "mode": "deck",
    "geo": "full",
    "docked": false,
    "panel": "notes",
    "chat": true,
    "deck": true,
    "ignoring": false,
    "pct": 0,
    "notes": {
      "list": true,
      "editor": false,
      "active": null,
      "count": 9
    },
    "viewport": [
      1707,
      1019
    ]
  },
  "rail": {
    "rail": [
      14,
      64,
      86,
      939,
      72
    ],
    "panel": [
      94,
      64,
      914,
      939
    ],
    "overlapRailPanel": false,
    "items": [
      {
        "nav": "chat",
        "text": "聊天",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          112,
          62,
          129
        ]
      },
      {
        "nav": "todos",
        "text": "待办",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          150,
          62,
          167
        ]
      },
      {
        "nav": "notes",
        "text": "笔记",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          188,
          62,
          205
        ]
      },
      {
        "nav": "clipboard",
        "text": "剪贴板",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          32,
          226,
          68,
          243
        ]
      },
      {
        "nav": "sticky",
        "text": "便签",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          264,
          62,
          281
        ]
      },
      {
        "nav": "countdown",
        "text": "倒计时",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          32,
          302,
          68,
          319
        ]
      },
      {
        "nav": "launch",
        "text": "启动",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          340,
          62,
          357
        ]
      },
      {
        "nav": "search",
        "text": "搜索",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          378,
          62,
          395
        ]
      },
      {
        "nav": "settings",
        "text": "设置",
        "ico": null,
        "overflowX": 0,
        "covered": false,
        "visible": true,
        "rect": [
          38,
          431,
          62,
          448
        ]
      }
    ]
  },
  "notes_open": true
}
```

### C_collapse_chat_keeps_hud（通过）

```json
{
  "ok": true,
  "opened": true,
  "has_btn": true,
  "btn_text": "▴ 收起对话",
  "peer_row": "[\"新会话\",\"对话\"]",
  "click_collapse": {
    "ok": true,
    "screen": [
      1768,
      120
    ],
    "sel": "[data-collapse-chat]"
  },
  "before": {
    "mode": "deck",
    "geo": "full",
    "docked": false,
    "panel": "notes",
    "chat": true,
    "deck": true,
    "ignoring": false,
    "pct": 0,
    "notes": {
      "list": true,
      "editor": false,
      "active": null,
      "count": 9
    },
    "viewport": [
      1707,
      1019
    ]
  },
  "after": {
    "mode": "deck",
    "geo": "full",
    "docked": false,
    "panel": "notes",
    "chat": false,
    "deck": true,
    "ignoring": true,
    "pct": 0,
    "notes": {
      "list": true,
      "editor": false,
      "active": null,
      "count": 9
    },
    "viewport": [
      1707,
      1019
    ]
  },
  "chat_dom": false,
  "rail_still": true,
  "panel_still": true,
  "click_toggle": {
    "ok": true,
    "screen": [
      1516,
      48
    ],
    "sel": ".island-toggle"
  },
  "after_toggle": {
    "mode": "idle",
    "geo": "full",
    "docked": false,
    "panel": "notes",
    "chat": false,
    "deck": false,
    "ignoring": false,
    "pct": 0,
    "notes": {
      "list": true,
      "editor": false,
      "active": null,
      "count": 9
    },
    "viewport": [
      1707,
      1019
    ]
  },
  "hud_closed": true
}
```

### D_island_compact_no_overlap（通过）

```json
{
  "ok": true,
  "layout": {
    "island": {
      "x": 673.6666870117188,
      "y": 12,
      "w": 360,
      "h": 40,
      "right": 1033.6666870117188,
      "bottom": 52,
      "text": "shell-hub 点击打开对话 0% ⌗ ◉ ⚙ ▴"
    },
    "parts": {
      "brand": {
        "x": 701.6666870117188,
        "y": 22.104167938232422,
        "w": 152.15625,
        "h": 19.791667938232422,
        "right": 853.8229370117188,
        "bottom": 41.895835876464844,
        "text": "shell-hub 点击打开对话"
      },
      "cue": {
        "x": 701.6666870117188,
        "y": 34.19791793823242,
        "w": 152.15625,
        "h": 7.6979169845581055,
        "right": 853.8229370117188,
        "bottom": 41.89583492279053,
        "text": "点击打开对话"
      },
      "pct": {
        "x": 861.8229370117188,
        "y": 24,
        "w": 14.84375,
        "h": 16,
        "right": 876.6666870117188,
        "bottom": 40,
        "text": "0%"
      },
      "decay": {
        "x": 861.8229370117188,
        "y": 21,
        "w": 41.84375,
        "h": 22,
        "right": 903.6666870117188,
        "bottom": 43,
        "text": "0%"
      },
      "toggle": {
        "x": 997.6666870117188,
        "y": 19,
        "w": 26,
        "h": 26,
        "right": 1023.6666870117188,
        "bottom": 45,
        "text": "▴"
      }
    },
    "overlaps": {
      "pct_brand": false,
      "pct_toggle": false,
      "brand_toggle": false,
      "decay_toggle": false
    },
    "clips": {
      "pct": false,
      "brand": false,
      "toggle": false,
      "cue": false
    },
    "chatOpen": false
  },
  "no_overlap": true,
  "no_clip": true,
  "cue": {
    "x": 701.6666870117188,
    "y": 34.19791793823242,
    "w": 152.15625,
    "h": 7.6979169845581055,
    "right": 853.8229370117188,
    "bottom": 41.89583492279053,
    "text": "点击打开对话"
  },
  "reopen": true
}
```

### E_coexist（通过）

```json
{
  "ok": true,
  "both1": true,
  "coexist": {
    "rail": {
      "sel": ".rail",
      "w": 72,
      "h": 875,
      "x": 14,
      "y": 64,
      "right": 86,
      "bottom": 939,
      "vis": "visible",
      "disp": "flex",
      "opacity": "1"
    },
    "panel": {
      "sel": ".hud.is-open .panel-col",
      "w": 820,
      "h": 875,
      "x": 94,
      "y": 64,
      "right": 914,
      "bottom": 939,
      "vis": "visible",
      "disp": "flex",
      "opacity": "1"
    },
    "cabin": {
      "sel": ".island-chat",
      "w": 302,
      "h": 476,
      "x": 930,
      "y": 56,
      "right": 1232,
      "bottom": 532,
      "vis": "visible",
      "disp": "flex",
      "opacity": "1"
    },
    "collapse": {
      "sel": "[data-collapse-chat]",
      "w": 82,
      "h": 28,
      "x": 1138,
      "y": 66,
      "right": 1220,
      "bottom": 94,
      "vis": "visible",
      "disp": "flex",
      "opacity": "1"
    },
    "composer": {
      "sel": ".composer textarea",
      "w": 224,
      "h": 54,
      "x": 942,
      "y": 466,
      "right": 1166,
      "bottom": 520,
      "vis": "visible",
      "disp": "block",
      "opacity": "1"
    },
    "list": {
      "sel": ".tv-scroll",
      "w": 295,
      "h": 691,
      "x": 107,
      "y": 215,
      "right": 402,
      "bottom": 907,
      "vis": "visible",
      "disp": "block",
      "opacity": "1"
    },
    "overlaps": {
      "cabin_rail": false,
      "cabin_composer_panel": false,
      "collapse_panel": false,
      "cabin_list": false
    }
  },
  "typed": true,
  "send_enabled": true,
  "sent": true,
  "chat_stayed_clip": true,
  "chat_stayed_launch": true,
  "chat_stayed_search": true,
  "search_focus": true,
  "panel_after_collapse": true,
  "chat_after_hud_close": true,
  "ign_both": {
    "css": [
      1280.3541870117188,
      580
    ],
    "screen": [
      1920,
      870
    ],
    "ignoring": true,
    "on": "DIV."
  },
  "ign_idle": {
    "css": [
      1081.6666870117188,
      560.45
    ],
    "screen": [
      1622,
      841
    ],
    "ignoring": true,
    "on": "DIV."
  },
  "clicks": {
    "todo": {
      "ok": true,
      "screen": [
        75,
        237
      ],
      "sel": "[data-nav=\"todos\"]"
    },
    "clip": {
      "ok": true,
      "screen": [
        75,
        351
      ],
      "sel": "[data-nav=\"clipboard\"]"
    },
    "launch": {
      "ok": true,
      "screen": [
        75,
        522
      ],
      "sel": "[data-nav=\"launch\"]"
    },
    "search": {
      "ok": true,
      "screen": [
        75,
        579
      ],
      "sel": "[data-nav=\"search\"]"
    }
  }
}
```

### F_todo_depth（通过）

```json
{
  "ok": true,
  "create_parent": {
    "click_new": {
      "ok": true,
      "screen": [
        532,
        186
      ],
      "sel": ".tv-primary"
    },
    "title": "【P1-2】子待办父项",
    "exists": true
  },
  "sub": {
    "added": true,
    "checked": true,
    "parent_done_before": false,
    "parent_done_after": false,
    "sub_kept_while_parent_open": true
  },
  "daily": {
    "title": "【P1-2】每日周期",
    "set_ok": true,
    "due_ok": true,
    "mode_ok": true,
    "can_save": true,
    "shown": true,
    "invalid": "",
    "title_now": "【P1-2】每日周期",
    "extra": null
  },
  "weekly": {
    "title": "【P1-2】每周周期",
    "set_ok": true,
    "due_ok": true,
    "mode_ok": true,
    "can_save": true,
    "shown": true,
    "invalid": "",
    "title_now": "【P1-2】每周周期",
    "extra": null
  },
  "rolled": {
    "ok": true,
    "before": {
      "id": 12,
      "title": "【P1-2】每日周期",
      "done": false,
      "priority": 0,
      "created_at": "2026-11-12 10:31:22.923978",
      "updated_at": "2026-11-12 10:31:22.986668",
      "completed_at": null,
      "due_at": 1794499140000,
      "remind_at": null,
      "remind_fired": false,
      "remind_notify_mode": "",
      "parent_id": null,
      "sort_order": null,
      "version": 4,
      "description": "",
      "pinned": false,
      "repeat_mode": "daily",
      "repeat_every": null,
      "repeat_unit": null,
      "repeat_weekdays": null,
      "repeat_month_day": null,
      "repeat_month_nth": null,
      "repeat_end_mode": null,
      "repeat_end_at": null,
      "repeat_count": null,
      "repeat_done_count": 0,
      "repeat_last_done_at": null
    },
    "after": {
      "id": 12,
      "title": "【P1-2】每日周期",
      "done": false,
      "priority": 0,
      "created_at": "2026-11-12 10:31:22.923978",
      "updated_at": "2026-11-12 10:31:38.262667",
      "completed_at": null,
      "due_at": 1794585540000,
      "remind_at": null,
      "remind_fired": false,
      "remind_notify_mode": "",
      "parent_id": null,
      "sort_order": null,
      "version": 5,
      "description": "",
      "pinned": false,
      "repeat_mode": "daily",
      "repeat_every": null,
      "repeat_unit": null,
      "repeat_weekdays": null,
      "repeat_month_day": null,
      "repeat_month_nth": null,
      "repeat_end_mode": null,
      "repeat_end_at": null,
      "repeat_count": null,
      "repeat_done_count": 1,
      "repeat_last_done_at": "2026-11-12 10:31:38.262667"
    }
  },
  "calendar": {
    "info": {
      "cellCount": 42,
      "markedCount": 26,
      "marked": [
        {
          "day": "2026-11-06",
          "chips": [
            "头盔验收待办-改名",
            "头盔验收待办-改名"
          ]
        },
        {
          "day": "2026-11-12",
          "chips": [
            "【P1-2】每周周期"
          ]
        },
        {
          "day": "2026-11-13",
          "chips": [
            "【P1-2】每日周期"
          ]
        },
        {
          "day": "2026-11-14",
          "chips": [
            "【P1-2】每日周期"
          ]
        },
        {
          "day": "2026-11-15",
          "chips": [
            "【P1-2】每日周期"
          ]
        },
        {
          "day": "2026-11-16",
          "chips": [
            "【P1-2】每日周期"
          ]
        },
        {
          "day": "2026-11-17",
          "chips": [
            "【P1-2】每日周期"
          ]
        },
        {
          "day": "2026-11-18",
          "chips": [
            "【P1-2】每日周期"
          ]
        },
        {
          "day": "2026-11-19",
          "chips": [
            "【P1-2】每周周期",
            "【P1-2】每日周期"
          ]
        },
        {
          "day": "2026-11-20",
          "chips": [
            "【P1-2】每日周期"
          ]
        }
      ]
    },
    "clicked": true,
    "day_list": {
      "items": [
        "未完成\n1",
        "【P1-2】每周周期\n23:59",
        "【P1-2】每周周期",
        "23:59"
      ],
      "seedsVisible": [
        "【P1-2】每周周期",
        "【P1-2】每日周期",
        "【P1-2】子待办父项",
        "【P1-2】子项",
        "【P1-2】每周周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每周周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每周周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每周周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每日周期",
        "【P1-2】每周周期\n23:59"
      ]
    },
    "sel": ".tv-cell[data-day='2026-11-12']"
  },
  "cleaned": [
    {
      "id": 11,
      "title": "【P1-2】子项"
    },
    {
      "id": 13,
      "title": "【P1-2】每周周期"
    },
    {
      "id": 12,
      "title": "【P1-2】每日周期"
    },
    {
      "id": 10,
      "title": "【P1-2】子待办父项"
    }
  ]
}
```

## 编译与进程

- 编译次数：1（`npx tauri build --debug --no-bundle --config .smoke/tauri.smoke.json`，随后 rcedit `.smoke/app.manifest`）
- 安装包：未出
- push：未 push
- 原版进程：{"before": [{"ProcessId": 12168, "ExecutablePath": "C:\\Users\\wcy\\Downloads\\x-hub-0.7.2-win-x64\\x-hub.exe"}, {"ProcessId": 14612, "ExecutablePath": "C:\\Users\\wcy\\projects\\XXXX\\src-tauri\\target\\debug\\x-hub.exe"}], "after": [{"ProcessId": 12168, "ExecutablePath": "C:\\Users\\wcy\\Downloads\\x-hub-0.7.2-win-x64\\x-hub.exe"}, {"ProcessId": 14612, "ExecutablePath": "C:\\Users\\wcy\\projects\\XXXX\\src-tauri\\target\\debug\\x-hub.exe"}], "path": "C:\\Users\\wcy\\Downloads\\x-hub-0.7.2-win-x64\\x-hub.exe", "pid_before": 12168, "pid_after": 12168, "untouched": true}
