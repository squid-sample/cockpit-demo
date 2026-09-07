# -*- coding: utf-8 -*-
"""
Windows 桌面圆形悬浮下班倒计时 + 会议定时提醒
- 每天 18:00 下班，单击圆圈开始/重新计时，双击暂停恢复 --:--:--
- 右键菜单可添加会议提醒（HH:MM + 名称），到点弹置顶通知 + 响铃
- 提醒列表持久化到同目录 reminders.json，重启不丢
- 按住拖动移动窗口；右键菜单退出
运行: python off_work_countdown.py  （或双击桌面"下班倒计时.bat"）
"""
import tkinter as tk
import json
import math
import os
import random
import sys
import threading
import time
import winsound
import traceback
from datetime import datetime

OFF_HOUR, OFF_MIN = 18, 0                       # 下班时间 18:00

SIZE    = 56                                    # 窗口边长
CIRCLE  = 48                                    # 圆直径
BG      = '#181825'                             # 圆内底色
ACCENT  = '#a6e3a1'                             # 倒计时数字（绿）
ACCENT_HI = '#00ff00'                           # 悬停时纯绿描边
WARN    = '#f38ba8'                             # 提醒色（红）
DIM     = '#9399b2'                             # 未开始的灰
FG      = '#cdd6f4'                             # 主文字
TRANS   = '#010101'                             # 透明色（勿与其他颜色重复）

ALPHA_NORMAL = 0.35                            # 平时半透明
ALPHA_HOVER  = 1.0                             # 鼠标悬停时不透明

DRAG_TOLERANCE = 4                              # 移动超过该像素算拖动，否则算点击

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'reminders.json')


LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'error.log')


def _log_exception(exc, val, tb):
    """Tk 回调异常统一记录：stderr + error.log（pythonw 下也能排查）"""
    traceback.print_exception(exc, val, tb, file=sys.stderr)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f'\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n')
            traceback.print_exception(exc, val, tb, file=f)
    except OSError:
        pass


def play_alarm(duration=15):
    """播放闹铃：低频柔和铃声，连续不中断，持续 duration 秒
    用 250Hz 低音 + 短间隔连续 Beep 模拟柔和钟声
    在独立线程运行，不阻塞 Tk 主循环"""
    def _run():
        end = time.monotonic() + duration
        while time.monotonic() < end:
            winsound.Beep(250, 400)     # 低频柔和音，400ms 连续
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def make_aa_circle_points(cx, cy, r, segments=None):
    """生成抗锯齿圆的高密度点序列：每像素周长至少 1 个顶点
    返回 [(x0,y0), (x1,y1), ...]，供 Canvas.create_polygon 使用"""
    if segments is None:
        segments = max(64, int(2 * math.pi * r * 3.0))   # 周长 3 倍密度更柔和
    pts = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        pts.append(cx + r * math.cos(a))
        pts.append(cy + r * math.sin(a))
    return pts


class ReminderDialog(tk.Toplevel):
    """添加提醒对话框：名称 + 时间(HH:MM)"""
    def __init__(self, app: 'CountdownApp'):
        super().__init__(app.root)
        self.app = app
        self.title('添加提醒')
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.grab_set()                         # 模态

        frm = tk.Frame(self, bg=BG, padx=14, pady=12)
        frm.pack()

        tk.Label(frm, text='事项名称', bg=BG, fg=DIM,
                 font=('Microsoft YaHei UI', 9)).grid(row=0, column=0,
                                                      sticky='w', pady=3)
        self.name_var = tk.StringVar(value='会议')
        self.name_entry = tk.Entry(
            frm, textvariable=self.name_var, width=22,
            bg='#313244', fg=FG, relief='flat',
            insertbackground=FG,
            font=('Microsoft YaHei UI', 10))
        self.name_entry.grid(row=0, column=1, pady=3, padx=(8, 0))

        tk.Label(frm, text='提醒时间', bg=BG, fg=DIM,
                 font=('Microsoft YaHei UI', 9)).grid(row=1, column=0,
                                                      sticky='w', pady=3)
        tf = tk.Frame(frm, bg=BG)
        tf.grid(row=1, column=1, sticky='w', pady=3, padx=(8, 0))
        self.h_var = tk.StringVar(value=f'{datetime.now().hour:02d}')
        self.m_var = tk.StringVar(value=f'{datetime.now().minute + 1:02d}')
        for var, hi in ((self.h_var, 23), (self.m_var, 59)):
            sp = tk.Spinbox(tf, from_=0, to=hi, width=4, wrap=True,
                            textvariable=var, format='%02.0f',
                            bg='#313244', fg=FG, relief='flat',
                            buttonbackground=BG,
                            justify='center',
                            font=('Consolas', 10))
            sp.pack(side='left')
        tk.Label(tf, text=':', bg=BG, fg=FG,
                 font=('Consolas', 11, 'bold')).pack(side='left')

        bf = tk.Frame(frm, bg=BG)
        bf.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        tk.Button(bf, text='确定', command=self._ok, width=8,
                  bg=ACCENT, fg='#11111b', relief='flat',
                  font=('Microsoft YaHei UI', 9, 'bold'),
                  activebackground='#94e2d5',
                  cursor='hand2').pack(side='left', padx=6)
        tk.Button(bf, text='取消', command=self.destroy, width=8,
                  bg='#45475a', fg=FG, relief='flat',
                  font=('Microsoft YaHei UI', 9),
                  activebackground='#585b70',
                  cursor='hand2').pack(side='left', padx=6)

        self.bind('<Return>', lambda e: self._ok())
        self.bind('<Escape>', lambda e: self.destroy())
        self.name_entry.focus_set()
        self.name_entry.select_range(0, 'end')

    def _ok(self):
        name = self.name_var.get().strip() or '提醒'
        try:
            hh, mm = int(self.h_var.get()), int(self.m_var.get())
        except ValueError:
            return
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return
        self.app.add_reminder(name, hh, mm)
        self.destroy()


class CountdownApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.target = None              # 下班倒计时目标；None = 未开始
        self.reminders = []             # [{'name','hh','mm','fired_date'}]
        self._load_reminders()

        root.overrideredirect(True)     # 无边框
        root.attributes('-topmost', True)
        root.attributes('-alpha', ALPHA_NORMAL)      # 平时半透明
        root.config(bg=TRANS)
        root.attributes('-transparentcolor', TRANS)   # 圆外全透明

        sw = root.winfo_screenwidth()
        root.geometry(f'{SIZE}x{SIZE}+{sw - SIZE - 30}+110')

        self.cv = tk.Canvas(root, width=SIZE, height=SIZE,
                            bg=TRANS, highlightthickness=0)
        self.cv.pack()

        c = SIZE / 2                    # 圆心
        r = CIRCLE / 2
        pts = make_aa_circle_points(c, c, r)
        # 外层抗锯齿圆：用 polygon 逼近，smooth=True 进一步平滑
        self.oval_id = self.cv.create_polygon(
            *pts, fill=BG, outline=ACCENT, width=1,
            smooth=True, joinstyle='round')

        self.time_id = self.cv.create_text(
            c, c, text='--:--:--', fill=DIM,
            font=('Consolas', 7, 'bold'))

        # 鼠标悬停：变不透明 + 更亮的描边/数字
        self.cv.bind('<Enter>', self._on_enter)
        self.cv.bind('<Leave>', self._on_leave)

        # 左键：按下记录位置；移动=拖动；单击=开始；双击=暂停恢复 -- 模式
        self._click_job = None          # 单击延迟任务（等待可能的双击）
        self._suppress_click = False    # 双击后抑制第二次松开触发单击
        self.cv.bind('<Button-1>', self._press)
        self.cv.bind('<B1-Motion>', self._motion)
        self.cv.bind('<ButtonRelease-1>', self._release)
        self.cv.bind('<Double-Button-1>', self._dbl)

        # 右键菜单
        self.menu = tk.Menu(root, tearoff=0)
        self.cv.bind('<Button-3>', self._popup_menu)

        root.after(200, self.tick)

    # ================= 悬停显眼 =================
    def _on_enter(self, _event=None):
        self.root.attributes('-alpha', ALPHA_HOVER)
        self.cv.itemconfig(self.oval_id, outline=ACCENT_HI, width=1)

    def _on_leave(self, _event=None):
        self.root.attributes('-alpha', ALPHA_NORMAL)
        self.cv.itemconfig(self.oval_id, outline=ACCENT, width=1)

    # ================= 会议提醒 =================
    def _popup_menu(self, event):
        m = self.menu
        m.delete(0, 'end')
        m.add_command(label='＋ 添加提醒…',
                      command=lambda: ReminderDialog(self))
        n = len(self.reminders)
        m.add_command(
            label=f'提醒列表（{n}）', state='disabled') if n else None
        for i, r in enumerate(self.reminders):
            m.add_command(
                label=f'  {r["hh"]:02d}:{r["mm"]:02d} {r["name"]}',
                command=lambda idx=i: self._del_reminder(idx))
        if n:
            m.add_separator()
        m.add_command(label='退出', command=self.root.destroy)
        m.tk_popup(event.x_root, event.y_root)

    def add_reminder(self, name, hh, mm):
        self.reminders.append({'name': name, 'hh': hh, 'mm': mm,
                               'fired_date': ''})
        self._save_reminders()

    def _del_reminder(self, idx):
        del self.reminders[idx]
        self._save_reminders()

    def _load_reminders(self):
        try:
            with open(DATA_FILE, encoding='utf-8') as f:
                self.reminders = json.load(f)
        except (OSError, ValueError):
            self.reminders = []

    def _save_reminders(self):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def _check_reminders(self):
        """每秒检查：到点且今天未触发 → 主窗口抖动 + 响铃（与下班同款效果）"""
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        changed = False
        for r in self.reminders:
            if r['fired_date'] == today:
                continue
            if (now.hour, now.minute) >= (r['hh'], r['mm']) \
               and now.hour * 60 + now.minute < r['hh'] * 60 + r['mm'] + 2:
                r['fired_date'] = today
                changed = True
                self._fire_reminder(r['name'])
        if changed:
            self._save_reminders()

    def _fire_reminder(self, name):
        """到点提醒：主窗口抖动 + 响铃，数字临时换成提醒名，15 秒后恢复"""
        play_alarm(15)
        self._shake(15)
        # 保存当前文本/颜色，临时显示提醒名
        self._saved_text = self.cv.itemcget(self.time_id, 'text')
        self._saved_fill = self.cv.itemcget(self.time_id, 'fill')
        self.cv.itemconfig(self.time_id, text=name[:8], fill=WARN,
                           font=('Microsoft YaHei UI', 7, 'bold'))
        self.root.after(15_000, self._restore_time)

    def _restore_time(self):
        """提醒抖动结束后恢复倒计时显示"""
        font_spec = ('Consolas', 7, 'bold')
        if self.target is not None:
            remain = (self.target - datetime.now()).total_seconds()
            if remain > 0:
                s = int(remain)
                hh, mm, ss = s // 3600, s % 3600 // 60, s % 60
                self.cv.itemconfig(self.time_id,
                                   text=f'{hh:02d}:{mm:02d}:{ss:02d}',
                                   fill=ACCENT, font=font_spec)
                return
        self.cv.itemconfig(self.time_id, text='--:--:--', fill=DIM,
                           font=font_spec)

    # ================= 下班倒计时 =================
    def _start(self):
        self._click_job = None          # 单击延迟任务已执行，清除
        now = datetime.now()
        self.target = now.replace(hour=OFF_HOUR, minute=OFF_MIN,
                                  second=0, microsecond=0)
        if now >= self.target:
            self.target = None
            self.cv.itemconfig(self.time_id, text='00:00:00', fill=WARN)
            return
        self.cv.itemconfig(self.time_id, fill=ACCENT)

    def _dbl(self, _event=None):
        self._suppress_click = True
        if self._click_job:             # 取消排队中的单击
            self.root.after_cancel(self._click_job)
        self._click_job = None
        if self.target is None:
            # 未开始时双击视为开始（避免快速点两下被误判清零，像"点了没反应"）
            self._start()
        else:
            self.target = None
            self.cv.itemconfig(self.time_id, text='--:--:--', fill=DIM)

    def tick(self):
        if self.target is not None:
            remain = (self.target - datetime.now()).total_seconds()
            if remain <= 0:
                self.target = None
                self.cv.itemconfig(self.time_id, text='00:00:00', fill=WARN)
                play_alarm(15)            # 闹铃响 15 秒
                self._shake(15)         # 到点抖动 15 秒
            else:
                s = int(remain)
                hh, mm, ss = s // 3600, s % 3600 // 60, s % 60
                self.cv.itemconfig(self.time_id,
                                   text=f'{hh:02d}:{mm:02d}:{ss:02d}')
        self._check_reminders()
        self.root.after(1000, self.tick)

    def _shake(self, seconds=15, amplitude=5, interval=50):
        """到点窗口抖动：随机偏移 amplitude 像素，持续 seconds 秒后归位"""
        base_x, base_y = self.root.winfo_x(), self.root.winfo_y()
        steps = int(seconds * 1000 / interval)

        def step(remaining=steps):
            if remaining <= 0:
                self.root.geometry(f'+{base_x}+{base_y}')   # 回原位
                return
            dx = random.randint(-amplitude, amplitude)
            dy = random.randint(-amplitude, amplitude)
            self.root.geometry(f'+{base_x + dx}+{base_y + dy}')
            self.root.after(interval, lambda: step(remaining - 1))

        step()

    # ================= 拖动 / 点击判定 =================
    def _press(self, event):
        self._dx = event.x_root - self.root.winfo_x()
        self._dy = event.y_root - self.root.winfo_y()
        self._dragging = False

    def _motion(self, event):
        if abs(event.x_root - self.root.winfo_x() - self._dx) > DRAG_TOLERANCE or \
           abs(event.y_root - self.root.winfo_y() - self._dy) > DRAG_TOLERANCE:
            self._dragging = True
        if self._dragging:
            self.root.geometry(
                f'+{event.x_root - self._dx}+{event.y_root - self._dy}')

    def _release(self, event):
        if self._suppress_click:        # 双击的第二次松开，不触发单击
            self._suppress_click = False
        elif not self._dragging:
            # 延迟 250ms 执行，给双击留出取消窗口
            self._click_job = self.root.after(250, self._start)
        self._dragging = False


if __name__ == '__main__':
    root = tk.Tk()
    root.report_callback_exception = _log_exception
    CountdownApp(root)
    root.mainloop()
