#!/usr/bin/env python3
"""Calculate Task 7 metrics from physical timing measurements. No sample values are assumed.
Example:
python benchmark_calculator.py --ispu-active-us 430 --ispu-clock-mhz 5 --mcu-read-cycles 8400 --mcu-clock-mhz 84 --ispu-active-ma 1.15 --ispu-sleep-ma 0.0
Use data-sheet-justified currents and measured pulse widths; do not call estimates measurements.
"""
import argparse
p=argparse.ArgumentParser()
p.add_argument('--ispu-active-us',type=float,required=True)
p.add_argument('--ispu-clock-mhz',type=float,required=True)
p.add_argument('--mcu-read-cycles',type=float,required=True)
p.add_argument('--mcu-clock-mhz',type=float,required=True)
p.add_argument('--ispu-active-ma',type=float,required=True)
p.add_argument('--ispu-sleep-ma',type=float,required=True)
p.add_argument('--ispu-rate-hz',type=float,default=208.0)
p.add_argument('--sensor-ma',type=float,default=0.595)
p.add_argument('--supply-v',type=float,default=1.8)
a=p.parse_args()
duty=min(1.,max(0.,a.ispu_active_us*a.ispu_rate_hz/1e6))
print(f'ISPU total processing cycles (estimated): {a.ispu_active_us*a.ispu_clock_mhz:.1f}')
print(f'STM32 register-read latency (measured cycles converted to time): {a.mcu_read_cycles/a.mcu_clock_mhz:.3f} us')
print(f'ISPU active duty cycle: {100*duty:.4f}%')
extra=a.ispu_active_ma*duty + a.ispu_sleep_ma*(1-duty)
print(f'Estimated chip current: {a.sensor_ma+extra:.5f} mA')
print(f'Estimated chip power (no STM32): {a.supply_v*(a.sensor_ma+extra):.5f} mW')
