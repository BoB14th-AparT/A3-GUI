#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
안드로이드 디바이스 및 Frida 서버 관리 유틸리티
- Frida 서버 재시작
- 디바이스 상태 모니터링
- 메모리/CPU 정리
- 안정성 체크
"""

import subprocess
import time
import re
from datetime import datetime

class DeviceManager:
    def __init__(self, frida_server_path='/data/local/tmp/frida-server'):
        self.frida_server_path = frida_server_path

    def log(self, level, message):
        """로그 출력"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        prefix = {
            'INFO': '[INFO]',
            'SUCCESS': '[OK]',
            'ERROR': '[ERROR]',
            'WARN': '[WARN]'
        }.get(level, '     ')
        try:
            print(f"[{timestamp}] {prefix} {message}")
        except UnicodeEncodeError:
            # Windows 콘솔 인코딩 문제 회피
            print(f"[{timestamp}] {prefix} {message}".encode('utf-8', errors='replace').decode('utf-8', errors='replace'))

    def adb(self, args, timeout=10):
        """ADB 명령 실행"""
        try:
            result = subprocess.run(
                ['adb'] + args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            self.log('ERROR', f'ADB command timeout: {" ".join(args)}')
            return -1, '', 'Timeout'
        except Exception as e:
            self.log('ERROR', f'ADB command failed: {e}')
            return -1, '', str(e)

    def check_device_connected(self):
        """디바이스 연결 확인"""
        code, out, err = self.adb(['devices'])
        if code != 0:
            return False

        lines = out.strip().split('\n')
        devices = [line for line in lines[1:] if '\tdevice' in line]

        if not devices:
            self.log('ERROR', 'No device connected')
            return False

        self.log('SUCCESS', f'Device connected: {devices[0].split()[0]}')
        return True

    def get_device_temp(self):
        """디바이스 온도 확인 (가능한 경우)"""
        code, out, err = self.adb(['shell', 'cat', '/sys/class/thermal/thermal_zone0/temp'])
        if code == 0 and out.strip().isdigit():
            temp = int(out.strip()) / 1000.0  # milli-celsius to celsius
            return temp
        return None

    def get_memory_info(self):
        """메모리 사용량 확인"""
        code, out, err = self.adb(['shell', 'cat', '/proc/meminfo'])
        if code != 0:
            return None

        mem_total = None
        mem_available = None

        for line in out.split('\n'):
            if line.startswith('MemTotal:'):
                mem_total = int(line.split()[1])  # kB
            elif line.startswith('MemAvailable:'):
                mem_available = int(line.split()[1])  # kB

        if mem_total and mem_available:
            used_pct = ((mem_total - mem_available) / mem_total) * 100
            return {
                'total_mb': mem_total // 1024,
                'available_mb': mem_available // 1024,
                'used_percent': round(used_pct, 1)
            }

        return None

    def is_frida_running(self):
        """Frida 서버 실행 확인"""
        code, out, err = self.adb(['shell', 'su', '-c', 'ps | grep frida-server'])

        # grep이 매칭을 못 찾으면 code=1 반환 (정상)
        if code == 0 and 'frida-server' in out and 'grep' not in out:
            self.log('INFO', 'Frida server is running')
            return True
        else:
            self.log('WARN', 'Frida server is NOT running')
            return False

    def stop_frida_server(self):
        """Frida 서버 중지"""
        self.log('INFO', 'Stopping Frida server...')

        # pkill로 종료 시도
        code, out, err = self.adb(['shell', 'su', '-c', 'pkill frida-server'], timeout=5)
        time.sleep(1)

        # 확인
        if not self.is_frida_running():
            self.log('SUCCESS', 'Frida server stopped')
            return True
        else:
            # killall로 재시도
            self.log('WARN', 'pkill failed, trying killall...')
            code, out, err = self.adb(['shell', 'su', '-c', 'killall frida-server'], timeout=5)
            time.sleep(1)

            if not self.is_frida_running():
                self.log('SUCCESS', 'Frida server stopped (via killall)')
                return True
            else:
                self.log('ERROR', 'Failed to stop Frida server')
                return False

    def start_frida_server(self):
        """Frida 서버 시작"""
        self.log('INFO', f'Starting Frida server: {self.frida_server_path}')

        # 백그라운드로 실행 (&)
        code, out, err = self.adb(
            ['shell', 'su', '-c', f'"{self.frida_server_path} &"'],
            timeout=5
        )

        # 시작 대기
        time.sleep(2)

        # 확인
        if self.is_frida_running():
            self.log('SUCCESS', 'Frida server started')
            return True
        else:
            self.log('ERROR', 'Failed to start Frida server')
            self.log('ERROR', f'stdout: {out}')
            self.log('ERROR', f'stderr: {err}')
            return False

    def restart_frida_server(self):
        """Frida 서버 재시작"""
        self.log('INFO', '========== Restarting Frida Server ==========')

        # 1. 중지
        self.stop_frida_server()
        time.sleep(1)

        # 2. 시작
        success = self.start_frida_server()

        if success:
            self.log('SUCCESS', 'Frida server restarted successfully')
        else:
            self.log('ERROR', 'Frida server restart failed')

        return success

    def clear_cache(self):
        """시스템 캐시 정리"""
        self.log('INFO', 'Clearing system cache...')

        # Drop caches (requires root)
        code, out, err = self.adb(['shell', 'su', '-c', 'sync'])
        time.sleep(0.5)
        code, out, err = self.adb(['shell', 'su', '-c', 'echo 3 > /proc/sys/vm/drop_caches'])

        if code == 0:
            self.log('SUCCESS', 'Cache cleared')
            return True
        else:
            self.log('WARN', 'Failed to clear cache (may need root)')
            return False

    def force_stop_all_apps(self, exclude_packages=None):
        """모든 앱 강제 종료 (시스템 앱 제외)"""
        self.log('INFO', 'Force stopping all user apps...')

        exclude_packages = exclude_packages or []
        exclude_packages.extend([
            'com.android.systemui',
            'com.android.launcher',
            'com.google.android.gms'
        ])

        # 실행 중인 프로세스 목록
        code, out, err = self.adb(['shell', 'pm', 'list', 'packages', '-3'])  # -3 = 3rd party only

        if code != 0:
            self.log('WARN', 'Failed to list packages')
            return False

        packages = [line.replace('package:', '') for line in out.strip().split('\n')]
        stopped = 0

        for pkg in packages:
            if pkg and pkg not in exclude_packages:
                code, _, _ = self.adb(['shell', 'am', 'force-stop', pkg], timeout=2)
                if code == 0:
                    stopped += 1

        self.log('SUCCESS', f'Stopped {stopped} apps')
        return True

    def device_cooldown(self, duration=30):
        """디바이스 쿨다운 대기"""
        self.log('INFO', f'Device cooldown for {duration} seconds...')

        # 진행률 표시
        for i in range(duration):
            remaining = duration - i
            if remaining % 10 == 0 or remaining <= 5:
                self.log('INFO', f'  Cooldown: {remaining}s remaining...')
            time.sleep(1)

        self.log('SUCCESS', 'Cooldown completed')

    def health_check(self, verbose=True):
        """디바이스 상태 체크"""
        if verbose:
            self.log('INFO', '========== Device Health Check ==========')

        checks = {
            'device_connected': False,
            'frida_running': False,
            'memory_ok': False,
            'temp_ok': True  # 온도는 선택적
        }

        # 1. 디바이스 연결
        checks['device_connected'] = self.check_device_connected()
        if not checks['device_connected']:
            return checks

        # 2. Frida 서버
        checks['frida_running'] = self.is_frida_running()

        # 3. 메모리
        mem_info = self.get_memory_info()
        if mem_info:
            if verbose:
                self.log('INFO', f"Memory: {mem_info['available_mb']}MB available "
                        f"({mem_info['used_percent']}% used)")

            # 메모리 사용률 80% 이하면 OK
            checks['memory_ok'] = mem_info['used_percent'] < 80

            if not checks['memory_ok']:
                self.log('WARN', f"High memory usage: {mem_info['used_percent']}%")

        # 4. 온도 (선택적)
        temp = self.get_device_temp()
        if temp:
            if verbose:
                self.log('INFO', f'Temperature: {temp:.1f}°C')

            # 온도 60도 이하면 OK
            checks['temp_ok'] = temp < 60.0

            if not checks['temp_ok']:
                self.log('WARN', f'High temperature: {temp:.1f}°C')

        # 전체 상태
        all_ok = all([
            checks['device_connected'],
            checks['frida_running'],
            checks['memory_ok'],
            checks['temp_ok']
        ])

        if verbose:
            if all_ok:
                self.log('SUCCESS', 'Device health: OK')
            else:
                self.log('WARN', 'Device health: Issues detected')
            print('=' * 50)

        return checks

    def full_reset(self, cooldown_duration=30):
        """전체 리셋 (Frida 재시작 + 캐시 정리 + 쿨다운)"""
        self.log('INFO', '========== Full Device Reset ==========')

        # 1. 모든 앱 강제 종료
        self.force_stop_all_apps()
        time.sleep(2)

        # 2. Frida 서버 재시작
        if not self.restart_frida_server():
            self.log('ERROR', 'Frida restart failed, attempting recovery...')
            time.sleep(5)
            self.start_frida_server()

        time.sleep(2)

        # 3. 캐시 정리
        self.clear_cache()
        time.sleep(1)

        # 4. 쿨다운
        self.device_cooldown(cooldown_duration)

        # 5. 최종 상태 확인
        checks = self.health_check(verbose=True)

        success = checks['device_connected'] and checks['frida_running']

        if success:
            self.log('SUCCESS', 'Full reset completed successfully')
        else:
            self.log('ERROR', 'Full reset completed with issues')

        return success


def main():
    """테스트 실행"""
    import argparse

    parser = argparse.ArgumentParser(description='Android Device Manager')
    parser.add_argument('action', choices=[
        'check', 'restart-frida', 'stop-frida', 'start-frida',
        'clear-cache', 'cooldown', 'full-reset'
    ])
    parser.add_argument('--frida-path', default='/data/local/tmp/frida-server')
    parser.add_argument('--cooldown', type=int, default=30, help='Cooldown duration (seconds)')

    args = parser.parse_args()

    manager = DeviceManager(frida_server_path=args.frida_path)

    if args.action == 'check':
        manager.health_check(verbose=True)
    elif args.action == 'restart-frida':
        manager.restart_frida_server()
    elif args.action == 'stop-frida':
        manager.stop_frida_server()
    elif args.action == 'start-frida':
        manager.start_frida_server()
    elif args.action == 'clear-cache':
        manager.clear_cache()
    elif args.action == 'cooldown':
        manager.device_cooldown(args.cooldown)
    elif args.action == 'full-reset':
        manager.full_reset(cooldown_duration=args.cooldown)


if __name__ == '__main__':
    main()
