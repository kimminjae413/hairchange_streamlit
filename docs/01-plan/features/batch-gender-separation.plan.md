# Plan: 배치 변환 남/여 완전 분리

## 1. 개요

### 1.1 요구사항
- 배치 변환 기능의 남/여 로직이 뒤죽박죽 → 완전 분리
- 여성: **길이(A~H) × 각도** 축
- 남성: **스타일(SF/SP/FU/PB/BZ/CP/MC) × 각도** 축

### 1.2 현재 문제점
1. `LENGTH_CATEGORIES = MALE_LENGTH_CATEGORIES`(688줄) 고정 → 여성 선택해도 남성 길이 표시
2. `selected_lengths`에 남성 스타일 코드(SF,SP)와 여성 길이(A~H) 혼용 → KeyError 가능
3. `FEMALE_LENGTH_CATEGORIES` 정의만 있고 UI에서 미사용
4. `FEMALE_LENGTH_TRANSFORM_RULES` 미적용 → 불가능한 변환 선택 가능
5. 결과 그리드에서 `LENGTH_CATEGORIES[length]` 직접 참조 → 남성 스타일 코드로 KeyError

---

## 2. 수정 파일

| 파일 | 수정 내용 |
|------|----------|
| `app.py` | `generate_batch_variations()` 함수 + 배치 탭 UI + 결과 그리드 |

---

## 3. 수정 범위

### 3.1 함수 수정 (1029~1094줄)
- `generate_batch_variations()`: `item_categories` 파라미터 추가
- `LENGTH_CATEGORIES[length]` → `item_categories.get(length, {})` 로 변경
- 남성일 때 progress 메시지: "스타일 변환 중: SIDE FRINGE"
- 여성일 때 progress 메시지: "길이 변환 중: Semi Long"

### 3.2 UI 수정 (2060~2440줄)
- 성별 선택을 col_left 최상단으로 이동
- **여성 경로**:
  - 원본 길이: `FEMALE_LENGTH_CATEGORIES` (A~H, 이름: Long A/B, Semi Long, Medium 등)
  - 변환 대상: `FEMALE_LENGTH_TRANSFORM_RULES`로 필터링
  - 추가 옵션: 앞머리(B0~B4) + 컬(Straight~Mix)
- **남성 경로**:
  - 원본 스타일: `MALE_STYLE_CATEGORIES` (SF/SP/FU/PB/BZ/CP/MC)
  - 변환 대상: `MALE_BANG_SWAP_RULES`의 `can_swap_to`로 필터링
  - 추가 옵션: 앞머리(B0~B4)
- 공통: 각도 선택 (0°~90°)

### 3.3 결과 그리드 수정 (2363~2440줄)
- 여성: 행 = 길이명(FEMALE_LENGTH_CATEGORIES), 열 = 각도
- 남성: 행 = 스타일명(MALE_STYLE_CATEGORIES), 열 = 각도
- `LENGTH_CATEGORIES[length]` → 성별별 카테고리 dict 사용

---

## 4. 영향 분석
- `generate_length_variation()`(700줄): 수정 불필요 — 이미 내부에서 남/여 분기 처리
- `generate_angle_variation()`(948줄): 수정 불필요 — 성별 무관
- 다른 탭 (시드 관리, 헤어 변경, 처리 기록): 영향 없음

---

## 5. 테스트
- [ ] 여성 선택 시 FEMALE_LENGTH_CATEGORIES 표시
- [ ] 남성 선택 시 MALE_STYLE_CATEGORIES 표시
- [ ] 여성: 변환 규칙 외 길이 선택 불가
- [ ] 남성: swap 규칙 외 스타일 선택 불가
- [ ] 배치 실행 후 결과 그리드에 올바른 이름 표시
- [ ] ZIP 다운로드 정상
