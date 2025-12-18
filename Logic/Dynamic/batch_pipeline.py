#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
여러 앱에 대해 순차적으로 파이프라인 실행
Usage:
    python batch_pipeline.py --applist applist.txt --duration 300 --runs 3
"""

import subprocess
import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from device_manager import DeviceManager

def log(level, message):
    """로그 출력"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    prefix = {
        'INFO': '📌',
        'SUCCESS': '✅',
        'ERROR': '❌',
        'WARN': '⚠️'
    }.get(level, '  ')
    print(f"[{timestamp}] {prefix} {message}")

def read_applist(applist_path):
    """applist.txt 읽기"""
    if not os.path.exists(applist_path):
        raise FileNotFoundError(f"App list file not found: {applist_path}")

    with open(applist_path, 'r', encoding='utf-8') as f:
        apps = []
        for line_num, line in enumerate(f, start=1):
            line = line.strip()

            # 빈 줄, 주석 무시
            if not line or line.startswith('#'):
                continue

            # 쌍따옴표/작은따옴표 제거 (CSV 형식 지원)
            line = line.strip('"').strip("'")

            # 유효한 패키지명 검증 (알파벳, 숫자, 점, 언더스코어만)
            if not line or not all(c.isalnum() or c in '._' for c in line):
                log('WARN', f'Line {line_num}: Skipping invalid package name: "{line}"')
                continue

            apps.append(line)

    return apps

def run_pipeline(pkg, duration, runs, spawn, ground_truth_dir, auto_extract_adb, device_manager=None):
    """단일 앱에 대해 pipeline_runner.js 실행"""
    log('INFO', f'========== Starting pipeline for {pkg} ==========')

    # 디바이스 상태 사전 체크
    if device_manager:
        checks = device_manager.health_check(verbose=False)
        if not checks['device_connected']:
            log('ERROR', 'Device not connected, skipping...')
            return False
        if not checks['frida_running']:
            log('WARN', 'Frida not running, attempting restart...')
            device_manager.restart_frida_server()

    # Ground truth 파일 경로 생성
    ground_truth = os.path.join(ground_truth_dir, f'adb_{pkg}.csv')

    # Ground truth 파일 존재 여부 확인
    if os.path.exists(ground_truth):
        log('INFO', f'Using existing ground truth: {ground_truth}')
    else:
        if auto_extract_adb:
            log('INFO', f'Ground truth will be auto-generated via ADB extraction')
            ground_truth = None  # pipeline_runner.js가 자동 생성
        else:
            log('WARN', f'Ground truth file not found: {ground_truth}')
            log('INFO', 'Running without ground truth comparison')
            ground_truth = None

    # 명령어 구성
    cmd = [
        'node',
        'pipeline_runner.js',
        '--pkg', pkg,
        '--duration', str(duration),
        '--runs', str(runs),
        '--out', 'artifacts_output'
    ]

    if spawn:
        cmd.append('--spawn')

    if ground_truth:
        cmd.extend(['--ground-truth', ground_truth])

    log('INFO', f'Command: {" ".join(cmd)}')

    # 실행
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False,  # 실시간 출력
            text=True,
            timeout=duration * runs + 300  # 여유 시간 추가
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            log('SUCCESS', f'Pipeline completed for {pkg} (elapsed: {elapsed:.1f}s)')
            return True
        else:
            log('ERROR', f'Pipeline failed for {pkg} with code {result.returncode}')
            return False

    except subprocess.TimeoutExpired:
        log('ERROR', f'Pipeline timeout for {pkg}')
        return False
    except Exception as e:
        log('ERROR', f'Pipeline error for {pkg}: {e}')
        return False

def main():
    parser = argparse.ArgumentParser(description='Batch pipeline runner for multiple apps')
    parser.add_argument('--applist', required=True, help='Path to app list file (one package per line)')
    parser.add_argument('--duration', type=int, default=300, help='Duration per run (seconds)')
    parser.add_argument('--runs', type=int, default=3, help='Number of runs per app')
    parser.add_argument('--spawn', action='store_true', default=True, help='Use Frida spawn mode (default: True)')
    parser.add_argument('--no-spawn', dest='spawn', action='store_false', help='Disable spawn mode (use attach mode)')
    parser.add_argument('--ground-truth-dir', default='artifacts_output', help='Directory containing ground truth CSV files')
    parser.add_argument('--auto-extract-adb', action='store_true', help='Auto-generate ground truth via ADB extraction')
    parser.add_argument('--delay', type=int, default=30, help='Delay between apps (seconds)')
    parser.add_argument('--start-from', type=int, default=0, help='Start from index (0-based)')

    # 디바이스 관리 옵션
    parser.add_argument('--enable-device-management', action='store_true',
                       help='Enable device health monitoring and Frida server management (RECOMMENDED)')
    parser.add_argument('--cooldown', type=int, default=30,
                       help='Cooldown duration after each app (seconds, default: 30)')
    parser.add_argument('--restart-frida-interval', type=int, default=1,
                       help='Restart Frida server every N apps (0=disable, default: 1=every app)')
    parser.add_argument('--frida-server-path', default='/data/local/tmp/frida-server',
                       help='Path to Frida server on device')

    args = parser.parse_args()

    # 앱 리스트 읽기
    try:
        apps = read_applist(args.applist)
    except Exception as e:
        log('ERROR', f'Failed to read app list: {e}')
        sys.exit(1)

    total_apps = len(apps)
    log('INFO', f'Found {total_apps} apps in {args.applist}')

    # 시작 인덱스 적용
    if args.start_from > 0:
        apps = apps[args.start_from:]
        log('INFO', f'Starting from index {args.start_from} ({total_apps - len(apps)} apps skipped)')

    # 디바이스 매니저 초기화
    device_manager = None
    if args.enable_device_management:
        log('INFO', 'Device management enabled')
        device_manager = DeviceManager(frida_server_path=args.frida_server_path)

        # 초기 상태 체크
        log('INFO', 'Initial device health check...')
        checks = device_manager.health_check(verbose=True)

        if not checks['device_connected']:
            log('ERROR', 'Device not connected, cannot proceed')
            sys.exit(1)

        if not checks['frida_running']:
            log('WARN', 'Frida server not running, starting...')
            if not device_manager.start_frida_server():
                log('ERROR', 'Failed to start Frida server, cannot proceed')
                sys.exit(1)
    else:
        log('WARN', 'Device management disabled - pipeline may be unstable')
        log('INFO', 'Recommendation: Use --enable-device-management flag')

    # 결과 저장
    results = {
        'success': [],
        'failed': []
    }

    batch_start_time = time.time()

    # 각 앱에 대해 순차 실행
    for idx, pkg in enumerate(apps, start=args.start_from):
        log('INFO', f'Processing app {idx + 1}/{total_apps}: {pkg}')

        success = run_pipeline(
            pkg=pkg,
            duration=args.duration,
            runs=args.runs,
            spawn=args.spawn,
            ground_truth_dir=args.ground_truth_dir,
            auto_extract_adb=args.auto_extract_adb,
            device_manager=device_manager
        )

        if success:
            results['success'].append(pkg)
        else:
            results['failed'].append(pkg)

        # 마지막 앱이 아니면 디바이스 관리 작업 수행
        if idx < total_apps - 1:
            if device_manager:
                # Frida 서버 재시작 (설정된 간격마다)
                if args.restart_frida_interval > 0 and (idx + 1) % args.restart_frida_interval == 0:
                    log('INFO', f'Frida server restart interval reached ({args.restart_frida_interval} apps)')
                    device_manager.full_reset(cooldown_duration=args.cooldown)
                else:
                    # 간단한 정리 + 쿨다운
                    log('INFO', 'Performing cleanup and cooldown...')
                    device_manager.force_stop_all_apps()
                    device_manager.clear_cache()
                    device_manager.device_cooldown(args.cooldown)

                    # 상태 체크
                    checks = device_manager.health_check(verbose=True)
                    if not checks['frida_running']:
                        log('WARN', 'Frida stopped unexpectedly, restarting...')
                        device_manager.restart_frida_server()
            else:
                # 디바이스 관리 비활성화 시 기본 대기
                log('INFO', f'Waiting {args.delay} seconds before next app...')
                time.sleep(args.delay)

    # 최종 결과
    total_elapsed = time.time() - batch_start_time

    print('\n' + '=' * 50)
    log('INFO', 'Batch Pipeline Summary')
    print('=' * 50)
    print(f'Total apps: {total_apps}')
    print(f'Success: {len(results["success"])}')
    print(f'Failed: {len(results["failed"])}')
    print(f'Total elapsed: {total_elapsed / 3600:.2f} hours')
    print()

    if results['success']:
        print('✅ Successful apps:')
        for pkg in results['success']:
            print(f'  - {pkg}')
        print()

    if results['failed']:
        print('❌ Failed apps:')
        for pkg in results['failed']:
            print(f'  - {pkg}')
        print()

    # 결과 저장
    result_file = f'batch_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(f'Batch Pipeline Results\n')
        f.write(f'Date: {datetime.now()}\n')
        f.write(f'Total: {total_apps}, Success: {len(results["success"])}, Failed: {len(results["failed"])}\n\n')
        f.write('Success:\n')
        for pkg in results['success']:
            f.write(f'  {pkg}\n')
        f.write('\nFailed:\n')
        for pkg in results['failed']:
            f.write(f'  {pkg}\n')

    log('SUCCESS', f'Results saved to {result_file}')

    sys.exit(0 if len(results['failed']) == 0 else 1)

if __name__ == '__main__':
    main()
