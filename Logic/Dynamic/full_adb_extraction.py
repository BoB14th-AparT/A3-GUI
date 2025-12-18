import subprocess
import csv
import sys
from datetime import datetime

# Windows cp949 인코딩 문제 해결
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run_adb_command(command):
    """adb shell su 명령 실행"""
    try:
        result = subprocess.run(
            ['adb', 'shell', 'su', '-c', command],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=10
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        print("    타임아웃")
        return "", "", -1
    except Exception as e:
        print(f"    오류: {e}")
        return "", str(e), -1

def parse_ls_line(line):
    """ls -al 한 줄 파싱"""
    if line.startswith('total'):
        return None
    
    parts = line.split()
    
    if len(parts) < 8:
        return None
    
    permissions = parts[0]
    filename = parts[7] if len(parts) > 7 else ''
    
    if len(parts) > 8:
        filename = ' '.join(parts[7:])
    
    if filename in ['.', '..']:
        return None
    
    return {
        'filename': filename,
        'type': 'directory' if permissions.startswith('d') else 'file'
    }

def scan_one_level(path):
    """1단계만 스캔 (하위 폴더만)"""
    paths = []
    
    print(f"    {path} (폴더만 스캔)")
    
    output, stderr, returncode = run_adb_command(f'ls -al "{path}"')
    
    if output is None or returncode != 0 or not output.strip():
        return paths
    
    lines = output.strip().split('\n')
    
    for line in lines:
        if not line.strip():
            continue
        
        try:
            item = parse_ls_line(line)
            if item:
                if item['type'] == 'directory':
                    full_path = f"{path}/{item['filename']}"
                    paths.append(full_path)
                    print(f"     - [D] {item['filename']}")
        except Exception:
            continue
    
    return paths

def scan_base_paths(package_name):
    """기본 경로들 스캔"""
    all_paths = []
    
    storage_base = '/storage/emulated/0'
    all_paths.append(storage_base)
    all_paths.append(f'/storage/emulated/0/Android/data/{package_name}/files')
    all_paths.append(f'/storage/emulated/0/Android/data/{package_name}/cache')
    
    sdcard_base = f'/sdcard/Android/data/{package_name}'
    all_paths.append(sdcard_base)
    all_paths.append(f'/sdcard/Android/data/{package_name}/files')
    all_paths.append(f'/sdcard/Android/data/{package_name}/cache')
    
    print(f"\n{'='*60}")
    print(f" 0단계 기본 경로들 추가 완료 (6개)")
    print(f"{'='*60}")

    data_user_base = f'/data/user/0/{package_name}'
    print(f"\n{'='*60}")
    print(f"기본 경로 탐색: {data_user_base}")
    print(f"{'='*60}")
    
    output, stderr, returncode = run_adb_command(f'ls -al "{data_user_base}"')
    
    if output and returncode == 0 and output.strip():
        for line in output.strip().split('\n'):
            try:
                item = parse_ls_line(line)
                if item and item['type'] == 'directory':
                    full_path = f"{data_user_base}/{item['filename']}"
                    all_paths.append(full_path)
                    print(f"  [D] {item['filename']}")
                    
                    if item['filename'] in ['files', 'databases', 'shared_prefs', 'cache']:
                        print(f"    → {item['filename']}/ 하위 1단계 스캔 시작")
                        all_paths.extend(scan_one_level(full_path))
            except Exception:
                continue
    
    return all_paths


# ===================== 추가된 함수 =====================
def scan_recursive_dirs(package_name):
    """디렉토리 전체 재귀 수집"""
    paths = []
    base = f'/data/user/0/{package_name}'
    output, _, rc = run_adb_command(f'find "{base}" -type d 2>/dev/null')
    if output and rc == 0:
        for line in output.split('\n'):
            if line.strip():
                paths.append(line.strip())
    return paths
# =====================================================


def main():
    print("="*60)
    print("ADB Package Path Extractor (폴더만 수집 모드)")
    print("="*60)
    
    package_name = input("\n패키지 이름 입력 (예: sg.bigo.live): ").strip()
    if not package_name:
        print("패키지 이름을 입력하세요!")
        return
    
    print(f"\n📱 패키지: {package_name}")
    print(f"🔍 경로 수집 시작 (폴더만) ...\n")
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 기존 1단계 기반 CSV
        all_paths = scan_base_paths(package_name)
        if all_paths:
            output_file = f"paths_{package_name}_dirs_{timestamp}.csv"
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['full_path'])
                for path in all_paths:
                    writer.writerow([path])
            print(f"\n 저장 완료: {output_file}")

        # ===== 추가: 전체 디렉토리 CSV =====
        recursive_paths = scan_recursive_dirs(package_name)
        if recursive_paths:
            output_file2 = f"paths_{package_name}_dirs_recursive_{timestamp}.csv"
            with open(output_file2, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['full_path'])
                for path in recursive_paths:
                    writer.writerow([path])
            print(f" 저장 완료: {output_file2}")
        # =================================

    except Exception as e:
        print(f"\n 오류: {e}")

if __name__ == "__main__":
    main()
