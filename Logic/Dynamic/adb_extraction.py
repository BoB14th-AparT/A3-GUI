##Logic/Dynamic/adb_extraction.py
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
                # 디렉토리(폴더)만 추가하도록 수정
                if item['type'] == 'directory':
                    full_path = f"{path}/{item['filename']}"
                    paths.append(full_path)
                    print(f"     - [D] {item['filename']}")
        except Exception as e:
            continue
    
    return paths

def scan_base_paths(package_name):
    """기본 경로들 스캔"""
    all_paths = []
    
    # /storage/emulated/0 계열 (0단계)
    storage_base = '/storage/emulated/0'
    all_paths.append(storage_base)
    storage_files = f'/storage/emulated/0/Android/data/{package_name}/files'
    all_paths.append(storage_files)
    storage_cache = f'/storage/emulated/0/Android/data/{package_name}/cache'
    all_paths.append(storage_cache)
    
    # /sdcard/Android/data/{package_name} 계열 (0단계)
    sdcard_base = f'/sdcard/Android/data/{package_name}'
    all_paths.append(sdcard_base)
    sdcard_files = f'/sdcard/Android/data/{package_name}/files'
    all_paths.append(sdcard_files)
    sdcard_cache = f'/sdcard/Android/data/{package_name}/cache'
    all_paths.append(sdcard_cache)
    
    # 로그 출력
    print(f"\n{'='*60}")
    print(f" 0단계 기본 경로들 추가 완료 (6개)")
    print(f"{'='*60}")

    # 4. /data/user/0/{package_name} - 하위 폴더들만 수집 + 특정 폴더는 1단계 더 탐색
    data_user_base = f'/data/user/0/{package_name}'
    print(f"\n{'='*60}")
    print(f"기본 경로 탐색: {data_user_base}")
    print(f"{'='*60}")
    
    output, stderr, returncode = run_adb_command(f'ls -al "{data_user_base}"')
    
    if output and returncode == 0 and output.strip():
        lines = output.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            try:
                item = parse_ls_line(line)
                if item:
                    full_path = f"{data_user_base}/{item['filename']}"
                    
                    # 디렉토리(폴더)만 추가하도록 수정
                    if item['type'] == 'directory':
                        all_paths.append(full_path)
                        print(f"  [D] {item['filename']}")
                        
                        # files, databases, shared_prefs, cache만 1단계 더 들어가기
                        if item['filename'] in ['files', 'databases', 'shared_prefs', 'cache']:
                            print(f"    → {item['filename']}/ 하위 1단계 스캔 시작")
                            sub_paths = scan_one_level(full_path)
                            all_paths.extend(sub_paths)
                    # 파일은 무시
            except Exception as e:
                continue
    
    return all_paths

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
        all_paths = scan_base_paths(package_name)
        
        # CSV 저장
        if all_paths:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"paths_{package_name}_dirs_{timestamp}.csv"
            
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['full_path'])
                for path in all_paths:
                    writer.writerow([path])
            
            print(f"\n{'='*60}")
            print(f" 저장 완료: {output_file}")
            print(f"   총 {len(all_paths)}개 폴더 경로")
            print(f"{'='*60}")
        else:
            print("\n 수집된 경로가 없습니다.")
    except Exception as e:
        print(f"\n 오류: {e}")

if __name__ == "__main__":
    main()
