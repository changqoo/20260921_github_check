# 검사 구조와 한계

## 세 가지 입력

- `O`: 관리자 저장소에 등록한 개발 시작 SHA
- `T`: 현재 PR 대상 브랜치의 SHA
- `H`: 검사 대상 PR의 정확한 HEAD SHA

자동 병합 `M = merge(T,H)`는 Git이 계산한 실제 공통 조상을 사용합니다. 보호 후보 `P = merge(T,H, merge-base=O, -Xours)`는 시작점을 기준으로 다시 계산하며, 여기서 ours는 **첫 번째 인자인 대상 브랜치 T**입니다. `-s ours`는 사용하지 않습니다. `-Xours`는 일반적인 비충돌 변경을 보존하면서 충돌 구간만 대상 쪽으로 선택합니다.

별도로 `merge(T,H, merge-base=O)`를 실행해 `-Xours`가 숨긴 겹침을 보고합니다. `M`이 clean이고 `M.tree != P.tree`이면 기존 변경 손실 가능성으로 차단합니다. 예를 들어 `O: A=0, T: A=1, H: A=0`에서 H가 T를 이미 조상으로 가진다면 실제 merge는 A=0이지만 보호 후보는 A=1입니다.

O를 인위적 merge-base로 지정한 결과는 일반 Git merge의 정답이 아니라 **보수적인 정책 후보**입니다. 복잡한 이력·의도적인 재수정에서 정상 변경도 제외될 수 있습니다. 실제 충돌, 시작점 기준 충돌, 결과 차이를 모두 차단해 자동 승인하지 않습니다.

## 실행 경계

검사는 매번 새 bare 저장소로 커밋 객체를 가져옵니다. PR checkout, PR Python 코드, hooks, 설치 명령, 빌드, custom merge driver를 실행하지 않습니다. 전역 Git config 및 replace refs를 사용하지 않고 external diff/textconv를 끕니다. SHA-1과 표준 Git merge 동작을 전제로 합니다. 제품이 별도 merge driver, filter/LFS/submodule를 사용하면 해당 파일의 의미와 실제 배포 결과는 별도로 검토해야 합니다.

Git 자체 취약점까지 제거하지는 않으므로 Runner의 Git을 패치하고 전용 계정/제한된 네트워크에서 운영합니다. 샌드박스는 코드에 의해 완전히 제공되는 것이 아닙니다. 소스 checkout 없이 객체 분석만 해도 Git 구현은 신뢰 컴퓨팅 기반에 포함됩니다.

`pull_request_target`은 충돌 PR에서도 실행되도록 선택했습니다. 이를 사용할 때 PR 코드를 checkout하고 실행하면 위험합니다. 이 프로젝트는 `/opt/pr-integrity-agent`의 관리자 설치 코드만 실행합니다. Runner에 다른 빌드 워크플로를 섞지 않고 PR에서 이 경로 또는 config를 변경할 수 없게 합니다. GitHub.com 개인 저장소에는 이 템플릿을 자동 활성화하지 않습니다.

## LLM

Ollama `/api/chat` + JSON schema로 `{summary,next_steps}`를 받습니다. 기본 `gemma3:4b`, 온도 0, 응답 길이/timeout 제한, schema 타입 검증을 사용합니다. 호스트 allowlist, HTTP redirect 거부, 환경 proxy 미사용으로 목적지를 제한합니다. 외부 인터넷 차단 자체는 사내 방화벽에서 적용하세요. 허용 hostname의 DNS/네트워크 운영은 관리자 책임입니다.

모델 입력은 검사 결과와 파일명으로 제한됩니다. 파일명에도 내부 정보가 포함될 수 있으므로 사내 endpoint만 설정하세요. 모델은 shell, Git, 네트워크 도구 호출 권한이 없습니다. 입력에 코드/파일명으로 삽입된 지시는 데이터로 취급하도록 프롬프트를 주고, 출력은 escape하여 렌더링합니다. 설명이 틀려도 Git 판정과 후보는 변경되지 않습니다.

## 판정할 수 없는 것

- 한 개발자가 자신의 author로 다른 개발자의 코드를 복사 또는 cherry-pick한 경우의 소유권
- 같은 파일의 비충돌 변경이 함수 호출/스키마/설정 의미상 서로 깨뜨리는 모든 경우
- branch 시작 이전의 변경 소유권, 잘못 등록된 관리자 baseline
- 사내 제품 테스트/배포 결과, LFS 실제 바이너리 내용, submodule 내부 변경
- main 갱신 후 오래된 status의 재사용을 코드만으로 완전히 방지하는 것: 보호 규칙의 최신화 필수

이 때문에 PASS 문구는 ‘검사 범위에서 위험 징후 없음’입니다. 업무별 회귀 테스트와 코드 리뷰를 함께 적용해야 합니다.

## 참고한 공식 문서

- [Git merge-tree](https://git-scm.com/docs/git-merge-tree): checkout 없이 병합, 명시적 merge-base, strategy option.
- [Git merge](https://git-scm.com/docs/git-merge): ours 전략과 ours 옵션 차이.
- [Ollama Chat API](https://docs.ollama.com/api/chat): JSON schema 응답 및 로컬 API.
- [Ollama Gemma 3](https://ollama.com/library/gemma3): 모델 태그.
- [GitHub 보호 브랜치](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches): 필수 status 및 최신화.
- [GitHub pull_request_target 보안](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target): 신뢰되지 않는 PR 실행 방지.

문서 확인일: 2026-09-19. GHES 버전별 메뉴/정책 차이는 실제 서버 문서로 확인하세요.
