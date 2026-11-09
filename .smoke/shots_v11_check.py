"""真屏截图：HUD 是透明覆盖层，CDP 抓图背景是透明（blend 模式会假白），
验收图必须用系统截屏才能看到「桌面穿透 + 光效」的真实叠加结果。"""
import json
import sys
import time

import ctypes.wintypes as w
from PIL import ImageGrab

sys.path.insert(0, '.smoke')
import verify_v10 as V
import verify_v11 as V11

V.wait_ready()


def grab(name):
    img = ImageGrab.grab(all_screens=True)
    p = V.HERE + '\\' + name
    img.save(p, 'PNG')
    return {'path': p, 'size': img.size}


pid = V.pid_of()
# 1) 收起态岛
V11.wait_idle_band()
print('idle', V.state()['mode'], V.state()['docked'])
print(grab('shot_check_01_island.png'))

# 2) 对话舱
V11.click_css('.island-brand', settle=1.8)
print('chat', V.state()['mode'])
print(grab('shot_check_02_chat.png'))
V.key_escape()
time.sleep(1.6)

# 3) HUD + 笔记三栏
if V.state()['mode'] != 'deck':
    V11.click_css('.island-toggle', settle=1.8)
for _ in range(3):
    if V.state()['notes']['list']:
        break
    V11.click_css('[data-nav="notes"]', settle=1.5)
for _ in range(3):
    if V.state()['notes']['editor']:
        break
    V11.click_css('.note-row', settle=1.6)
print('notes', json.dumps(V.state()['notes']))
print(grab('shot_check_03_notes.png'))

# 4) 光效峰值（同一条 CSS 动画暂停 60ms）
info, _ = V11.freeze_peak_shot('shot_check_04_peak_cdp.png')
time.sleep(0.2)
print('peak', info)
print(grab('shot_check_05_peak_screen.png'))
print('state', V.state()['mode'], 'ignoring', V.state()['ignoring'])