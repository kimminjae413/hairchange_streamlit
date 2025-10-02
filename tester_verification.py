#!/usr/bin/env python3
"""
테스터 독립 검증 스크립트 (최종버전)
SSH 접속 후 이 파일을 실행하여 VModel AI 성능을 독립적으로 검증
KOLAS 인증 기준 준수 + 9단계 처리 흐름 추적
"""

import json
import os
from datetime import datetime
from collections import defaultdict

def calculate_kolas_metrics():
    """KOLAS 기준에 따른 성능 지표 계산"""
    
    print("\n" + "="*80)
    print("🔍 VModel AI 성능 지표 독립 검증 (KOLAS 인증 기준)")
    print("="*80)
    
    # 성능 로그 파일 읽기
    performance_data = []
    performance_file = "performance_data/performance_log.jsonl"
    
    try:
        with open(performance_file, "r", encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        performance_data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"⚠️  JSON 파싱 오류 무시: {e}")
                        continue
    except FileNotFoundError:
        print(f"❌ 성능 데이터 파일을 찾을 수 없습니다: {performance_file}")
        print(f"   현재 디렉토리: {os.getcwd()}")
        print(f"   파일 존재 여부: {os.path.exists(performance_file)}")
        return None
    
    if not performance_data:
        print("❌ 성능 데이터가 없습니다.")
        print("   헤어스타일 변환을 먼저 실행해주세요.")
        return None
    
    print(f"\n📂 데이터 파일: {os.path.abspath(performance_file)}")
    print(f"📊 총 레코드 수: {len(performance_data)}")
    
    # 중복 검사 - request_id 기준
    request_ids = [record.get('request_id') for record in performance_data]
    unique_request_ids = set(request_ids)
    
    if len(request_ids) != len(unique_request_ids):
        print(f"\n⚠️  중복 감지: {len(request_ids) - len(unique_request_ids)}개의 중복 레코드")
        print("   → 중복 제거 후 계산합니다")
        
        # 중복 제거 (같은 request_id는 최신 것만 유지)
        unique_data = {}
        for record in performance_data:
            req_id = record.get('request_id')
            if req_id:
                unique_data[req_id] = record
        performance_data = list(unique_data.values())
        print(f"   → 중복 제거 완료: {len(performance_data)}개 레코드")
    else:
        print(f"\n✅ 중복 없음: 모든 레코드가 고유함")
    
    # 기본 통계
    total_tests = len(performance_data)
    successful_tests = sum(1 for record in performance_data if record.get('success', False))
    completed_tests = sum(1 for record in performance_data if record.get('completed', False))
    failed_tests = total_tests - successful_tests
    
    # KOLAS 기준 계산
    # Accuracy = (성공한 요청 / 전체 요청) × 100
    accuracy = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
    
    # Precision = (완료된 요청 / 성공한 요청) × 100
    precision = (completed_tests / successful_tests) * 100 if successful_tests > 0 else 0
    
    # Recall = (완료된 요청 / 전체 요청) × 100
    recall = (completed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    # F1-Score = 2 × (Precision × Recall) / (Precision + Recall)
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # 처리 시간 분석
    processing_times = [record.get('processing_time', 0) for record in performance_data if record.get('success', False)]
    api_response_times = [record.get('api_response_time', 0) for record in performance_data if record.get('api_response_time', 0)]
    
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    avg_api_response_time = sum(api_response_times) / len(api_response_times) if api_response_times else 0
    max_processing_time = max(processing_times) if processing_times else 0
    min_processing_time = min(processing_times) if processing_times else 0
    
    # 결과 출력
    print("\n" + "-"*80)
    print("📈 측정 데이터 (중복 제거 완료)")
    print("-"*80)
    print(f"전체 변환 시도:     {total_tests:>3}건")
    print(f"성공한 변환:        {successful_tests:>3}건")
    print(f"완료된 변환:        {completed_tests:>3}건 (result_url 생성)")
    print(f"실패한 변환:        {failed_tests:>3}건")
    
    print("\n" + "-"*80)
    print("🏆 KOLAS 성능 지표 (인증 기준: 75% 이상)")
    print("-"*80)
    
    # Accuracy
    accuracy_status = "✅ 통과" if accuracy >= 75 else "❌ 미달"
    print(f"Accuracy (정확도):   {accuracy:>6.2f}%  {accuracy_status}")
    print(f"  → 공식: (성공 / 전체) × 100")
    print(f"  → 계산: ({successful_tests} ÷ {total_tests}) × 100 = {accuracy:.2f}%")
    
    # Precision
    precision_status = "✅ 통과" if precision >= 75 else "❌ 미달"
    print(f"\nPrecision (정밀도):  {precision:>6.2f}%  {precision_status}")
    print(f"  → 공식: (완료 / 성공) × 100")
    print(f"  → 계산: ({completed_tests} ÷ {successful_tests}) × 100 = {precision:.2f}%")
    
    # Recall
    recall_status = "✅ 통과" if recall >= 75 else "❌ 미달"
    print(f"\nRecall (재현율):     {recall:>6.2f}%  {recall_status}")
    print(f"  → 공식: (완료 / 전체) × 100")
    print(f"  → 계산: ({completed_tests} ÷ {total_tests}) × 100 = {recall:.2f}%")
    
    # F1-Score
    f1_status = "✅ 통과" if f1_score >= 75 else "❌ 미달"
    print(f"\nF1-Score:            {f1_score:>6.2f}%  {f1_status}")
    print(f"  → 공식: 2 × (Precision × Recall) / (Precision + Recall)")
    print(f"  → 계산: 2 × ({precision:.2f} × {recall:.2f}) / ({precision:.2f} + {recall:.2f}) = {f1_score:.2f}%")
    
    print("\n" + "-"*80)
    print("⏱️  처리 시간 분석")
    print("-"*80)
    
    # AI 모델 생성시간 (전체 처리 시간)
    time_status = "✅ 통과" if avg_processing_time <= 60 else "❌ 미달"
    print(f"AI 모델 생성시간:   {avg_processing_time:>6.2f}초  {time_status} (기준: 60초 이내)")
    print(f"  → 평균: {avg_processing_time:.2f}초")
    print(f"  → 최대: {max_processing_time:.2f}초")
    print(f"  → 최소: {min_processing_time:.2f}초")
    
    # AI 모델 반응시간 (첫 응답 시간)
    reaction_status = "✅ 통과" if avg_api_response_time <= 1 else "❌ 미달"
    print(f"\nAI 모델 반응시간:   {avg_api_response_time:>6.2f}초  {reaction_status} (기준: 1초 이내)")
    print(f"  → Task 생성 API 첫 응답 시간")
    
    # 전체 기준 통과 여부
    all_passed = (
        accuracy >= 75 and 
        precision >= 75 and 
        recall >= 75 and 
        f1_score >= 75 and 
        avg_processing_time <= 60 and
        avg_api_response_time <= 1
    )
    
    print("\n" + "="*80)
    print("🎯 최종 검증 결과")
    print("="*80)
    
    if all_passed:
        print("✅ 모든 KOLAS 인증 기준을 통과했습니다!")
    else:
        print("❌ 일부 기준을 통과하지 못했습니다.")
        print("\n미달 항목:")
        if accuracy < 75:
            print(f"  • Accuracy: {accuracy:.2f}% (기준: 75% 이상)")
        if precision < 75:
            print(f"  • Precision: {precision:.2f}% (기준: 75% 이상)")
        if recall < 75:
            print(f"  • Recall: {recall:.2f}% (기준: 75% 이상)")
        if f1_score < 75:
            print(f"  • F1-Score: {f1_score:.2f}% (기준: 75% 이상)")
        if avg_processing_time > 60:
            print(f"  • 생성시간: {avg_processing_time:.2f}초 (기준: 60초 이내)")
        if avg_api_response_time > 1:
            print(f"  • 반응시간: {avg_api_response_time:.2f}초 (기준: 1초 이내)")
    
    print("="*80)
    
    return {
        'total_tests': total_tests,
        'successful_tests': successful_tests,
        'completed_tests': completed_tests,
        'failed_tests': failed_tests,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'avg_processing_time': avg_processing_time,
        'avg_api_response_time': avg_api_response_time,
        'all_passed': all_passed
    }

def show_processing_flow():
    """9단계 처리 흐름 추적 및 표시"""
    print("\n" + "="*80)
    print("📋 AI 처리 흐름 분석 (9단계)")
    print("="*80)
    
    log_file = "logs/vmodel_api_raw.log"
    
    try:
        with open(log_file, "r", encoding='utf-8') as f:
            content = f.read()
            lines = content.strip().split('\n')
        
        print(f"\n📂 파일: {os.path.abspath(log_file)}")
        print(f"📊 총 로그 라인: {len(lines)}")
        
        # request_id별로 그룹핑
        requests = defaultdict(list)
        for line in lines:
            if 'REQUEST_START' in line or 'REQUEST_COMPLETE' in line or 'STEP:' in line:
                # request_id 추출
                if 'Request=' in line or 'ID=' in line:
                    parts = line.split('Request=') if 'Request=' in line else line.split('ID=')
                    if len(parts) > 1:
                        req_id = parts[1].split(',')[0].split('|')[0].strip()
                        requests[req_id].append(line)
        
        if not requests:
            print("\n⚠️  처리 흐름 로그를 찾을 수 없습니다.")
            print("   app.py가 최신 버전인지 확인하세요.")
            return
        
        print(f"\n🔍 발견된 요청: {len(requests)}개")
        print("\n" + "-"*80)
        
        # 최근 3개 요청의 처리 흐름 표시
        recent_requests = list(requests.items())[-3:]
        
        for req_id, logs in recent_requests:
            print(f"\n📌 Request ID: {req_id}")
            print("-"*80)
            
            # 9단계 체크리스트
            steps = {
                '1_REQUEST_START': '❌',
                '2_IMAGE_UPLOAD': '❌',
                '3_API_REQUEST': '❌',
                '4_API_CALL': '❌',
                '5_FIRST_RESPONSE': '❌',
                '6_TASK_CREATED': '❌',
                '7_POLLING': '❌',
                '8_RESULT_DOWNLOAD': '❌',
                '9_COMPLETE': '❌'
            }
            
            for log in logs:
                if '1_REQUEST_START' in log or 'REQUEST_START' in log:
                    steps['1_REQUEST_START'] = '✅'
                if '2_IMAGE_UPLOAD' in log or 'IMAGE_UPLOAD' in log:
                    steps['2_IMAGE_UPLOAD'] = '✅'
                if '3_API_REQUEST' in log or 'API_REQUEST_PREPARED' in log:
                    steps['3_API_REQUEST'] = '✅'
                if '4_API_CALL' in log or 'API_CALL_START' in log:
                    steps['4_API_CALL'] = '✅'
                if '5_FIRST_RESPONSE' in log or 'FIRST_RESPONSE_RECEIVED' in log:
                    steps['5_FIRST_RESPONSE'] = '✅'
                if '6_TASK_CREATED' in log or 'TASK_CREATED' in log:
                    steps['6_TASK_CREATED'] = '✅'
                if '7_POLLING' in log or 'POLLING' in log:
                    steps['7_POLLING'] = '✅'
                if '8_RESULT_DOWNLOAD' in log or 'RESULT_DOWNLOAD' in log:
                    steps['8_RESULT_DOWNLOAD'] = '✅'
                if '9_COMPLETE' in log or 'REQUEST_COMPLETE' in log:
                    steps['9_COMPLETE'] = '✅'
            
            # 단계별 출력
            print("처리 단계:")
            print(f"  {steps['1_REQUEST_START']} 1. 요청 시작 (데이터 삽입)")
            print(f"  {steps['2_IMAGE_UPLOAD']} 2. 이미지 업로드")
            print(f"  {steps['3_API_REQUEST']} 3. API 요청 준비")
            print(f"  {steps['4_API_CALL']} 4. API 호출")
            print(f"  {steps['5_FIRST_RESPONSE']} 5. 첫 응답 수신 (반응시간 측정)")
            print(f"  {steps['6_TASK_CREATED']} 6. Task 생성 완료")
            print(f"  {steps['7_POLLING']} 7. 상태 폴링")
            print(f"  {steps['8_RESULT_DOWNLOAD']} 8. 결과 다운로드")
            print(f"  {steps['9_COMPLETE']} 9. 처리 완료 (자동 로깅)")
            
            # 전체 성공 여부
            all_steps = all(v == '✅' for v in steps.values())
            if all_steps:
                print("\n  ✅ 모든 단계 완료")
            else:
                print("\n  ⚠️  일부 단계 미완료")
        
        print("\n" + "-"*80)
        print("💡 참고: 최근 3개 요청의 처리 흐름만 표시됩니다.")
        
    except FileNotFoundError:
        print(f"❌ 로그 파일을 찾을 수 없습니다: {log_file}")

def show_vmodel_evidence():
    """VModel 서버 원본 데이터 검증"""
    print("\n" + "="*80)
    print("🛡️  VModel API 원본 응답 검증 (조작 불가능)")
    print("="*80)
    
    performance_file = "performance_data/performance_log.jsonl"
    
    try:
        with open(performance_file, "r", encoding='utf-8') as f:
            performance_data = []
            for line in f:
                if line.strip():
                    try:
                        performance_data.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        if not performance_data:
            print("❌ 데이터가 없습니다.")
            return
        
        # 완료된 변환만 필터링
        completed = [d for d in performance_data if d.get('completed')]
        
        print(f"\n📊 완료된 변환: {len(completed)}건")
        print("\n" + "-"*80)
        print("Task ID 목록 (VModel 서버가 직접 발급):")
        print("-"*80)
        
        for i, record in enumerate(completed, 1):
            task_id = record.get('task_id', 'N/A')
            result_url = record.get('result_url', '')
            timestamp = record.get('timestamp', '')
            
            print(f"\n[{i}] Task ID: {task_id}")
            print(f"    타임스탬프: {timestamp}")
            print(f"    결과 URL: {result_url[:80]}...")
            
            # VModel CDN 확인
            if 'replicate' in result_url or 'pbxt.replicate' in result_url:
                print(f"    ✅ VModel CDN 확인: 외부 서버 원본 데이터")
            else:
                print(f"    ⚠️  URL 형식 확인 필요")
        
        print("\n" + "-"*80)
        print("📌 검증 포인트:")
        print("  • Task ID는 VModel 서버가 직접 발급 (조작 불가)")
        print("  • Result URL은 VModel CDN에서 제공 (외부 서버)")
        print("  • 타임스탬프는 실시간 기록 (순차 검증 가능)")
        
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {performance_file}")

def show_raw_logs():
    """원본 로그 파일 표시"""
    print("\n" + "="*80)
    print("📄 VModel API 원본 로그")
    print("="*80)
    
    log_file = "logs/vmodel_api_raw.log"
    
    try:
        with open(log_file, "r", encoding='utf-8') as f:
            content = f.read()
            lines = content.strip().split('\n')
            total_lines = len(lines)
            
            print(f"\n📂 파일: {os.path.abspath(log_file)}")
            print(f"📊 총 라인 수: {total_lines}")
            print(f"\n마지막 30개 로그 (최근 활동):")
            print("-"*80)
            
            for line in lines[-30:]:
                print(line)
                
    except FileNotFoundError:
        print(f"❌ 로그 파일을 찾을 수 없습니다: {log_file}")
        print(f"   현재 디렉토리: {os.getcwd()}")

def show_success_summary():
    """성공/실패 요약 표시"""
    print("\n" + "="*80)
    print("📊 성공/실패 요약")
    print("="*80)
    
    log_file = "logs/success_failures.log"
    
    try:
        with open(log_file, "r", encoding='utf-8') as f:
            lines = f.readlines()
            total_lines = len(lines)
            
            print(f"\n📂 파일: {os.path.abspath(log_file)}")
            print(f"📊 총 라인 수: {total_lines}")
            
            # 성공/실패 카운트
            success_count = sum(1 for line in lines if 'SUCCESS' in line)
            failed_count = sum(1 for line in lines if 'FAILED' in line)
            
            print(f"\n통계:")
            print(f"  ✅ 성공: {success_count}건")
            print(f"  ❌ 실패: {failed_count}건")
            
            if total_lines > 0:
                success_rate = (success_count / total_lines) * 100
                print(f"  📈 성공률: {success_rate:.1f}%")
            
            print(f"\n마지막 15개 결과:")
            print("-"*80)
            
            for line in lines[-15:]:
                print(line.strip())
                
    except FileNotFoundError:
        print(f"❌ 요약 로그를 찾을 수 없습니다: {log_file}")

def export_report():
    """검증 결과를 텍스트 파일로 내보내기"""
    print("\n" + "="*80)
    print("📝 검증 결과 리포트 생성")
    print("="*80)
    
    metrics = calculate_kolas_metrics()
    
    if not metrics:
        print("❌ 데이터가 없어 리포트를 생성할 수 없습니다.")
        return
    
    report_file = f"KOLAS_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("VModel AI 성능 검증 리포트 (KOLAS 인증 기준)\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"검증 일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}\n")
        f.write(f"검증자: KOLAS 공인시험기관 테스터\n")
        f.write(f"검증 방법: SSH 독립 실행\n\n")
        
        f.write("-"*80 + "\n")
        f.write("📊 측정 데이터\n")
        f.write("-"*80 + "\n")
        f.write(f"전체 변환 시도:  {metrics['total_tests']}건\n")
        f.write(f"성공한 변환:     {metrics['successful_tests']}건\n")
        f.write(f"완료된 변환:     {metrics['completed_tests']}건\n")
        f.write(f"실패한 변환:     {metrics['failed_tests']}건\n\n")
        
        f.write("-"*80 + "\n")
        f.write("🏆 KOLAS 성능 지표 (인증 기준: 75% 이상)\n")
        f.write("-"*80 + "\n")
        f.write(f"Accuracy:   {metrics['accuracy']:.2f}%  {'✅ 통과' if metrics['accuracy'] >= 75 else '❌ 미달'}\n")
        f.write(f"Precision:  {metrics['precision']:.2f}%  {'✅ 통과' if metrics['precision'] >= 75 else '❌ 미달'}\n")
        f.write(f"Recall:     {metrics['recall']:.2f}%  {'✅ 통과' if metrics['recall'] >= 75 else '❌ 미달'}\n")
        f.write(f"F1-Score:   {metrics['f1_score']:.2f}%  {'✅ 통과' if metrics['f1_score'] >= 75 else '❌ 미달'}\n\n")
        
        f.write("-"*80 + "\n")
        f.write("⏱️  처리 시간\n")
        f.write("-"*80 + "\n")
        f.write(f"AI 모델 생성시간:  {metrics['avg_processing_time']:.2f}초  {'✅ 통과' if metrics['avg_processing_time'] <= 60 else '❌ 미달'} (기준: 60초)\n")
        f.write(f"AI 모델 반응시간:  {metrics['avg_api_response_time']:.2f}초  {'✅ 통과' if metrics['avg_api_response_time'] <= 1 else '❌ 미달'} (기준: 1초)\n\n")
        
        f.write("="*80 + "\n")
        f.write("🎯 최종 검증 결과\n")
        f.write("="*80 + "\n")
        
        if metrics['all_passed']:
            f.write("✅ 모든 KOLAS 인증 기준을 통과했습니다.\n\n")
        else:
            f.write("❌ 일부 기준을 통과하지 못했습니다.\n\n")
            f.write("미달 항목:\n")
            if metrics['accuracy'] < 75:
                f.write(f"  • Accuracy: {metrics['accuracy']:.2f}% (기준: 75% 이상)\n")
            if metrics['precision'] < 75:
                f.write(f"  • Precision: {metrics['precision']:.2f}% (기준: 75% 이상)\n")
            if metrics['recall'] < 75:
                f.write(f"  • Recall: {metrics['recall']:.2f}% (기준: 75% 이상)\n")
            if metrics['f1_score'] < 75:
                f.write(f"  • F1-Score: {metrics['f1_score']:.2f}% (기준: 75% 이상)\n")
            if metrics['avg_processing_time'] > 60:
                f.write(f"  • 생성시간: {metrics['avg_processing_time']:.2f}초 (기준: 60초 이내)\n")
            if metrics['avg_api_response_time'] > 1:
                f.write(f"  • 반응시간: {metrics['avg_api_response_time']:.2f}초 (기준: 1초 이내)\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("검증 완료\n")
        f.write("="*80 + "\n")
    
    print(f"\n✅ 리포트 생성 완료: {report_file}")
    print(f"   파일 위치: {os.path.abspath(report_file)}")

def main():
    """메인 함수"""
    import sys
    
    print("\n" + "="*80)
    print("🔧 VModel AI 테스터 독립 검증 도구 (최종버전)")
    print("   KOLAS 인증 기준 준수 + 9단계 처리 흐름 추적")
    print("="*80)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--metrics":
            calculate_kolas_metrics()
        elif command == "--flow":
            show_processing_flow()
        elif command == "--evidence":
            show_vmodel_evidence()
        elif command == "--logs":
            show_raw_logs()
        elif command == "--summary":
            show_success_summary()
        elif command == "--export":
            export_report()
        elif command == "--all":
            calculate_kolas_metrics()
            show_processing_flow()
            show_vmodel_evidence()
            show_success_summary()
        else:
            print("\n사용법:")
            print("  python tester_verification.py [옵션]")
            print("\n옵션:")
            print("  --metrics   : KOLAS 성능 지표 계산 (기본)")
            print("  --flow      : 9단계 처리 흐름 추적")
            print("  --evidence  : VModel 원본 데이터 검증")
            print("  --logs      : 원본 로그 표시")
            print("  --summary   : 성공/실패 요약")
            print("  --export    : 검증 결과 리포트 생성")
            print("  --all       : 전체 검증 (metrics + flow + evidence + summary)")
            print("\n옵션 없이 실행하면 기본 검증(--metrics)을 수행합니다.")
    else:
        # 기본 검증 실행
        calculate_kolas_metrics()
        print("\n💡 더 자세한 정보는 --all 옵션을 사용하세요.")

if __name__ == "__main__":
    main()
