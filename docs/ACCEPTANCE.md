# 적용 전에 채울 정보

| 정보 | 현재 가정 / 입력 위치 |
|---|---|
| 사내 Git 서비스 | GitHub Enterprise Server. GitLab/Gitea라면 API adapter 교체 필요 |
| GHES 버전 / Actions 사용 가능 여부 | 관리자 확인 필요 |
| 서버 OS / CPU / RAM / GPU·VRAM | Linux Runner 가정. 정확한 장비 확인 필요 |
| Python / Git | Python 3.10+, Git 2.50+ |
| 모델 실행기 | Ollama. 다른 런타임이면 llm.py adapter 변경 |
| 모델 태그 | gemma3:4b 기본. 장비·지연시간에 따라 확정 |
| 실제 Git URL/조직/저장소 | config의 github_server_url, github_api_url, allowed_repositories |
| 개발자 author 이메일 | baseline의 owners; 공동 개발자는 여러 개 등록 |
| baseline 등록 담당자 | 관리 권한 분리 필요 |
| 테스트 실행 명령 / CI 이름 | 제품별 실제 빌드·회귀 테스트를 별도 필수 check로 설정 |
| 충돌 처리 정책 | 최신 대상 구간 유지 + 내 비충돌 변경을 새 폴더에 적용 |
| 후보 패치 보관/다운로드 위치 | Runner의 reports_dir, 회사 내부 파일 전송 절차 |
| 사내 CA / 네트워크 허용 | GHES HTTPS, 로컬/내부 Ollama만 허용 |

## 인수 테스트

| 시나리오 | 기대 결과 |
|---|---|
| A/B가 같은 main에서 분기, 같은 파일의 멀리 떨어진 줄 수정 | PASS, A/B 둘 다 보존 |
| A main 반영 후 B가 동일 구간 수정 | BLOCK, 후보에는 A + B 비충돌 구간 |
| B가 최신 main 받은 뒤 옛 파일 복사로 A 변경 원복 | Git clean이어도 BASE_CHANGE_LOSS BLOCK |
| B가 dev를 feature에 merge | FOREIGN_MERGE 또는 FOREIGN_COMMITS BLOCK |
| 기준점 미등록 또는 다른 repository/branch 기록 | BLOCK 또는 실행 오류, 통과 status 없음 |
| 삭제/수정 충돌 | BLOCK, 구조적 충돌 후보 없음 |
| main이 분석 중 갱신됨 | error / 재검사 필요 |
| main이 PASS 이후 갱신됨 | up-to-date 보호 규칙으로 병합 제한, push 재검사 |
| prepare 전에 head/base 변경 | 적용 거부 |
| 후보 패치 변조 | checksum 불일치로 적용 거부 |
| Gemma 미실행/timeout/이상 JSON | Git 판정 유지, 설명 실패 표시 |
| dev/qa PR과 main PR이 같은 HEAD | dev/qa 보고서가 main status를 덮어쓰지 않음 |
| PR 파일명에 HTML/모델 지시 포함 | 보고서 escape, 모델이 gate/패치 변경 못함 |
| 사내 인터넷 차단 상태 | Git 로컬 검사 + 로컬 Gemma 설명 가능 |

실제 검증 결과와 버전은 운영자가 기록합니다. 저장소의 자동 테스트는 합성 Git 이력을 검증하며, 실제 GitHub API/GHES Runner·Gemma 모델 추론·제품 기능 테스트의 통과를 의미하지 않습니다.
