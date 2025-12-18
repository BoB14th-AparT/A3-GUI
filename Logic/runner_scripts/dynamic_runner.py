#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dynamic_runner.py
Dynamic 분석 실행 래퍼 (테스트용: 60초 × 1회)
"""
import subprocess
import sys
import os
import shutil
import glob
from pathlib import Path

# Windows 콘솔 인코딩 문제 해결 (조건부)
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    try:
        import io
        if not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass


def safe_print(text):
    """안전한 출력"""
    try:
        print(text, flush=True)
    except:
        try:
            print(str(text).encode('ascii', errors='ignore').decode('ascii'), flush=True)
        except:
            pass


def check_node_installed():
    """Node.js 설치 확인"""
    node_path = shutil.which('node')
    if node_path:
        try:
            result = subprocess.run([node_path, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                safe_print(f"[+] Node.js 버전: {result.stdout.strip()}")
                return True
        except:
            pass
    
    for path in [r'C:\Program Files\nodejs\node.exe', r'C:\Program Files (x86)\nodejs\node.exe']:
        if os.path.exists(path):
            try:
                result = subprocess.run([path, '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    safe_print(f"[+] Node.js 버전: {result.stdout.strip()}")
                    return True
            except:
                pass
    
    return False


def run_dynamic_analysis(package_name, duration=60, runs=1, output_dir=None):
    """Dynamic 분석 실행 (테스트용 기본값: 60초 × 1회)"""
    safe_print("=" * 60)
    safe_print("=== Dynamic 분석 시작 ===")
    safe_print("=" * 60)

    if not check_node_installed():
        safe_print("[!] Node.js가 설치되지 않았습니다.")
        return None

    script_dir = Path(__file__).parent
    dynamic_dir = script_dir.parent / "Dynamic"
    
    if not dynamic_dir.exists():
        safe_print(f"[!] Dynamic 디렉토리를 찾을 수 없습니다: {dynamic_dir}")
        return None

    safe_print(f"[+] Dynamic 디렉토리: {dynamic_dir}")

    pipeline_runner = dynamic_dir / "pipeline_runner.js"
    if not pipeline_runner.exists():
        safe_print(f"[!] pipeline_runner.js를 찾을 수 없습니다: {pipeline_runner}")
        return None

    final_output = f"dynamic_{package_name}.csv"
    estimated_time = (duration * runs) + 120
    
    safe_print(f"\n=== 분석 설정 ===")
    safe_print(f"패키지명: {package_name}")
    safe_print(f"실행 시간: {duration}초 × {runs}회")
    safe_print(f"예상 소요: 약 {estimated_time//60}분")
    safe_print("=" * 60)

    original_dir = os.getcwd()
    os.chdir(str(dynamic_dir))

    try:
        node_cmd = shutil.which('node') or r'C:\Program Files\nodejs\node.exe'
        cmd = f'"{node_cmd}" pipeline_runner.js --pkg {package_name} --duration {duration} --runs {runs} --spawn'
        
        safe_print(f"\n[+] 명령어: {cmd}")
        safe_print(f"[+] 작업 디렉토리: {os.getcwd()}")
        safe_print(f"[+] 디바이스에서 앱 실행 및 API 호출 수집 중...\n")
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # Node.js 실행 (실시간 출력)
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            bufsize=1,
            universal_newlines=True
        )
        
        # 실시간 로그 출력
        for line in process.stdout:
            safe_print(line.rstrip())
        
        process.wait(timeout=estimated_time)
        
        if process.returncode != 0:
            safe_print(f"[!] Node.js 실행 실패 (exit code: {process.returncode})")
            return None
        
        safe_print("\n[+] Node.js 실행 완료")
        
        # ===== 결과 파일 찾기 (pipeline_runner.js가 생성한 폴더) =====
        artifacts_output = "artifacts_output"
        pipeline_dirs = glob.glob(os.path.join(artifacts_output, f"pipeline_{package_name}_*"))
        
        if not pipeline_dirs:
            safe_print("[!] 결과 폴더 없음")
            return None
        
        # 가장 최근 폴더 선택
        latest_pipeline_dir = sorted(pipeline_dirs)[-1]
        safe_print(f"[+] 결과 폴더: {latest_pipeline_dir}")
        
        # merged_collected_paths.csv 찾기
        source_file = os.path.join(latest_pipeline_dir, "merged_collected_paths.csv")
        tokenized_file = os.path.join(latest_pipeline_dir, "merged_collected_paths_tokenized.csv")
        
        if not os.path.exists(source_file):
            safe_print(f"[!] 결과 파일 없음: {source_file}")
            return None
        
        safe_print(f"[+] 원본 결과: {source_file}")
        
        # ===== Export 폴더 구조 생성 =====
        if output_dir:
            export_dir = os.path.join(output_dir, "Export")
        else:
            export_dir = os.path.join(original_dir, "Export")
        
        # Export/Dynamic 폴더 (대문자 D)
        export_dynamic_dir = os.path.join(export_dir, "Dynamic")
        os.makedirs(export_dir, exist_ok=True)
        os.makedirs(export_dynamic_dir, exist_ok=True)
        
        # ===== 1. artifacts_output 전체를 Export/Dynamic으로 이동 =====
        if os.path.exists(artifacts_output):
            dst_artifacts = os.path.join(export_dynamic_dir, "artifacts_output")
            try:
                if os.path.exists(dst_artifacts):
                    shutil.rmtree(dst_artifacts)
                shutil.move(artifacts_output, dst_artifacts)
                safe_print(f"[+] 중간 폴더 이동: {dst_artifacts}")
            except Exception as e:
                safe_print(f"[!] 폴더 이동 실패: {e}")
        
        # ===== 2. 중간 파일 경로 업데이트 =====
        # artifacts_output이 이동했으므로 경로 갱신
        source_file = os.path.join(export_dynamic_dir, "artifacts_output", 
                                   os.path.basename(latest_pipeline_dir), 
                                   "merged_collected_paths.csv")
        tokenized_file = os.path.join(export_dynamic_dir, "artifacts_output",
                                      os.path.basename(latest_pipeline_dir),
                                      "merged_collected_paths_tokenized.csv")
        
        # ===== 3. 최종 파일은 Export 루트로 복사하지 않음! (토큰화 후 저장) =====
        # output_path는 나중에 토큰화 단계에서 사용
        output_path = os.path.join(export_dir, final_output)
        
        if not os.path.exists(source_file):
            safe_print(f"[!] 결과 파일 없음: {source_file}")
            return None
        
        safe_print(f"[+] 원본 결과: {source_file}")
        safe_print(f"[+] 중간 파일 위치: {export_dynamic_dir}")

        # ===== 1단계: 파일 제거, 폴더만 유지 (postprocess_dynamic.py) =====
        safe_print("\n" + "=" * 60)
        safe_print("=== 1단계: 후처리 (파일→폴더) ===")
        safe_print("=" * 60)

        postprocess_script = dynamic_dir / "postprocess_dynamic.py"
        postprocessed_file = os.path.join(export_dynamic_dir, "artifacts_output",
                                          os.path.basename(latest_pipeline_dir),
                                          "merged_collected_paths_postprocessed.csv")

        if postprocess_script.exists():
            cmd_postprocess = (
                f'python "{postprocess_script}" '
                f'--input "{source_file}" '
                f'--output "{postprocessed_file}"'
            )

            try:
                result = subprocess.run(
                    cmd_postprocess,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=300
                )

                if result.stdout:
                    safe_print(result.stdout)

                if result.returncode == 0 and os.path.exists(postprocessed_file):
                    safe_print(f"[+] ✅ 후처리 완료: {postprocessed_file}")
                    source_file = postprocessed_file  # 다음 단계 입력으로 사용
                else:
                    safe_print(f"[WARN] 후처리 실패 (exit code: {result.returncode}), 원본 사용")

            except subprocess.TimeoutExpired:
                safe_print("[WARN] 후처리 타임아웃, 원본 사용")
            except Exception as e:
                safe_print(f"[WARN] 후처리 오류: {e}, 원본 사용")
        else:
            safe_print("[WARN] postprocess_dynamic.py 없음, 후처리 스킵")

        # ===== 2단계: 깨진 문자 제거 (cleanup_dynamic_corrupted.py) =====
        safe_print("\n" + "=" * 60)
        safe_print("=== 2단계: 깨진 문자 제거 ===")
        safe_print("=" * 60)

        cleanup_corrupted_script = dynamic_dir / "cleanup_dynamic_corrupted.py"
        cleaned_file = os.path.join(export_dynamic_dir, "artifacts_output",
                                    os.path.basename(latest_pipeline_dir),
                                    "merged_collected_paths_cleaned.csv")

        if cleanup_corrupted_script.exists():
            cmd_cleanup_corrupted = (
                f'python "{cleanup_corrupted_script}" '
                f'--input "{source_file}" '
                f'--output "{cleaned_file}"'
            )

            try:
                result2 = subprocess.run(
                    cmd_cleanup_corrupted,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=300
                )

                if result2.stdout:
                    safe_print(result2.stdout)

                if result2.returncode == 0 and os.path.exists(cleaned_file):
                    safe_print(f"[+] ✅ 깨진 문자 제거 완료: {cleaned_file}")
                    source_file = cleaned_file  # 다음 단계 입력으로 사용
                else:
                    safe_print(f"[WARN] 깨진 문자 제거 실패 (exit code: {result2.returncode}), 이전 파일 사용")

            except subprocess.TimeoutExpired:
                safe_print("[WARN] 깨진 문자 제거 타임아웃, 이전 파일 사용")
            except Exception as e:
                safe_print(f"[WARN] 깨진 문자 제거 오류: {e}, 이전 파일 사용")
        else:
            safe_print("[WARN] cleanup_dynamic_corrupted.py 없음, 깨진 문자 제거 스킵")

        # ===== 3단계: 토큰화 (path_tokenizer.py) =====
        safe_print("\n" + "=" * 60)
        safe_print("=== 3단계: 토큰화 ===")
        safe_print("=" * 60)

        tokenizer_script = dynamic_dir / "path_tokenizer.py"
        token_output = f"dynamic_token_{package_name}.csv"
        token_path = os.path.join(export_dir, token_output)

        # path_tokenizer.py 실행 (source_file은 cleaned_file)
        if tokenizer_script.exists():
            cmd_tokenize = (
                f'python "{tokenizer_script}" '
                f'--csv "{source_file}" '
                f'--column "path" '
                f'--new-column "path_tokenized" '
                f'--out "{token_path}"'
            )
            
            try:
                result = subprocess.run(
                    cmd_tokenize,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=300
                )
                
                if result.stdout:
                    safe_print(result.stdout)
                
                if result.returncode == 0 and os.path.exists(token_path):
                    safe_print(f"[+] ✅ 토큰화 완료: {token_path}")
                else:
                    safe_print(f"[WARN] 토큰화 실패 (exit code: {result.returncode})")
                    return output_path
            
            except subprocess.TimeoutExpired:
                safe_print("[WARN] 토큰화 타임아웃")
                return output_path
            except Exception as e:
                safe_print(f"[WARN] 토큰화 오류: {e}")
                return output_path
        else:
            safe_print("[WARN] path_tokenizer.py 없음, 토큰화 스킵")
            return output_path
        
        # ===== 4단계: 중복 제거 (cleanup_dynamic_tokens.py) =====
        if not os.path.exists(token_path):
            safe_print("[WARN] 토큰 파일 없음, 중복 제거 스킵")
            return output_path

        safe_print("\n" + "=" * 60)
        safe_print("=== 4단계: 중복 제거 ===")
        safe_print("=" * 60)
        
        cleanup_script = dynamic_dir / "cleanup_dynamic_tokens.py"
        if cleanup_script.exists():
            cmd_cleanup = (
                f'python "{cleanup_script}" '
                f'--in-dir "{export_dir}" '
                f'--out-dir "{export_dir}" '
                f'--pattern "{token_output}"'
            )
            
            try:
                result2 = subprocess.run(
                    cmd_cleanup,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=300
                )
                
                if result2.stdout:
                    safe_print(result2.stdout)
                
                final_token_path = os.path.join(export_dir, f"dynamic_token_dup_{package_name}.csv")
                if result2.returncode == 0 and os.path.exists(final_token_path):
                    safe_print(f"[+] ✅ 중복 제거 완료: {final_token_path}")
                    
                    # 중간 토큰 파일을 Export/Dynamic으로 이동
                    shutil.move(token_path, os.path.join(export_dynamic_dir, token_output))
                    safe_print(f"[+] 중간 파일 이동: {export_dynamic_dir}/{token_output}")
                    
                    # 최종 파일 경로 반환
                    return final_token_path
                else:
                    safe_print(f"[WARN] 중복 제거 실패 (exit code: {result2.returncode})")
                    return token_path
            
            except subprocess.TimeoutExpired:
                safe_print("[WARN] 중복 제거 타임아웃")
                return token_path
            except Exception as e:
                safe_print(f"[WARN] 중복 제거 오류: {e}")
                return token_path
        else:
            safe_print("[WARN] cleanup_dynamic_tokens.py 없음, 중복 제거 스킵")
            return token_path
        
    except subprocess.TimeoutExpired:
        safe_print(f"\n[!] 시간 초과")
        if 'process' in locals():
            process.kill()
        return None
    except Exception as e:
        safe_print(f"\n[!] 오류: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        safe_print("사용법: python dynamic_runner.py <패키지명> [duration] [runs] [출력 디렉토리]")
        sys.exit(1)

    pkg = sys.argv[1]
    dur = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    rns = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    out_dir = sys.argv[4] if len(sys.argv) > 4 else None

    result = run_dynamic_analysis(pkg, dur, rns, out_dir)
    sys.exit(0 if result else 1)