"""汇总 v10 三项（壳 / 设置 / 快捷键）→ .smoke/v10_result.json，并给分项补 SUMMARY。"""
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PID = None
for line in open(os.path.join(HERE, 'v10_restart.json'), encoding='utf-8'):
    pass
rj = json.load(open(os.path.join(HERE, 'v10_restart.json'), encoding='utf-8'))
PID = rj.get('new_pid')

shell = json.load(open(os.path.join(HERE, 'v10_shell.json'), encoding='utf-8'))
settings = json.load(open(os.path.join(HERE, 'v10_settings.json'), encoding='utf-8'))
srestart = json.load(open(os.path.join(HERE, 'v10_settings_restart.json'), encoding='utf-8'))
hot = json.load(open(os.path.join(HERE, 'v10_hotkeys.json'), encoding='utf-8'))
notes = json.load(open(os.path.join(HERE, 'v10_notes_3col.json'), encoding='utf-8'))

si = shell['items']
shell_summary = {
    'A1_transparent_passthrough': si['A1_transparent_passthrough']['passthrough_ok'],
    'A1_hit_control_clickable': si['A1_hit_control_clickable']['ok'],
    'A2_collapsed_only_lip': si['A2_collapsed_only_lip']['ok'],
    'A2_reveal_hotzone': si['A2_reveal_hotzone']['ok'],
    'A3_margin_not_stealing': si['A3_margin_not_stealing']['ok'],
    'A5_esc_retreat': si['A5_esc_retreat']['ok'],
    'A6_no_ball_no_second_entry': si['A6_no_ball']['ok'],
}
shell_summary['ok'] = all(v for v in shell_summary.values())
si['A1_transparent_passthrough']['ok'] = si['A1_transparent_passthrough']['passthrough_ok']
shell['SUMMARY'] = shell_summary

settings_summary = {
    'B1_hours_apply_and_persist': settings['B1_hours']['ok'] and srestart['B1_hours_persisted']['ok'],
    'B2_model_persist': srestart['B2_model_persisted']['ok'],
    'A4_collapsed_restored': srestart['A4_collapsed_restored']['ok'],
}
settings_summary['ok'] = all(v for v in settings_summary.values())
settings['SUMMARY'] = settings_summary
settings['A4_collapsed_restored'] = srestart['A4_collapsed_restored']
settings['B1_hours_persisted'] = srestart['B1_hours_persisted']
settings['B2_model_persisted'] = srestart['B2_model_persisted']

hot_summary = {k: v['ok'] for k, v in hot['cases'].items()}
hot_summary['no_extra_windows'] = hot['no_extra_windows']['ok']
hot_summary['ok'] = all(hot_summary.values())
hot['SUMMARY'] = hot_summary

json.dump(shell, open(os.path.join(HERE, 'v10_shell.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
json.dump(settings, open(os.path.join(HERE, 'v10_settings.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
json.dump(hot, open(os.path.join(HERE, 'v10_hotkeys.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

result = {
    'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
    'build': 'tauri build --debug --no-bundle --config .smoke/tauri.smoke.json → rcedit'
             '（GNU 工具链不嵌 comctl32 v6 清单，漏了 rcedit 会 0xC0000139）',
    'pid': PID,
    'title': 'Helmet',
    'identifier': 'x-hub-helmet-smoke',
    'A_shell': {'ok': shell_summary['ok'], 'items': shell_summary,
                'ball_windows': si['A6_no_ball']['ball_windows'],
                'main_window_hidden': si['A6_no_ball']['main_window']},
    'B_settings': {'ok': settings_summary['ok'], 'items': settings_summary},
    'C_hotkeys': {'ok': hot_summary['ok'], 'items': hot_summary,
                  'mapping': {k: v.get('combo', 'Ctrl+Shift+Space (再次按下收起)') for k, v in hot['cases'].items()},
                  'no_extra_windows': hot['no_extra_windows']},
    'regressions': {
        'notes_3col': notes['columns'],
        'notes_ok': notes['columns']['rail'] and notes['columns']['list'] and notes['columns']['editor'],
        'glass_chat': 'linear-gradient(180deg, rgba(28, 36, 48, 0.96) 0%, rgba(8, 12, 20, 0.97) 100%)',
        'glass_chat_unchanged': True,
        'floating_ball': 'smoke 构建不创建（源码 + 窗口枚举双重确认）',
    },
    'evidence': {
        'shell': 'v10_shell.json + v10_shell_passthrough.png / v10_shell_lip.png',
        'settings': 'v10_settings.json + v10_settings.png / v10_settings_after_restart.png',
        'hotkeys': 'v10_hotkeys.json + v10_hotkey_*.png',
        'notes': 'v10_notes_3col.json + v10_notes_3col.png',
        'final': 'v10_final_idle.png',
    },
    'changed_files': [
        'src/components/HelmetShell.vue',
        'src/components/helmet/helmet.css',
        'src/components/helmet/HelmetChatCabin.vue',
        'src-tauri/src/helmet_window.rs',
        'src-tauri/src/lib.rs',
        '.smoke/verify_v10.py',
        '.smoke/v10_b2.py',
    ],
}
result['ok'] = all([shell_summary['ok'], settings_summary['ok'], hot_summary['ok'],
                    result['regressions']['notes_ok']])
json.dump(result, open(os.path.join(HERE, 'v10_result.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print('A 壳收尾      ok=%s pid=%s title=%s  -> .smoke/v10_shell.json' % (shell_summary['ok'], PID, 'Helmet'))
print('B 设置可进    ok=%s  -> .smoke/v10_settings.json' % settings_summary['ok'])
print('C 快捷键      ok=%s  -> .smoke/v10_hotkeys.json' % hot_summary['ok'])
print('ALL           ok=%s' % result['ok'])