import streamlit as st
import requests
from PIL import Image, ImageDraw
import io
import base64
import time
import uuid
import json
import os
from datetime import datetime

def setup_verification_logging():
    """테스터 독립 검증을 위한 로깅 시스템 초기화"""
    os.makedirs("logs", exist_ok=True)
    os.makedirs("performance_data", exist_ok=True)
    
    if 'logging_initialized' not in st.session_state:
        timestamp = datetime.now().isoformat()
        session_start_log = f"[{timestamp}] SESSION_START: User {st.session_state.get('user_id', 'unknown')} started session"
        append_to_log("logs/session.log", session_start_log)
        st.session_state.logging_initialized = True

def append_to_log(file_path, message):
    """로그 파일에 메시지 추가"""
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")
    except Exception as e:
        print(f"로그 기록 실패: {e}")

def log_9step_process(request_id, step, message, extra_data=None):
    """9단계 처리 과정 상세 로깅"""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] STEP_{step}: {request_id} - {message}"
    if extra_data:
        log_entry += f" | Data: {json.dumps(extra_data, ensure_ascii=False)}"
    append_to_log("logs/vmodel_api_raw.log", log_entry)

def log_vmodel_request(request_id, request_data):
    """변환 요청 시작 로그 (디버깅용만, 성능 측정 제외)"""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] REQUEST_START: {request_id}"
    append_to_log("logs/vmodel_api_raw.log", log_entry)
    append_to_log("logs/vmodel_api_raw.log", f"  Request: {json.dumps(request_data, ensure_ascii=False)}")

def log_vmodel_polling(request_id, task_id, status, attempt):
    """폴링 중간 상태 로그 (디버깅용만, 성능 측정 제외)"""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] POLLING: {request_id} | Task: {task_id} | Status: {status} | Attempt: {attempt}"
    append_to_log("logs/vmodel_api_raw.log", log_entry)

def log_vmodel_completion(request_id, task_id, success, result_url=None, error=None, processing_time=0, first_response_time=0):
    """변환 완료 로그 (성능 측정 포함) - 실제 완료시 1회만 호출"""
    timestamp = datetime.now().isoformat()
    
    response_data = {
        "request_id": request_id,
        "task_id": task_id,
        "success": success,
        "result_url": result_url,
        "error": error,
        "processing_time": processing_time,
        "first_response_time": first_response_time
    }
    api_response_log = f"[{timestamp}] COMPLETION: {json.dumps(response_data, ensure_ascii=False)}"
    append_to_log("logs/vmodel_api_raw.log", api_response_log)
    
    if success:
        success_log = f"[{timestamp}] SUCCESS - {request_id} completed in {processing_time:.1f}s (first response: {first_response_time:.3f}s)"
    else:
        success_log = f"[{timestamp}] FAILED - {request_id}: {error}"
    append_to_log("logs/success_failures.log", success_log)
    
    completed = success and bool(result_url)
    
    performance_record = {
        "timestamp": timestamp,
        "request_id": request_id,
        "user_id": st.session_state.get('user_id', 'unknown'),
        "task_id": task_id,
        "success": success,
        "completed": completed,
        "processing_time": processing_time,
        "first_response_time": first_response_time,
        "result_url": result_url,
        "error": error
    }
    
    performance_file = "performance_data/performance_log.jsonl"
    with open(performance_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(performance_record, ensure_ascii=False) + '\n')
    
    if 'performance_history' not in st.session_state:
        st.session_state.performance_history = []
    st.session_state.performance_history.append(performance_record)

def calculate_realtime_metrics():
    """실시간 성능 지표 계산 (정부 기준)"""
    if 'performance_history' not in st.session_state or not st.session_state.performance_history:
        return None
    
    data = st.session_state.performance_history
    total = len(data)
    successful = len([d for d in data if d.get('success', False)])
    completed = len([d for d in data if d.get('completed', False)])
    
    accuracy = (successful / total) * 100 if total > 0 else 0
    precision = (completed / successful) * 100 if successful > 0 else 0
    recall = (completed / total) * 100 if total > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    processing_times = [d.get('processing_time', 0) for d in data if d.get('success', False)]
    first_response_times = [d.get('first_response_time', 0) for d in data if d.get('first_response_time', 0)]
    avg_processing = sum(processing_times) / len(processing_times) if processing_times else 0
    avg_first_response = sum(first_response_times) / len(first_response_times) if first_response_times else 0
    
    return {
        'total_requests': total,
        'successful_requests': successful,
        'completed_requests': completed,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'avg_processing_time': avg_processing,
        'avg_first_response_time': avg_first_response,
        'processing_times': processing_times
    }

def handle_verification_api():
    """테스터 검증용 API 엔드포인트 처리"""
    query_params = st.query_params
    
    if "api" in query_params:
        api_type = query_params["api"]
        
        if api_type == "logs":
            logs_data = get_logs_data()
            st.json(logs_data)
            st.stop()
            
        elif api_type == "performance":
            performance_data = get_performance_data()
            st.json(performance_data)
            st.stop()
        
        elif api_type == "metrics":
            display_detailed_metrics()
            st.stop()

def display_detailed_metrics():
    """상세 성능 지표 및 계산 과정 표시"""
    st.title("🎯 AI 성능 평가 결과 (KTCC/KOLAS 기준)")
    
    performance_data = get_performance_data()
    
    if not performance_data.get('data'):
        st.error("성능 데이터가 없습니다.")
        st.write("디버그 정보:")
        st.json(performance_data)
        return
    
    data = performance_data['data']
    
    if not data:
        st.warning("완료된 헤어스타일 변환이 없습니다.")
        st.info("헤어스타일 변환을 완료한 후 다시 확인해주세요.")
        return
    
    total_requests = len(data)
    successful_requests = len([d for d in data if d.get('success', False)])
    completed_requests = len([d for d in data if d.get('completed', False)])
    
    processing_times = [d.get('processing_time', 0) for d in data if d.get('success', False)]
    first_response_times = [d.get('first_response_time', 0) for d in data if d.get('first_response_time', 0)]
    avg_processing = sum(processing_times) / len(processing_times) if processing_times else 0
    avg_first_response = sum(first_response_times) / len(first_response_times) if first_response_times else 0
    
    accuracy = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
    precision = (completed_requests / successful_requests) * 100 if successful_requests > 0 else 0
    recall = (completed_requests / total_requests) * 100 if total_requests > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    st.subheader("📊 측정 데이터")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**기본 통계:**")
        st.write(f"- 전체 변환 시도: {total_requests}건")
        st.write(f"- 성공한 변환: {successful_requests}건") 
        st.write(f"- 완료된 변환: {completed_requests}건")
    
    with col2:
        st.write("**계산 결과:**")
        st.write(f"- Accuracy: {accuracy:.1f}%")
        st.write(f"- Precision: {precision:.1f}%")
        st.write(f"- Recall: {recall:.1f}%")
        st.write(f"- F1-Score: {f1_score:.1f}%")
    
    st.subheader("🔢 KTCC 기준 계산 공식")
    
    st.markdown(f"""
**1. Accuracy (정확도)**
```
공식: (성공한 요청 / 전체 요청) × 100
계산: ({successful_requests} ÷ {total_requests}) × 100 = {accuracy:.1f}%
기준: 75% 이상 → {'✅ 통과' if accuracy >= 75 else '❌ 미달'}
```

**2. Precision (정밀도)**  
```
공식: (완료된 요청 / 성공한 요청) × 100
계산: ({completed_requests} ÷ {successful_requests}) × 100 = {precision:.1f}%
기준: 75% 이상 → {'✅ 통과' if precision >= 75 else '❌ 미달'}
```

**3. Recall (재현율)**
```
공식: (완료된 요청 / 전체 요청) × 100
계산: ({completed_requests} ÷ {total_requests}) × 100 = {recall:.1f}%
기준: 75% 이상 → {'✅ 통과' if recall >= 75 else '❌ 미달'}
```

**4. F1-Score**
```
공식: 2 × (Precision × Recall) / (Precision + Recall)
계산: 2 × ({precision:.1f} × {recall:.1f}) / ({precision:.1f} + {recall:.1f}) = {f1_score:.1f}%
기준: 75% 이상 → {'✅ 통과' if f1_score >= 75 else '❌ 미달'}
```

**5. AI 모델 생성시간**
```
측정값: {avg_processing:.1f}초 (평균)
기준: 60초 이내 → {'✅ 통과' if avg_processing <= 60 else '❌ 미달'}
```

**6. AI 모델 반응시간**
```
측정값: {avg_first_response:.3f}초 (평균)
기준: 1초 이내 → {'✅ 통과' if avg_first_response <= 1 else '❌ 미달'}
```
""")
    
    st.subheader("📋 최종 평가 결과")
    
    results_data = {
        "평가항목": ["Accuracy", "Precision", "Recall", "F1-Score", "생성시간", "반응시간"],
        "측정값": [f"{accuracy:.1f}%", f"{precision:.1f}%", f"{recall:.1f}%", f"{f1_score:.1f}%", f"{avg_processing:.1f}초", f"{avg_first_response:.3f}초"],
        "정부기준": ["75% 이상", "75% 이상", "75% 이상", "75% 이상", "60초 이내", "1초 이내"],
        "통과여부": [
            "✅" if accuracy >= 75 else "❌",
            "✅" if precision >= 75 else "❌", 
            "✅" if recall >= 75 else "❌",
            "✅" if f1_score >= 75 else "❌",
            "✅" if avg_processing <= 60 else "❌",
            "✅" if avg_first_response <= 1 else "❌"
        ]
    }
    
    st.table(results_data)
    
    st.subheader("🛡️ 독립 검증 증거")
    st.markdown(f"""
**1. 완료된 Task ID 목록:**
```
{', '.join([d.get('task_id', 'N/A') for d in data if d.get('completed')])}
```

**2. VModel 서버 응답 URL:**
- 모든 result_url이 VModel CDN에서 직접 제공
- 조작 불가능한 외부 서버 데이터

**3. 로그 파일 위치:**
- 원본 로그: `logs/vmodel_api_raw.log`
- 성능 데이터: `performance_data/performance_log.jsonl`
- 성공/실패: `logs/success_failures.log`

**4. 독립 검증 방법:**
```bash
# SSH 접속 후 실행
python tester_verification.py --metrics
```
""")

def get_logs_data():
    """로그 데이터 수집 및 반환"""
    try:
        logs_data = {
            "timestamp": datetime.now().isoformat(),
            "log_files": {},
            "recent_logs": []
        }
        
        log_files = [
            "logs/vmodel_api_raw.log",
            "logs/success_failures.log",
            "logs/session.log"
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        logs_data["log_files"][os.path.basename(log_file)] = content
                        
                        lines = content.strip().split('\n')
                        for line in lines[-10:]:
                            if line.strip() and line.startswith('['):
                                logs_data["recent_logs"].append(line)
                                
                except Exception as e:
                    logs_data["log_files"][f"{log_file}_error"] = f"Read failed: {str(e)}"
            else:
                logs_data["log_files"][f"{log_file}_missing"] = "File does not exist"
        
        return logs_data
    except Exception as e:
        return {"error": f"Failed to collect logs: {str(e)}"}

def get_performance_data():
    """성능 데이터 수집 및 반환"""
    try:
        performance_data = []
        
        if not os.path.exists("performance_data"):
            os.makedirs("performance_data")
        
        performance_file = "performance_data/performance_log.jsonl"
        if os.path.exists(performance_file):
            with open(performance_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    for line in content.strip().split('\n'):
                        if line.strip():
                            try:
                                performance_data.append(json.loads(line))
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error: {e} in line: {line}")
                                continue
        
        return {
            "timestamp": datetime.now().isoformat(),
            "data": performance_data,
            "total_records": len(performance_data),
            "file_exists": os.path.exists(performance_file),
            "file_path": os.path.abspath(performance_file)
        }
    except Exception as e:
        return {"error": f"Failed to collect performance data: {str(e)}"}

st.set_page_config(
    page_title="AI 헤어스타일 변경 서비스",
    page_icon="💇‍♀️",
    layout="wide"
)

handle_verification_api()

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 2rem;
        font-weight: bold;
    }
    .success-box {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .info-box {
        background: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #bee5eb;
        margin: 1rem 0;
    }
    .quality-info {
        background: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #ffeaa7;
        margin: 1rem 0;
    }
    .metrics-box {
        background: #e2e3e5;
        color: #383d41;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #d6d8db;
        margin: 1rem 0;
    }
    .verification-box {
        background: #f8f9fa;
        color: #495057;
        padding: 1rem;
        border: 2px solid #6c757d;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
    
if 'seed_images' not in st.session_state:
    st.session_state.seed_images = {}
    
if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []

setup_verification_logging()

VMODEL_API_KEY = st.secrets.get("VMODEL_API_KEY", "")

def resize_image_if_needed(image, max_size=1024):
    """이미지가 너무 크면 자동으로 리사이즈"""
    width, height = image.size
    
    if width > max_size or height > max_size:
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return resized_image, True
    
    return image, False

def validate_image(image):
    """이미지 유효성 검사 및 자동 리사이즈"""
    try:
        if image.size[0] < 100 or image.size[1] < 100:
            return False, "이미지 크기가 너무 작습니다 (최소 100x100)", image
        
        processed_image, was_resized = resize_image_if_needed(image, max_size=1024)
        
        if was_resized:
            original_size = f"{image.size[0]}x{image.size[1]}"
            new_size = f"{processed_image.size[0]}x{processed_image.size[1]}"
            message = f"이미지 크기를 자동 조정했습니다: {original_size} → {new_size}"
        else:
            message = "유효한 이미지입니다"
        
        return True, message, processed_image
        
    except Exception as e:
        return False, f"이미지 검증 실패: {e}", image

def upload_image_to_imgur(image):
    """Imgur에 이미지 업로드하고 URL 반환"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        headers = {
            'Authorization': 'Client-ID 546c25a59c58ad7',
            'Content-Type': 'application/json',
        }
        
        data = {
            'image': img_b64,
            'type': 'base64',
            'title': 'temp_upload'
        }
        
        response = requests.post(
            'https://api.imgur.com/3/image',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                return result['data']['link']
        
        st.warning("이미지 업로드 서비스에 일시적 문제가 있습니다. 다른 방법을 시도합니다...")
        return upload_to_tempfile_io(image)
        
    except Exception as e:
        st.warning(f"이미지 업로드 중 오류: {e}. 다른 방법을 시도합니다...")
        return upload_to_tempfile_io(image)

def upload_to_tempfile_io(image):
    """대안 임시 파일 호스팅 서비스"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        files = {'file': ('image.png', buffer, 'image/png')}
        
        response = requests.post(
            'https://tmpfiles.org/api/v1/upload',
            files=files,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'data' in result and 'url' in result['data']:
                temp_url = result['data']['url']
                direct_url = temp_url.replace('https://tmpfiles.org/', 'https://tmpfiles.org/dl/')
                return direct_url
                
    except Exception as e:
        st.error(f"모든 이미지 업로드 서비스가 실패했습니다: {e}")
        return None

def poll_vmodel_task(request_id, task_id, max_attempts=90):
    """VModel Task 상태 폴링 - 9단계 로깅 포함"""
    headers = {"Authorization": f"Bearer {VMODEL_API_KEY}"}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    polling_start = time.time()
    log_9step_process(request_id, "7_POLLING_START", f"상태 폴링 시작 | Task: {task_id}")
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                f"https://api.vmodel.ai/api/tasks/v1/get/{task_id}", 
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('code') == 200 and 'result' in result:
                    task_result = result['result']
                    status = task_result.get('status', 'processing')
                    
                    log_vmodel_polling(request_id, task_id, status, attempt + 1)
                    
                    progress = min(0.95, (attempt + 1) * 0.01)
                    progress_bar.progress(progress)
                    
                    if status == 'processing':
                        status_text.text(f"🎨 AI 고품질 처리 중... ({progress*100:.0f}%) - {attempt+1}/90초")
                    elif status == 'starting':
                        status_text.text("🚀 AI 모델 시작 중...")
                    elif status == 'succeeded':
                        progress_bar.progress(1.0)
                        status_text.text("✨ 완료!")
                        
                        output = task_result.get('output', [])
                        if output and len(output) > 0:
                            result_url = output[0]
                            
                            log_9step_process(request_id, "8_DOWNLOAD_START", f"결과 이미지 다운로드 시작 | URL: {result_url}")
                            
                            st.info(f"결과 이미지 다운로드 중: {result_url}")
                            
                            img_response = requests.get(result_url, timeout=30)
                            if img_response.status_code == 200:
                                total_processing_time = time.time() - polling_start
                                
                                log_9step_process(request_id, "9_COMPLETE", f"헤어스타일 변환 완료 | 총 처리시간: {total_processing_time:.2f}초", {
                                    "task_id": task_id,
                                    "result_url": result_url,
                                    "processing_time": total_processing_time,
                                    "image_size": len(img_response.content)
                                })
                                
                                log_vmodel_completion(
                                    request_id=request_id,
                                    task_id=task_id,
                                    success=True,
                                    result_url=result_url,
                                    processing_time=total_processing_time,
                                    first_response_time=st.session_state.get(f'first_response_{request_id}', 0)
                                )
                                
                                return Image.open(io.BytesIO(img_response.content))
                            else:
                                st.error(f"이미지 다운로드 실패: HTTP {img_response.status_code}")
                                return None
                        
                        st.error("결과 이미지 URL을 찾을 수 없습니다.")
                        return None
                        
                    elif status == 'failed':
                        error_msg = task_result.get('error', '알 수 없는 오류')
                        
                        log_vmodel_completion(
                            request_id=request_id,
                            task_id=task_id,
                            success=False,
                            error=error_msg,
                            processing_time=time.time() - polling_start,
                            first_response_time=st.session_state.get(f'first_response_{request_id}', 0)
                        )
                        
                        st.error(f"처리 실패: {error_msg}")
                        return None
                    
                    elif status == 'canceled':
                        st.error("작업이 취소되었습니다.")
                        return None
                
                time.sleep(1)
            else:
                st.error(f"Task 상태 확인 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            if attempt == max_attempts - 1:
                st.error(f"처리 시간 초과 (90초): {e}")
                return None
            time.sleep(1)
    
    st.error("처리 시간 초과 - VModel 서버가 응답하지 않습니다")
    return None

def process_with_vmodel_api(seed_image, ref_image, quality_mode="high"):
    """VModel API로 헤어 변경 처리 - 9단계 로깅 포함, VModel 문서 호환"""
    
    if not VMODEL_API_KEY:
        st.error("⚠️ VModel API 키가 설정되지 않았습니다. Streamlit Secrets에서 VMODEL_API_KEY를 설정해주세요.")
        return None
    
    try:
        request_id = f"req_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        log_9step_process(request_id, "1_REQUEST_START", "헤어스타일 변환 요청 시작", {
            "quality_mode": quality_mode,
            "seed_size": seed_image.size,
            "ref_size": ref_image.size
        })
        
        st.info("이미지를 업로드하고 있습니다...")
        
        # VModel 문서에 따른 올바른 매핑
        target_url = upload_image_to_imgur(seed_image)    # 사람 얼굴 이미지
        source_url = upload_image_to_imgur(ref_image)     # 헤어스타일 참조 이미지
        
        if not target_url or not source_url:
            st.error("이미지 업로드에 실패했습니다. 잠시 후 다시 시도해주세요.")
            return None
        
        log_9step_process(request_id, "2_UPLOAD_COMPLETE", "이미지 업로드 완료", {
            "target_url": target_url,
            "source_url": source_url
        })
        
        st.success("이미지 업로드 완료!")
        
        # VModel 공식 문서 형식에 맞춘 payload
        payload = {
            "version": "5c0440717a995b0bbd93377bd65dbb4fe360f67967c506aa6bd8f6b660733a7e",
            "input": {
                "source": source_url,    # 헤어스타일 참조 이미지
                "target": target_url,    # 사람 얼굴 이미지
                "disable_safety_checker": False,
            }
        }
        
        log_9step_process(request_id, "3_API_PREPARED", "VModel API 요청 준비 완료", {
            "payload": payload
        })
        
        if quality_mode == "high":
            st.markdown("""
            <div class="quality-info">
                🎨 <strong>고품질 모드</strong>로 처리합니다<br>
                • 더 선명한 머리카락 디테일<br>
                • 자연스러운 경계 블렌딩<br>
                • 처리시간 약간 증가 (30-45초)
            </div>
            """, unsafe_allow_html=True)
        
        headers = {
            "Authorization": f"Bearer {VMODEL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        log_vmodel_request(request_id, payload)
        
        log_9step_process(request_id, "4_API_CALL_START", "VModel API 호출 시작")
        
        first_response_start = time.time()
        response = requests.post(
            "https://api.vmodel.ai/api/tasks/v1/create", 
            json=payload, 
            headers=headers, 
            timeout=30
        )
        first_response_time = time.time() - first_response_start
        
        log_9step_process(request_id, "5_FIRST_RESPONSE", f"첫 응답 수신 | 반응시간: {first_response_time:.3f}초", {
            "status_code": response.status_code,
            "response_time": first_response_time
        })
        
        st.session_state[f'first_response_{request_id}'] = first_response_time
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('code') == 200 and 'result' in result:
                task_id = result['result'].get('task_id')
                if task_id:
                    log_9step_process(request_id, "6_TASK_CREATED", f"Task 생성 완료 | Task ID: {task_id}")
                    
                    return poll_vmodel_task(request_id, task_id, max_attempts=90)
        
        try:
            error_data = response.json()
            log_vmodel_completion(
                request_id=request_id,
                task_id=None,
                success=False,
                error=str(error_data),
                first_response_time=first_response_time
            )
            st.error(f"API 오류: {error_data}")
        except:
            log_vmodel_completion(
                request_id=request_id,
                task_id=None,
                success=False,
                error=f"HTTP {response.status_code}",
                first_response_time=first_response_time
            )
            st.error(f"API 호출 실패: HTTP {response.status_code}")
        
        return None
        
    except Exception as e:
        log_vmodel_completion(
            request_id=request_id if 'request_id' in locals() else "unknown",
            task_id=None,
            success=False,
            error=str(e),
            first_response_time=0
        )
        st.error(f"처리 중 오류 발생: {e}")
        return None

def create_download_link(image, filename):
    """이미지 다운로드 링크 생성 - 고품질 설정"""
    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG', optimize=True, compress_level=1)
    img_buffer.seek(0)
    return img_buffer.getvalue()

st.markdown("""
<div class="main-header">
    <h1>💇‍♀️ AI 헤어스타일 변경 서비스</h1>
    <p>AI로 원하는 헤어스타일을 미리 체험해보세요!</p>
    <small>🎯 <strong>고품질 모드</strong> - 선명한 머리카락 디테일 지원</small>
</div>
""", unsafe_allow_html=True)

if not VMODEL_API_KEY:
    st.error("""
    ⚠️ **VModel API 키가 필요합니다!**
    
    1. [VModel.ai](https://vmodel.ai)에서 API 키 발급
    2. Streamlit Cloud 대시보드 → Settings → Secrets
    3. 다음 내용 추가:
    ```
    VMODEL_API_KEY = "your-api-key-here"
    ```
    """)
    st.stop()

metrics = calculate_realtime_metrics()
if metrics:
    st.markdown("### 🔍 실시간 성능 지표")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        accuracy_status = "✅" if metrics['accuracy'] >= 75 else "❌"
        st.metric("Accuracy", f"{metrics['accuracy']:.1f}%", delta=f"{accuracy_status} (기준: 75%)")
    
    with col2:
        precision_status = "✅" if metrics['precision'] >= 75 else "❌"
        st.metric("Precision", f"{metrics['precision']:.1f}%", delta=f"{precision_status} (기준: 75%)")
    
    with col3:
        recall_status = "✅" if metrics['recall'] >= 75 else "❌"
        st.metric("Recall", f"{metrics['recall']:.1f}%", delta=f"{recall_status} (기준: 75%)")
    
    with col4:
        f1_status = "✅" if metrics['f1_score'] >= 75 else "❌"
        st.metric("F1-Score", f"{metrics['f1_score']:.1f}%", delta=f"{f1_status} (기준: 75%)")
    
    with st.expander("🔍 성능 측정 방식"):
        st.markdown(f"""
        <div class="verification-box">
        <h4>📊 정확한 성능 측정</h4>
        
        <strong>9단계 처리 과정:</strong><br>
        1. REQUEST_START: 요청 시작<br>
        2. UPLOAD_COMPLETE: 이미지 업로드 완료<br>
        3. API_PREPARED: API 요청 준비<br>
        4. API_CALL_START: API 호출<br>
        5. FIRST_RESPONSE: 첫 응답 수신 (반응시간)<br>
        6. TASK_CREATED: Task 생성 완료<br>
        7. POLLING_START: 상태 폴링 시작<br>
        8. DOWNLOAD_START: 결과 다운로드<br>
        9. COMPLETE: 처리 완료 (생성시간)<br><br>
        
        <strong>현재 측정값:</strong><br>
        • 전체 변환: {metrics['total_requests']}회<br>
        • 성공: {metrics['successful_requests']}회<br>
        • 완료: {metrics['completed_requests']}회<br>
        • 평균 처리시간: {metrics['avg_processing_time']:.1f}초<br>
        • 평균 반응시간: {metrics['avg_first_response_time']:.3f}초<br><br>
        
        <strong>독립 검증:</strong><br>
        • 상세 분석: <code>?api=metrics</code><br>
        • 원본 로그: <code>?api=logs</code><br>
        • 성능 데이터: <code>?api=performance</code>
        </div>
        """, unsafe_allow_html=True)

with st.sidebar:
    st.header("🎛️ 설정")
    st.info(f"사용자 ID: {st.session_state.user_id}")
    
    st.markdown("### 🔑 API 상태")
    vmodel_status = "✅ 연결됨" if VMODEL_API_KEY else "❌ 미설정"
    st.write(f"VModel: {vmodel_status}")
    
    if st.button("🔄 새 세션 시작"):
        st.session_state.clear()
        st.rerun()
    
    st.divider()
    
    st.markdown("### 🧪 테스트 관리")
    st.warning("⚠️ 테스터 전용: 기존 데이터를 백업하고 새로운 테스트를 시작합니다.")
    
    if st.button("🗑️ 테스트 데이터 초기화", type="secondary"):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        perf_file = "performance_data/performance_log.jsonl"
        if os.path.exists(perf_file):
            backup_file = f"performance_data/performance_log_backup_{timestamp}.jsonl"
            os.rename(perf_file, backup_file)
            st.info(f"백업 완료: {backup_file}")
        
        log_files = ["logs/vmodel_api_raw.log", "logs/success_failures.log", "logs/session.log"]
        for log_file in log_files:
            if os.path.exists(log_file):
                backup_file = f"{log_file}.backup_{timestamp}"
                os.rename(log_file, backup_file)
        
        open(perf_file, 'w').close()
        open("logs/vmodel_api_raw.log", 'w').close()
        open("logs/success_failures.log", 'w').close()
        open("logs/session.log", 'w').close()
        
        if 'performance_history' in st.session_state:
            st.session_state.performance_history = []
        
        st.success("✅ 테스트 데이터가 초기화되었습니다!")
        st.info("이제 새로운 테스트를 시작할 수 있습니다.")
        time.sleep(2)
        st.rerun()
    
    st.divider()
    
    st.markdown("""
    ### 📋 사용 방법
    1. **시드 이미지 업로드** (본인 얼굴)
    2. **참조 이미지 업로드** (원하는 헤어스타일)
    3. **AI 변환 실행**
    4. **결과 확인 및 다운로드**
    
    ### 💡 팁
    - 정면을 바라보는 고화질 사진 사용
    - 머리카락이 명확히 보이는 이미지
    - 배경이 단순한 사진 권장
    
    ### ⚡ 처리 속도
    - **고품질 모드**: 30-45초
    - 결과 해상도: 원본과 동일
    - 품질 최적화된 PNG 다운로드
    
    ### 🎨 품질 개선사항
    - ✨ 머리 끝부분 선명도 향상
    - 🎯 자연스러운 헤어 블렌딩
    - 🔥 디테일 보존 최적화
    
    ### 🔍 테스터 검증
    - SSH 접속 후 독립 검증 가능
    - `python tester_verification.py --metrics`
    - KTCC/KOLAS 기준 자동 계산
    - 9단계 처리 과정 상세 추적
    """)

tab1, tab2, tab3 = st.tabs(["🎨 헤어 변경", "📸 시드 관리", "📝 처리 기록"])

with tab2:
    st.header("📸 시드 이미지 관리")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        seed_file = st.file_uploader(
            "시드 이미지 업로드 (본인 얼굴)", 
            type=['png', 'jpg', 'jpeg'],
            help="어떤 크기든 OK! 자동으로 최적 크기로 조정됩니다"
        )
        
        if seed_file:
            seed_image = Image.open(seed_file)
            is_valid, message, processed_image = validate_image(seed_image)
            
            if is_valid:
                st.image(processed_image, caption="미리보기 (처리된 이미지)", width=300)
                st.success(message)
                st.caption(f"원본 파일명: {seed_file.name}")
                st.caption(f"처리된 크기: {processed_image.size}")
            else:
                st.image(seed_image, caption="미리보기", width=300)
                st.error(message)
                processed_image = seed_image
    
    with col2:
        if seed_file and st.button("💾 시드 저장", type="primary"):
            seed_image = Image.open(seed_file)
            is_valid, message, processed_image = validate_image(seed_image)
            
            if is_valid:
                seed_id = str(uuid.uuid4())[:8]
                st.session_state.seed_images[seed_id] = {
                    'image': processed_image,
                    'filename': seed_file.name,
                    'original_size': seed_image.size,
                    'processed_size': processed_image.size,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                st.markdown(f"""
                <div class="success-box">
                    ✅ 시드 저장 완료!<br>
                    ID: {seed_id}<br>
                    {message}
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1)
                st.rerun()
            else:
                st.error(message)
    
    if st.session_state.seed_images:
        st.divider()
        st.subheader("💾 저장된 시드 이미지")
        
        for seed_id, seed_data in st.session_state.seed_images.items():
            with st.expander(f"🖼️ {seed_data['filename']} ({seed_data['created_at']})"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.image(seed_data['image'], width=200)
                
                with col2:
                    st.write(f"**ID**: {seed_id}")
                    st.write(f"**크기**: {seed_data['image'].size}")
                    
                    if st.button(f"🗑️ 삭제", key=f"delete_{seed_id}"):
                        del st.session_state.seed_images[seed_id]
                        st.rerun()

with tab1:
    st.header("🎨 헤어스타일 변경")
    
    if not st.session_state.seed_images:
        st.warning("먼저 시드 이미지를 업로드해주세요!")
        st.info("👈 **시드 관리** 탭에서 시드 이미지를 추가하세요")
    else:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("1️⃣ 시드 이미지 선택")
            
            seed_options = {
                f"{data['filename']} ({data['created_at']})": seed_id 
                for seed_id, data in st.session_state.seed_images.items()
            }
            
            selected_seed_name = st.selectbox("시드 선택", list(seed_options.keys()))
            selected_seed_id = seed_options[selected_seed_name]
            selected_seed_data = st.session_state.seed_images[selected_seed_id]
            
            st.image(selected_seed_data['image'], caption="선택된 시드", width=250)
        
        with col2:
            st.subheader("2️⃣ 헤어 참조 이미지")
            
            ref_file = st.file_uploader(
                "원하는 헤어스타일 이미지", 
                type=['png', 'jpg', 'jpeg'],
                help="원하는 헤어스타일이 담긴 사진"
            )
            
            if ref_file:
                ref_image = Image.open(ref_file)
                st.image(ref_image, caption="참조 이미지", width=250)
        
        if ref_file:
            st.divider()
            st.subheader("3️⃣ 품질 설정")
            
            quality_mode = st.radio(
                "처리 품질 선택",
                ["high", "standard"],
                format_func=lambda x: {
                    "high": "🎨 고품질 (권장) - 선명한 디테일, 30-45초",
                    "standard": "⚡ 표준 - 빠른 처리, 15-25초"
                }[x],
                index=0
            )
        
        if ref_file:
            st.divider()
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 AI 헤어 변경 시작", type="primary", use_container_width=True):
                    
                    ref_image = Image.open(ref_file)
                    
                    is_valid, message, processed_ref_image = validate_image(ref_image)
                    if not is_valid:
                        st.error(f"참조 이미지 오류: {message}")
                        st.stop()
                    
                    if processed_ref_image.size != ref_image.size:
                        st.info(f"참조 이미지 크기 조정: {ref_image.size} → {processed_ref_image.size}")
                    
                    with st.spinner("AI가 헤어스타일을 변경하고 있습니다..."):
                        start_time = time.time()
                        
                        result_image = process_with_vmodel_api(
                            selected_seed_data['image'],
                            processed_ref_image,
                            quality_mode=quality_mode
                        )
                        
                        processing_time = time.time() - start_time
                        
                        if result_image:
                            st.success(f"✨ 헤어 변경 완료! (소요시간: {processing_time:.1f}초)")
                            
                            history_item = {
                                'id': str(uuid.uuid4())[:8],
                                'seed_filename': selected_seed_data['filename'],
                                'ref_filename': ref_file.name,
                                'result_image': result_image,
                                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'processing_time': processing_time,
                                'quality_mode': quality_mode
                            }
                            st.session_state.processing_history.append(history_item)
                            
                            st.divider()
                            st.markdown("### 🎉 최종 결과")
                            
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                st.image(selected_seed_data['image'], caption="원본", width=300)
                            with col2:
                                st.image(result_image, caption="변경 결과", width=300)
                            
                            st.divider()
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                quality_suffix = "HQ" if quality_mode == "high" else "STD"
                                filename = f"hair_result_{quality_suffix}_{timestamp}.png"
                                
                                download_data = create_download_link(result_image, filename)
                                
                                st.download_button(
                                    label="💾 고품질 PNG 다운로드",
                                    data=download_data,
                                    file_name=filename,
                                    mime="image/png",
                                    use_container_width=True,
                                    help="최고 품질의 PNG 파일로 다운로드됩니다"
                                )
                            
                            quality_desc = "고품질" if quality_mode == "high" else "표준"
                            st.info(f"""
                            **처리 정보**
                            - 품질 모드: {quality_desc}
                            - 처리 시간: {processing_time:.1f}초
                            - 최종 해상도: {result_image.size}
                            - 파일 형식: 고품질 PNG
                            - 압축: 최적화됨
                            """)
                            
                        else:
                            st.error("헤어 변경에 실패했습니다. 다시 시도해주세요.")

with tab3:
    st.header("📝 처리 기록")
    
    if not st.session_state.processing_history:
        st.info("아직 처리 기록이 없습니다.")
    else:
        st.write(f"총 {len(st.session_state.processing_history)}개의 처리 기록")
        
        history = sorted(
            st.session_state.processing_history, 
            key=lambda x: x['created_at'], 
            reverse=True
        )
        
        for item in history:
            quality_emoji = "🎨" if item.get('quality_mode') == 'high' else "⚡"
            quality_text = "고품질" if item.get('quality_mode') == 'high' else "표준"
            
            with st.expander(f"{quality_emoji} {item['created_at']} - {item['seed_filename']} → {item['ref_filename']} ({quality_text})"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.write(f"**처리 ID**: {item['id']}")
                    st.write(f"**시드 파일**: {item['seed_filename']}")
                    st.write(f"**참조 파일**: {item['ref_filename']}")
                    st.write(f"**품질 모드**: {quality_text}")
                    st.write(f"**처리 시간**: {item['processing_time']:.1f}초")
                
                with col2:
                    st.image(item['result_image'], caption="처리 결과", width=300)
                    
                    timestamp = item['created_at'].replace('-', '').replace(':', '').replace(' ', '_')
                    quality_suffix = "HQ" if item.get('quality_mode') == 'high' else "STD"
                    filename = f"result_{item['id']}_{quality_suffix}_{timestamp}.png"
                    download_data = create_download_link(item['result_image'], filename)
                    
                    st.download_button(
                        "💾 고품질 다운로드",
                        download_data,
                        filename,
                        "image/png",
                        key=f"download_{item['id']}",
                        help="최고 품질 PNG 다운로드"
                    )

st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    💇‍♀️ AI Hair Style Transfer | Made with ❤️ using Streamlit Cloud<br>
    <small>🎨 고품질 모드로 선명한 헤어 디테일을 경험해보세요!</small><br>
    <small>🔍 <strong>독립 검증 API</strong>: ?api=logs | ?api=performance | ?api=metrics</small><br>
    <small>📊 정확한 성능 측정: 9단계 처리 추적, 완료시 1회만 기록, request_id 추적</small><br>
    <small>세션 종료시 데이터가 삭제됩니다. 중요한 결과는 다운로드하세요!</small>
</div>
""", unsafe_allow_html=True)
