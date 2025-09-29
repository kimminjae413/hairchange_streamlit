#!/usr/bin/env python3
"""
테스터 독립 검증 스크립트
SSH 접속 후 이 파일을 실행하여 VModel AI 성능을 독립적으로 검증
KTCC/KOLAS 인증 기준 준수
"""

import json
import os
from datetime import datetime
from collections import defaultdict

def calculate_ktcc_metrics():
    """KTCC 기준에 따른 성능 지표 계산"""
    
    print("\n" + "="*70)
    print("🔍 VModel AI 성능 지표 독립 검증 (KTCC/KOLAS 기준)")
    print("="*70)
    
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
    
    # 기본 통계
    total_tests = len(performance_data)
    successful_tests = sum(1 for record in performance_data if record.get('success', False))
    completed_tests = sum(1 for record in performance_data if record.get('completed', False))
    failed_tests = total_tests - successful_tests
    
    # KTCC 기준 계산
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
    total_times = [record.get('total_time', 0) for record in performance_data if record.get('total_time', 0)]
    
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    avg_total_time = sum(total_times) / len(total_times) if total_times else 0
    max_processing_time = max(processing_times) if processing_times else 0
    min_processing_time = min(processing_times) if processing_times else 0
    
    # 결과 출력
    print("\n" + "-"*70)
    print("📈 기본 통계")
    print("-"*70)
    print(f"전체 변환 시도:     {total_tests:>3}건")
    print(f"성공한 변환:        {successful_tests:>3}건")
    print(f"완료된 변환:        {completed_tests:>3}건")
    print(f"실패한 변환:        {failed_tests:>3}건")
    
    print("\n" + "-"*70)
    print("🏆 KTCC 성능 지표 (기준: 75% 이상)")
    print("-"*70)
    
    # Accuracy
    accuracy_status = "✅ 통과" if accuracy >= 75 else "❌ 미달"
    print(f"Accuracy (정확도):   {accuracy:>6.2f}%  {accuracy_status}")
    print(f"  → 계산: ({successful_tests} ÷ {total_tests}) × 100")
    
    # Precision
    precision_status = "✅ 통과" if precision >= 75 else "❌ 미달"
    print(f"Precision (정밀도):  {precision:>6.2f}%  {precision_status}")
    print(f"  → 계산: ({completed_tests} ÷ {successful_tests}) × 100")
    
    # Recall
    recall_status = "✅ 통과" if recall >= 75 else "❌ 미달"
    print(f"Recall (재현율):     {recall:>6.2f}%  {recall_status}")
    print(f"  → 계산: ({completed_tests} ÷ {total_tests}) × 100")
    
    # F1-Score
    f1_status = "✅ 통과" if f1_score >= 75 else "❌ 미달"
    print(f"F1-Score:            {f1_score:>6.2f}%  {f1_status}")
    print(f"  → 계산: 2 × ({precision:.2f} × {recall:.2f}) ÷ ({precision:.2f} + {recall:.2f})")
    
    print("\n" + "-"*70)
    print("⏱️  처리 시간 분석")
    print("-"*70)
    
    # AI 모델 생성시간 (전체 처리 시간)
    time_status = "✅ 통과" if avg_processing_time <= 60 else "❌ 미달"
    print(f"AI 모델 생성시간:   {avg_processing_time:>6.2f}초  {time_status} (기준: 60초)")
    print(f"  → 평균: {avg_processing_time:.2f}초")
    print(f"  → 최대: {max_processing_time:.2f}초")
    print(f"  → 최소: {min_processing_time:.2f}초")
    
    # AI 모델 반응시간 (VModel 서버 처리 시간)
    reaction_status = "✅ 통과" if avg_total_time <= 1 else "❌ 미달"
    print(f"AI 모델 반응시간:   {avg_total_time:>6.2f}초  {reaction_status} (기준: 1초)")
    print(f"  → VModel 서버 처리 시간")
    
    # 전체 기준 통과 여부
    all_passed = (
        accuracy >= 75 and 
        precision >= 75 and 
        recall >= 75 and 
        f1_score >= 75 and 
        avg_processing_time <= 60
    )
    
    print("\n" + "="*70)
    print("🎯 최종 검증 결과")
    print("="*70)
    
    if all_passed:
        print("✅ 모든 KTCC/KOLAS 기준을 통과했습니다!")
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
    
    print("="*70)
    
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
        'avg_total_time': avg_total_time,
        'all_passed': all_passed
    }

def show_raw_logs():
    """원본 로그 파일 표시"""
    print("\n" + "="*70)
    print("📄 VModel API 원본 로그")
    print("="*70)
    
    log_file = "logs/vmodel_api_raw.log"
    
    try:
        with open(log_file, "r", encoding='utf-8') as f:
            content = f.read()
            lines = content.strip().split('\n')
            total_lines = len(lines)
            
            print(f"\n📂 파일: {os.path.abspath(log_file)}")
            print(f"📊 총 라인 수: {total_lines}")
            print(f"\n마지막 20개 로그 (최근 활동):")
            print("-"*70)
            
            for line in lines[-20:]:
                print(line)
                
    except FileNotFoundError:
        print(f"❌ 로그 파일을 찾을 수 없습니다: {log_file}")
        print(f"   현재 디렉토리: {os.getcwd()}")

def show_success_summary():
    """성공/실패 요약 표시"""
    print("\n" + "="*70)
    print("📊 성공/실패 요약")
    print("="*70)
    
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
            
            print(f"\n마지막 10개 결과:")
            print("-"*70)
            
            for line in lines[-10:]:
                print(line.strip())
                
    except FileNotFoundError:
        print(f"❌ 요약 로그를 찾을 수 없습니다: {log_file}")
        print(f"   현재 디렉토리: {os.getcwd()}")

def show_task_details():
    """Task ID별 상세 정보 표시"""
    print("\n" + "="*70)
    print("🔍 Task ID별 상세 정보")
    print("="*70)
    
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
        
        print(f"\n총 {len(performance_data)}개의 변환 기록")
        print("-"*70)
        
        for i, record in enumerate(performance_data, 1):
            status = "✅ 성공" if record.get('completed') else "❌ 실패"
            task_id = record.get('task_id', 'N/A')
            request_id = record.get('request_id', 'N/A')
            processing_time = record.get('processing_time', 0)
            timestamp = record.get('timestamp', 'N/A')
            
            print(f"\n[{i}] {status}")
            print(f"  Request ID:  {request_id}")
            print(f"  Task ID:     {task_id}")
            print(f"  처리시간:    {processing_time:.2f}초")
            print(f"  타임스탬프:  {timestamp}")
            
            if record.get('result_url'):
                print(f"  결과 URL:    {record['result_url'][:60]}...")
            
            if record.get('error'):
                print(f"  에러:        {record['error']}")
    
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {performance_file}")

def export_report():
    """검증 결과를 텍스트 파일로 내보내기"""
    print("\n" + "="*70)
    print("📝 검증 결과 내보내기")
    print("="*70)
    
    metrics = calculate_ktcc_metrics()
    
    if not metrics:
        print("❌ 데이터가 없어 리포트를 생성할 수 없습니다.")
        return
    
    report_file = f"verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("VModel AI 성능 검증 리포트 (KTCC/KOLAS 기준)\n")
        f.write("="*70 + "\n\n")
        
        f.write(f"검증 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"검증자: KTCC/KOLAS 테스터\n\n")
        
        f.write("-"*70 + "\n")
        f.write("기본 통계\n")
        f.write("-"*70 + "\n")
        f.write(f"전체 변환 시도:  {metrics['total_tests']}건\n")
        f.write(f"성공한 변환:     {metrics['successful_tests']}건\n")
        f.write(f"완료된 변환:     {metrics['completed_tests']}건\n")
        f.write(f"실패한 변환:     {metrics['failed_tests']}건\n\n")
        
        f.write("-"*70 + "\n")
        f.write("KTCC 성능 지표 (기준: 75% 이상)\n")
        f.write("-"*70 + "\n")
        f.write(f"Accuracy:   {metrics['accuracy']:.2f}%  {'✅' if metrics['accuracy'] >= 75 else '❌'}\n")
        f.write(f"Precision:  {metrics['precision']:.2f}%  {'✅' if metrics['precision'] >= 75 else '❌'}\n")
        f.write(f"Recall:     {metrics['recall']:.2f}%  {'✅' if metrics['recall'] >= 75 else '❌'}\n")
        f.write(f"F1-Score:   {metrics['f1_score']:.2f}%  {'✅' if metrics['f1_score'] >= 75 else '❌'}\n\n")
        
        f.write("-"*70 + "\n")
        f.write("처리 시간\n")
        f.write("-"*70 + "\n")
        f.write(f"생성시간:   {metrics['avg_processing_time']:.2f}초  {'✅' if metrics['avg_processing_time'] <= 60 else '❌'} (기준: 60초)\n")
        f.write(f"반응시간:   {metrics['avg_total_time']:.2f}초  {'✅' if metrics['avg_total_time'] <= 1 else '❌'} (기준: 1초)\n\n")
        
        f.write("="*70 + "\n")
        f.write("최종 결과\n")
        f.write("="*70 + "\n")
        
        if metrics['all_passed']:
            f.write("✅ 모든 KTCC/KOLAS 기준을 통과했습니다.\n")
        else:
            f.write("❌ 일부 기준을 통과하지 못했습니다.\n")
    
    print(f"\n✅ 리포트 생성 완료: {report_file}")
    print(f"   파일 위치: {os.path.abspath(report_file)}")

def main():
    """메인 함수"""
    import sys
    
    print("\n" + "="*70)
    print("🔧 VModel AI 테스터 독립 검증 도구")
    print("   KTCC/KOLAS 인증 기준 준수")
    print("="*70)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--metrics":
            calculate_ktcc_metrics()
        elif command == "--logs":
            show_raw_logs()
        elif command == "--summary":
            show_success_summary()
        elif command == "--details":
            show_task_details()
        elif command == "--export":
            export_report()
        elif command == "--all":
            calculate_ktcc_metrics()
            show_success_summary()
            show_task_details()
        else:
            print("\n사용법:")
            print("  python tester_verification.py [옵션]")
            print("\n옵션:")
            print("  --metrics   : KTCC 성능 지표 계산")
            print("  --logs      : 원본 로그 표시")
            print("  --summary   : 성공/실패 요약")
            print("  --details   : Task ID별 상세 정보")
            print("  --export    : 검증 결과 텍스트 파일로 내보내기")
            print("  --all       : 전체 검증 (metrics + summary + details)")
            print("\n옵션 없이 실행하면 기본 검증(--metrics + --summary)을 수행합니다.")
    else:
        # 기본 검증 실행
        calculate_ktcc_metrics()
        show_success_summary()

if __name__ == "__main__":
    main()
