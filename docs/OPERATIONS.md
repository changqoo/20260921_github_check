# 브랜치 운영 절차

## 정상 개발 흐름

1. 개발자가 `git fetch origin` 후 `git switch -c feature/TICKET origin/main`을 실행합니다.
2. 최초 개발 커밋 전 기준점을 등록합니다. 서버 관리자는 자신의 신뢰된 clone에서 최신 main을 fetch하여 시작 SHA와 소유자 이메일을 확인합니다. `register`의 `--head`와 `--main`은 이 시점 같은 SHA여야 합니다.
3. 서버 보호 디렉터리의 baseline JSON에 repository, branch, start_sha, owners가 기록됩니다. 개발자 PC에서 만든 파일은 편의용 초안이며, 서버가 자동으로 신뢰하면 안 됩니다. 관리자가 검증하여 등록해야 합니다.
4. 기능 커밋을 작성해 feature 브랜치를 원격에 push하고 dev 및 qa에 각각 PR합니다. dev/qa 검사 결과는 보고서에 표시합니다. 이 버전은 dev/qa 테스트 CI 결과를 자동 승격 조건으로 수집하지 않습니다.
5. dev/qa에서 기능 테스트를 통과한 **동일 feature HEAD SHA**로 main PR을 만듭니다. dev/qa를 feature로 역병합하지 않습니다.
6. main PR은 `pr-integrity`와 실제 제품 CI를 필수 검사로 지정합니다. 최신 main이 반영된 상태여야 병합할 수 있게 설정합니다.
7. main이 변경되면 main을 feature에 merge하고 재검사합니다. baseline을 초기화하지 않습니다. 원래 기준점이 남아야 잘못 해결한 원복을 감지합니다.

**중요:** dev/qa 테스트 이후 HEAD 또는 main이 바뀌면 결과 후보를 다시 테스트해야 합니다. 이 검사기는 기존 제품의 단위·통합·배포 테스트를 대체하지 않습니다.

## 관리자 baseline 등록 예

아래는 서버에서 신뢰하는 product clone을 사용합니다. 브랜치 등록 전에 main을 fetch해야 하며, `origin/main` 같은 로컬 ref를 개발자가 임의로 지정하는 API를 외부에 열지 않습니다.

```bash
git -C /srv/product fetch origin
cd /opt/pr-integrity-agent
python3 -m prguard register \
  --repo /srv/product --main origin/main --head origin/main \
  --repository MY_ORG/product --branch feature/TICKET \
  --owner developer@company.example \
  --registry /var/lib/prguard/baselines
```

개발자도 이와 동일한 origin/main SHA에서 브랜치를 생성해야 합니다. 여러 명이 한 feature를 공유하면 `--owner`를 반복할 수 있습니다. 이메일은 Git author email이며 계정 이메일과 다를 수 있습니다. 이메일은 위조 가능하므로 인증된 사용자 identity 증명은 아닙니다. 조직 정책상 필요하면 signed commit 정책을 별도로 적용하세요.

baseline 파일은 PR 저장소 밖에 두고 Runner에는 읽기 권한만 줍니다. 등록 관리 계정만 생성할 수 있도록 하며 코드의 `open(..., 'x')`가 기존 파일의 덮어쓰기를 거부합니다. baseline 브랜치명은 재사용하지 마세요. 다른 작업에 재사용해야 하면 기존 이력과 승인 기록을 보관한 뒤 별도 관리 절차로 변경합니다.

## 이미 개발 중인 브랜치

현재 merge-base로 자동 소급 등록하지 않습니다. 관리자와 개발자가 실제 시작 SHA를 확인하고, 해당 SHA에서의 브랜치 생성 이력·작업 티켓·커밋 목록을 감사한 다음 baseline JSON을 별도로 작성할 수 있습니다. 형식은 신규 등록 파일과 같고 `registered_at` 및 추가 `approval_note` 필드에 근거를 남깁니다. `start_sha`는 양쪽의 조상이어야 합니다. 시작점을 확인할 수 없으면 새 main에서 새 feature를 만들고 확인된 작업만 옮기세요.

## 충돌 후보 처리

1. BLOCK 보고서를 확인합니다. 겹친 변경과 기존 변경 손실은 결함 확정이 아닙니다.
2. 새 `prepare` 작업 폴더에서 `git diff --cached`를 검토합니다. 자동 제외된 기능이 필요한지 확인합니다.
3. 이 후보를 새 feature 브랜치로 진행할 경우, 부모인 기록된 main SHA를 기준으로 관리자 baseline을 **새 브랜치명**으로 등록합니다. main이 바뀌었다면 재생성하세요.
4. 새 작업 폴더에서 사용자 이름/이메일을 설정하고 `git branch -m feature/TICKET-safe`, `git commit`, `git remote add origin <사내 product URL>`, `git push -u origin feature/TICKET-safe`를 실행합니다.
5. dev/qa 테스트 및 새 main PR을 진행합니다. 기존 PR은 검토 후 종료합니다.

`prepare`는 source 저장소의 remote/credential 설정을 복사하지 않습니다. 새 폴더의 staged 변경을 사용자 확인 없이 커밋하거나 push하지 않습니다.

## 타인의 변경을 의도적으로 수정해야 하는 경우

의도적인 변경도 충돌 구간에 걸리면 차단됩니다. LLM의 판단이나 PR 라벨만으로 gate를 해제하지 않습니다. 담당자와 기존 코드 소유자가 수정 의도를 검토한 뒤 **최신 main에서 새 feature를 만들고 승인된 수정을 다시 구현**합니다. 새 baseline부터 시작하므로 과거 변경과 구별할 수 있습니다. 기존 baseline을 덮어써 차단을 우회하는 방식은 사용하지 마세요.

## main 보호 설정

- PR 필수, 직접 push/force push 제한, 관리자의 bypass 제한.
- 필수 status context: `pr-integrity` 및 기존 제품 테스트.
- **Require branches to be up to date before merging** 활성화. push 이벤트 재검사만으로는 main 변경 직후의 경쟁 조건을 완전히 막지 못하므로 필수입니다.
- 사내 GHES 버전에서 지원하는 경우 check의 출처도 지정하세요.
- 현재 템플릿은 `merge_group`을 처리하지 않습니다. **merge queue를 활성화하지 마세요.** 도입하려면 별도 이벤트/SHA 처리 확장이 필요합니다.
- GitHub status는 SHA 단위입니다. 같은 feature SHA로 dev/qa 검사 결과를 쓰면 main 결과를 덮어쓸 수 있어 이 버전은 **main 대상에만 gate status**를 씁니다. dev/qa는 Actions Summary 보고만 제공합니다.
- 동일 SHA의 서로 다른 main PR은 만들지 않는 운영 규칙을 권장합니다. status는 PR별 독립 키가 아닙니다.

## 장애 처리

기준점 누락/Git 오류는 실패 처리합니다. 모델 장애는 Git 판정에 영향을 주지 않으며 설명에만 표시됩니다. 실행 중 head/base가 변경되면 오류 status로 종료하고 재실행해야 합니다. main·qa·dev push 시 열려 있는 PR을 재검사하며, 필요 시 Actions의 수동 실행을 사용합니다. 대규모 저장소의 검사 시간이 30분 제한을 넘으면 타임아웃과 Runner 용량을 조정하고 재검사하세요.

보고서 경로는 `<reports_dir>/<run_id>/<attempt>/<PR번호>`입니다. Runner 운영자가 접근 권한과 보존기간을 설정하고 정기 정리하세요. 대형 패치는 보고서 디스크 사용량을 늘립니다. 현재 외부 artifact action 없이 동작하므로 패치 파일은 Runner 디스크에서 승인된 내부 파일 전송으로 가져옵니다. GitHub 화면에는 Actions Summary와 PR status 링크가 표시됩니다.
