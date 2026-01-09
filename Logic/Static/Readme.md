1. python taint_ip_merged_fin.py --apk <apk 경로> --sources sources_merged.txt --sinks sinks_merged.txt --dyn-methods dyn_methods_merged.txt --out taint_flows_<앱 이름>_merged.jsonl --full-trace (--debug: 디버깅)

2. python artifacts_path_merged_fin.py taint_flows_<앱 이름>_merged.jsonl -o artifacts_path_<앱 이름>_merged.csv

3. python noise_filter.py -i artifacts_path_<앱 이름>_merged.csv -o artifacts_path_<앱 이름>_merged.csv -f filter.txt (--removed: 제거된 행 저장, --quiet: 상세 로그 숨김)

4. python filter_artifacts.py -i artifacts_path_<앱 이름>_merged.csv -o artifacts_<앱 이름>_filter_path.csv

5. python compare_paths.py --adb adb_<앱 패키지명>.csv --code artifacts_<앱 이름>_filter_path.csv -o <앱 이름>_compare.csv

6. 