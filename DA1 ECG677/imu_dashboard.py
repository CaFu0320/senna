#!/usr/bin/env python3
"""Live STM32 / LIS2MDL serial dashboard. Python 3.10+.

Windows setup (Command Prompt, in this file's folder):
    py -m pip install pyserial matplotlib
    py imu_dashboard.py
Other systems: use python3 instead of py. Linux may need python3-tk.

Close CubeIDE's serial terminal before connecting. Select the board's COM port,
leave baud at 115200 (or match your firmware), then Connect. Press the board's
RESET button if needed. Demo runs without hardware; Stop ends either source.
Record CSV saves subsequent accepted rows until Stop recording / Stop / exit.

Supported comma-separated rows, automatically detected by column count:
  12: ax,ay,az,gx,gy,gz,mx,my,mz,roll,pitch,yaw  [your message(7).txt]
   9: ax,ay,az,gx,gy,gz,mx,my,mz
   7: t_ms,mx_raw,my_raw,mz_raw,mx_uT,my_uT,mz_uT [LIS2MDL test]
  14: seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz,mag_new,mag_valid,mag_age_us
  16: same as 12, followed by qw,qx,qy,qz (optional future firmware)
Accel: m/s^2. Gyro: degrees/s. Mag: microtesla. Euler: degrees.
Lines beginning # and known CSV headers are ignored. Blank/absent channels
are NaN, not zero. No calibration, filtering, or orientation estimation is
performed here: all values are displayed as transmitted by the firmware.

Plots use PC reception time, NOT precise sensor sampling time. Device times
are preserved in recordings when supplied; their wrap/reset is not modified.
Received rows/s is serial throughput, not the IMU's configured ODR. Plotting
runs at about 10 frames/s independently of serial acquisition. A bounded queue
reports PC queue drops; USB/firmware losses cannot be detected without sequence
numbers. Recordings include source (SERIAL or DEMO); demo data are synthetic.
"""

import csv
import math
import queue
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


CHANNELS = ('ax', 'ay', 'az', 'gx', 'gy', 'gz', 'mx', 'my', 'mz',
            'roll', 'pitch', 'yaw', 'qw', 'qx', 'qy', 'qz')
META = ('seq', 't_us', 't_ms', 'mx_raw', 'my_raw', 'mz_raw',
        'mag_new', 'mag_valid', 'mag_age_us')
CSV_FIELDS = ('source', 'pc_elapsed_s') + CHANNELS + META
COLORS = ('#2563eb', '#e85d2a', '#119477')
GROUPS = (('Acceleration', 'm/s²', CHANNELS[0:3]),
          ('Angular velocity', '°/s', CHANNELS[3:6]),
          ('Magnetic field', 'µT', CHANNELS[6:9]),
          ('Orientation from firmware', '°', CHANNELS[9:12]))


def parse_line(line):
    """Return a named sample, None for headers/comments; raise for bad data."""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    parts = [p.strip() for p in line.split(',')]
    if parts[0].lower() in ('seq', 't_ms', 't_us', 'ax', 'ax_ms2'):
        return None
    values = [float(p) for p in parts]
    n = len(values)
    if n in (9, 12, 16):
        result = dict(zip(CHANNELS[:n], values))
    elif n == 7:
        result = dict(zip(('t_ms', 'mx_raw', 'my_raw', 'mz_raw',
                           'mx', 'my', 'mz'), values))
    elif n == 14:
        result = dict(zip(('seq', 't_us') + CHANNELS[:9] +
                          ('mag_new', 'mag_valid', 'mag_age_us'), values))
        if result['mag_valid'] not in (0, 1):
            raise ValueError('Invalid magnetometer validity flag')
        if not result['mag_valid']:
            result.update(mx=math.nan, my=math.nan, mz=math.nan)
    else:
        raise ValueError(f'Unsupported column count: {n}')
    if any(math.isinf(v) for v in values):
        raise ValueError('Infinite value')
    if not any(math.isfinite(result.get(k, math.nan)) for k in CHANNELS):
        raise ValueError('No finite sensor values')
    return result


class LineFramer:
    """Preserve partial serial lines across read timeouts; bound line size."""
    def __init__(self):
        self.buffer = bytearray()
        self.discard = False

    def feed(self, data):
        for byte in data:
            if byte == 10:
                if not self.discard:
                    yield self.buffer.decode('ascii', errors='replace')
                self.buffer.clear()
                self.discard = False
            elif not self.discard:
                self.buffer.append(byte)
                if len(self.buffer) > 4096:
                    self.buffer.clear()
                    self.discard = True
                    yield 'oversized serial line'


def make_figure():
    fig = Figure(figsize=(11, 6.5), dpi=100, facecolor='#f5f7fb')
    axes = fig.subplots(2, 2).ravel()
    lines, labels = [], []
    for ax, (title, unit, keys) in zip(axes, GROUPS):
        ax.set_title(title, loc='left', fontsize=11, fontweight='bold', pad=30)
        ax.set_ylabel(unit)
        ax.set_xlabel('PC reception time (s)')
        ax.grid(True, alpha=0.18)
        ax.set_xlim(0, 15)
        group = [ax.plot([], [], color=c, linewidth=1.3, label=k)[0]
                 for c, k in zip(COLORS, keys)]
        ax.legend(loc='upper right', ncol=3, fontsize=8)
        labels.append(ax.text(0, 1.04, 'Waiting for data', transform=ax.transAxes,
                              fontsize=9, color='#526077'))
        lines.append(group)
    fig.subplots_adjust(left=.08, right=.98, bottom=.10, top=.87,
                        wspace=.24, hspace=.65)
    return fig, axes, lines, labels


class Dashboard:
    def __init__(self, root):
        self.root = root
        root.title('Design Assignment 1 — STM32 Sensor Dashboard')
        root.geometry('1200x850')
        root.minsize(950, 700)
        self.events = queue.Queue(maxsize=5000)
        self.stop_event = threading.Event()
        self.worker = None
        self.record_file = None
        self.writer = None
        self.rows = self.bad = self.drops = 0
        self.source = 'SERIAL'
        self.start_time = time.perf_counter()
        self.times = deque(maxlen=5000)
        self.data = {k: deque(maxlen=5000) for k in CHANNELS}
        self.rate_times = deque(maxlen=5000)
        self.latest = {}
        self.dirty = False
        self.last_flush = 0

        bar = ttk.Frame(root, padding=10)
        bar.pack(fill='x')
        ttk.Label(bar, text='Port').pack(side='left')
        self.port = ttk.Combobox(bar, width=16)
        self.port.pack(side='left', padx=6)
        ttk.Button(bar, text='Refresh', command=self.refresh_ports).pack(side='left')
        ttk.Label(bar, text='  Baud').pack(side='left')
        self.baud = ttk.Combobox(bar, width=9, values=('115200', '230400', '460800', '921600'))
        self.baud.set('115200')
        self.baud.pack(side='left', padx=6)
        self.connect_button = ttk.Button(bar, text='Connect', command=self.connect)
        self.connect_button.pack(side='left', padx=4)
        self.demo_button = ttk.Button(bar, text='Demo', command=lambda: self.start(True))
        self.demo_button.pack(side='left', padx=4)
        ttk.Button(bar, text='Stop', command=self.stop).pack(side='left', padx=4)
        self.record_button = ttk.Button(bar, text='Record CSV', command=self.toggle_record)
        self.record_button.pack(side='right')

        self.status = tk.StringVar(value='Select your board port, or click Demo for synthetic data.')
        self.stats = tk.StringVar(value='No samples received')
        self.record_status = tk.StringVar(value='Not recording')
        ttk.Label(root, textvariable=self.status, padding=(12, 2)).pack(anchor='w')
        ttk.Label(root, textvariable=self.stats, padding=(12, 2)).pack(anchor='w')
        self.fig, self.axes, self.lines, self.labels = make_figure()
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        ttk.Label(root, textvariable=self.record_status, padding=(12, 3)).pack(anchor='w')
        ttk.Label(root, text='15-second view • Values as transmitted • Missing channels stay blank • '
                  'PC reception timing', padding=(12, 6)).pack(anchor='w')
        self.refresh_ports()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.tick)

    def refresh_ports(self):
        try:
            from serial.tools import list_ports
            devices = [p.device for p in list_ports.comports()]
            self.port['values'] = devices
            if devices and not self.port.get():
                self.port.set(devices[0])
        except ImportError:
            self.status.set('Install pyserial to connect. Demo is available without a board.')

    def connect(self):
        try:
            baud = int(self.baud.get())
            if baud <= 0 or not self.port.get().strip():
                raise ValueError
        except ValueError:
            messagebox.showerror('Connection', 'Choose a serial port and a positive baud rate.')
            return
        self.start(False, self.port.get().strip(), baud)

    def start(self, demo=False, port='', baud=115200):
        if self.worker and self.worker.is_alive():
            return
        self.stop()
        self.events = queue.Queue(maxsize=5000)
        self.stop_event = threading.Event()
        self.rows = self.bad = self.drops = 0
        self.times.clear()
        self.rate_times.clear()
        for values in self.data.values():
            values.clear()
        self.latest = {}
        self.dirty = True
        self.source = 'DEMO' if demo else 'SERIAL'
        self.start_time = time.perf_counter()
        self.status.set('DEMO — synthetic values' if demo else f'Opening {port} at {baud}…')
        self.connect_button.configure(state='disabled')
        self.demo_button.configure(state='disabled')
        self.worker = threading.Thread(target=self.read_source, args=(demo, port, baud), daemon=True)
        self.worker.start()

    def enqueue(self, kind, payload):
        try:
            self.events.put_nowait((kind, time.perf_counter(), payload))
        except queue.Full:
            self.drops += 1

    def read_source(self, demo, port, baud):
        try:
            if demo:
                while not self.stop_event.is_set():
                    t = time.perf_counter() - self.start_time
                    s, c = math.sin(t), math.cos(t)
                    values = (s, .5*c, 9.81+.2*s, 8*c, 4*s, 12*c,
                              22+2*s, -15+c, -28+2*c, 8*s, 4*c, 30*s)
                    self.enqueue('line', ','.join(f'{v:.4f}' for v in values))
                    self.stop_event.wait(.01)
            else:
                import serial
                with serial.Serial(port, baudrate=baud, timeout=.1,
                                   bytesize=8, parity='N', stopbits=1) as connection:
                    self.enqueue('status', f'Connected: {port}, {baud} baud, 8N1 — waiting for CSV')
                    framer = LineFramer()
                    while not self.stop_event.is_set():
                        chunk = connection.read(min(4096, max(1, connection.in_waiting)))
                        for line in framer.feed(chunk):
                            self.enqueue('line', line)
        except Exception as error:
            self.enqueue('error', f'{type(error).__name__}: {error}')

    def stop_recording(self):
        if self.record_file:
            try:
                self.record_file.close()
            except OSError as error:
                messagebox.showerror('Recording error', str(error))
        self.record_file = self.writer = None
        self.record_button.configure(text='Record CSV')

    def toggle_record(self):
        if self.record_file:
            self.stop_recording()
            self.record_status.set('Recording stopped')
            return
        if not self.worker or not self.worker.is_alive():
            messagebox.showinfo('Record', 'Connect to the board or start Demo first.')
            return
        filename = filedialog.asksaveasfilename(
            defaultextension='.csv', filetypes=[('CSV', '*.csv')],
            initialfile=f'{self.source.lower()}_{datetime.now():%Y%m%d_%H%M%S}.csv')
        if not filename:
            return
        try:
            self.record_file = open(filename, 'w', newline='', encoding='utf-8')
            self.writer = csv.DictWriter(self.record_file, fieldnames=CSV_FIELDS)
            self.writer.writeheader()
            self.record_button.configure(text='Stop recording')
            self.record_status.set(f'Recording {self.source}: {Path(filename).name}')
        except OSError as error:
            self.stop_recording()
            messagebox.showerror('Recording error', str(error))

    def stop(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=.5)
        self.stop_recording()
        self.record_status.set('Not recording')
        self.status.set('Stopped')
        # Keep controls disabled if an OS serial-open call is still returning.
        if not self.worker or not self.worker.is_alive():
            self.connect_button.configure(state='normal')
            self.demo_button.configure(state='normal')

    def tick(self):
        for _ in range(5000):
            try:
                kind, received, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind in ('status', 'error'):
                self.status.set(payload)
                continue
            try:
                sample = parse_line(payload)
            except ValueError:
                self.bad += 1
                continue
            if sample is None:
                continue
            t = received - self.start_time
            self.times.append(t)
            self.rate_times.append(received)
            self.rows += 1
            self.latest = sample
            for key in CHANNELS:
                self.data[key].append(sample.get(key, math.nan))
            self.dirty = True
            if self.writer:
                try:
                    self.writer.writerow(dict(source=self.source, pc_elapsed_s=f'{t:.6f}', **sample))
                except OSError as error:
                    self.stop_recording()
                    self.record_status.set(f'Recording failed: {error}')
        now = time.perf_counter()
        while self.rate_times and self.rate_times[0] < now - 2:
            self.rate_times.popleft()
        duration = min(2.0, max(.1, now - self.start_time))
        rate = len(self.rate_times) / duration
        self.stats.set(f'{self.source} | Rows: {self.rows:,} | Received: {rate:.1f} rows/s | '
                       f'Invalid lines: {self.bad} | PC queue drops: {self.drops}')
        if self.record_file and now - self.last_flush >= 1:
            try:
                self.record_file.flush()
                self.last_flush = now
            except OSError as error:
                self.stop_recording()
                self.record_status.set(f'Recording failed: {error}')
        if self.dirty:
            self.draw()
            self.dirty = False
        if self.worker and not self.worker.is_alive():
            self.worker = None
            self.stop_recording()
            self.record_status.set('Not recording — source stopped')
            self.connect_button.configure(state='normal')
            self.demo_button.configure(state='normal')
        self.root.after(100, self.tick)

    def draw(self):
        end = self.times[-1] if self.times else 0
        left, right = max(0, end - 15), max(15, end)
        while self.times and self.times[0] < left:
            self.times.popleft()
            for values in self.data.values():
                values.popleft()
        for ax, group, label, (_, _, keys) in zip(self.axes, self.lines, self.labels, GROUPS):
            finite = []
            for line, key in zip(group, keys):
                values = self.data[key]
                line.set_data(list(self.times), list(values))
                finite.extend(v for v in values if math.isfinite(v))
            ax.set_xlim(left, right)
            if finite:
                low, high = min(finite), max(finite)
                margin = max(.1, (high - low) * .12)
                ax.set_ylim(low - margin, high + margin)
            label.set_text('   '.join(f'{k}: {self.latest[k]:.2f}' if
                           math.isfinite(self.latest.get(k, math.nan)) else f'{k}: —'
                           for k in keys))
        self.canvas.draw_idle()

    def close(self):
        self.stop()
        self.root.destroy()


if __name__ == '__main__':
    Dashboard(tk.Tk()).root.mainloop()
