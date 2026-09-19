# 개인 PC → 개인 GitHub → 사내망 반입

**반입 후 사내 Git 접속정보와 인증을 새로 설정해야 합니다.** 외부 PC의 GitHub.com 로그인은 사내 Git 인증을 대신하지 않습니다. [사내 Git 접속·인증 안내서](INTERNAL_GIT_SETUP.md)에 주소 변경, PAT/SSH 로그인, 사내 CA, Runner 등록과 검증 명령을 정리했습니다.

## 1. 외부망 PC 준비

이 저장소에는 범용 에이전트와 합성 테스트만 올립니다. `config.local.json`, baseline, 사내 코드, 토큰, 모델 파일, 실제 보고서는 Git 추적 대상에서 제외합니다.

```powershell
git clone https://github.com/changqoo/20260921_github_check.git
cd 20260921_github_check
python -m unittest discover -v
python scripts/build_bundle.py
```

생성물은 `dist/pr-integrity-agent-source.zip`과 `dist/pr-integrity-agent-source.zip.sha256`입니다. ZIP에는 파일별 `MANIFEST.sha256`도 포함됩니다. Python 패키지 다운로드는 필요하지 않습니다.

수정 후 개인 GitHub 업로드:

```powershell
git status --short
git add prguard tests scripts docs deploy .github README.md config.example.json .gitignore
git diff --cached --stat
git commit -m "Update PR integrity agent"
git push origin main
```

처음부터 빈 GitHub 저장소에 수동 업로드한다면 프로젝트 폴더에서 `git init -b main`, 위 add/commit, `git remote add origin https://github.com/changqoo/20260921_github_check.git`, `git push -u origin main` 순서입니다. 기존 원격 내용이 있으면 먼저 clone하여 통합하며 force push하지 않습니다. 인증은 Git Credential Manager 또는 조직이 승인한 SSH를 사용하고 PAT를 URL이나 스크립트에 넣지 마세요.

외부망에서 준비할 반입 목록:

| 항목 | 준비 내용 |
|---|---|
| 에이전트 | ZIP + SHA256 + 커밋 SHA (`git rev-parse HEAD`) |
| Python | 사내 서버 OS/아키텍처용 3.10+ 설치 파일/내부 패키지 |
| Git | 서버 OS용 2.50+ 및 보안 패치 버전 |
| Ollama | 테스트에 사용한 동일 버전의 서버 OS용 설치 파일 |
| Gemma 3 | 정확한 태그의 모델 manifests + blobs, 라이선스/모델 카드 |
| GPU 사용 시 | GPU에 맞는 사내 승인 드라이버/런타임 |
| GitHub Runner | 사내 GHES 화면에서 안내하는 호환 Runner 패키지 |

GitHub에 있는 저장소를 인터넷이 없는 사내 서버에서 직접 clone할 수는 없습니다. 외부망 PC에서 다운로드/ZIP 생성 후 회사의 승인된 반입 경로로 옮깁니다. 동일 반입 경로로 패키지와 모델을 별도로 전달합니다.

## 2. Gemma 3 모델 반입

외부 PC에 Ollama를 설치하고 실행한 다음:

```powershell
ollama --version
ollama pull gemma3:4b
ollama show gemma3:4b
ollama run gemma3:4b "한국어로 한 문장 인사해 주세요."
```

정확한 태그·Ollama 버전·`ollama show` 출력과 모델 파일 checksum을 반입 기록에 남깁니다. GPU 용량 정보가 미정이므로 4b는 초기 설정값이며 성능 보증값이 아닙니다.

Windows 기본 모델 경로는 `%USERPROFILE%\.ollama\models`입니다. 모델 로드/다운로드가 끝난 뒤 **manifests와 참조하는 blobs를 함께** 보관합니다. 경로를 `OLLAMA_MODELS`로 변경했다면 해당 경로를 사용합니다. 다른 모델이 섞여 있다면 관리자와 반입 범위를 확인하세요. 모델 저장 경로는 [Ollama 공식 FAQ](https://docs.ollama.com/faq)를 참고하세요.

Linux 사내 서버에서는 승인된 Ollama 설치 후 모델을 예를 들어 `/srv/ollama/models`로 복사하고 Ollama 서비스 사용자에게 읽기/쓰기 권한을 부여합니다. 서비스 환경에 다음을 설정한 뒤 재시작합니다.

```ini
# systemctl edit ollama 로 추가하는 예
[Service]
Environment="OLLAMA_MODELS=/srv/ollama/models"
Environment="OLLAMA_HOST=127.0.0.1:11434"
```

`ollama list`와 `ollama run gemma3:4b`로 외부망 연결 없이 로드되는지 확인합니다. 모델은 GitHub 저장소에 업로드하지 않습니다. Ollama/Gemma 라이선스와 회사 반입 정책은 별도 승인 기준에 따릅니다. 별도 호스트로 Ollama를 운영한다면 내부 방화벽으로 접근을 제한하고 `allowed_llm_hosts` 및 URL을 실제 주소로 바꿉니다.

## 3. 사내망에서 소스 검증

```bash
sha256sum -c pr-integrity-agent-source.zip.sha256
unzip pr-integrity-agent-source.zip
cd pr-integrity-agent
sha256sum -c MANIFEST.sha256
python3 -m unittest discover -v
python3 scripts/demo.py
```

Windows 검증은 `Get-FileHash .\pr-integrity-agent-source.zip -Algorithm SHA256` 결과와 `.sha256` 파일을 비교합니다. ZIP의 checksum 파일은 신뢰된 반입 기록과 대조해야 하며, 두 파일을 함께 변조한 공격을 막는 서명은 아닙니다.

### 3-1. 사내 Git 접속·인증 재설정

1. 관리자에게 사내 Git 종류/버전, 웹·clone·API URL, 계정/인증 정책과 CA 인증서를 확인합니다.
2. 사내 PC에 Git을 설치하고 사내 계정으로 PAT 또는 SSH 인증을 설정합니다.
3. 제품 저장소를 사내 URL에서 새로 clone합니다. 기존 clone을 재사용하면 fetch URL과 별도 push URL을 모두 확인합니다.
4. `git ls-remote` 및 `git fetch origin`으로 읽기 권한을 확인하고, 관리자 지정 테스트 저장소의 임시 브랜치에서 push 권한을 확인합니다.
5. 아래 config의 서버/API 주소, 허용 저장소와 baseline의 repository를 실제 사내 값으로 설정합니다.
6. 사내 GHES에 Runner를 새로 등록합니다. PR 검사에는 사내 Actions가 발급한 작업용 `GITHUB_TOKEN`을 사용합니다.

구체적인 명령과 인증정보 저장 위치는 [사내 Git 접속·인증 안내서](INTERNAL_GIT_SETUP.md)를 따릅니다. 에이전트 소스 저장소와 검사 대상 제품 저장소는 별개이므로 에이전트의 origin을 제품 저장소로 바꾸지 마세요.

## 4. 사내 Runner 설치와 파일 배치

GitHub Enterprise Server에서 Actions가 활성화되어 있어야 합니다. 사내 서버의 관리 UI가 제시하는 **해당 GHES 호환 Runner** 설치 절차를 따릅니다. 전용 Runner label은 `pr-integrity`로 지정합니다. Linux 계정 예시는 `prguard-runner`이며 실제 서비스 계정으로 대체하세요.

| 경로 | 소유/권한 |
|---|---|
| `/opt/pr-integrity-agent` | 관리자 소유, Runner는 읽기/실행만 |
| `/etc/prguard/config.json` | 관리자 소유, Runner는 읽기만 |
| `/var/lib/prguard/baselines` | 등록 관리자만 쓰기, Runner는 읽기만 |
| `/var/lib/prguard/reports` | Runner 쓰기, 승인된 운영자만 읽기 |

소스 ZIP의 내용을 `/opt/pr-integrity-agent`로 복사합니다. `config.example.json`을 `/etc/prguard/config.json`으로 복사한 뒤 다음 값을 교체합니다.

```json
{
  "github_server_url": "https://github.YOUR_COMPANY.example",
  "github_api_url": "https://github.YOUR_COMPANY.example/api/v3",
  "allowed_repositories": ["YOUR_ORG/YOUR_PRODUCT"],
  "targets": ["main", "qa", "dev"],
  "registry_dir": "/var/lib/prguard/baselines",
  "reports_dir": "/var/lib/prguard/reports",
  "llm_enabled": true,
  "ollama_url": "http://127.0.0.1:11434",
  "allowed_llm_hosts": ["127.0.0.1"],
  "model": "gemma3:4b",
  "llm_timeout": 120
}
```

사내 CA 인증서는 Python/OS와 Git 신뢰 저장소에 설치합니다. HTTPS 검증을 끄지 않습니다. 토큰은 config에 기록하지 않으며 워크플로의 `GITHUB_TOKEN`을 사용합니다.

Runner는 이 검사 워크플로 전용으로 제한합니다. 다른 PR 빌드가 같은 Runner에서 실행되면 관리자 설치 코드와 자격 증명 보호가 약해집니다. GitHub/GHES의 Runner group·워크플로 접근 정책으로 범위를 제한하세요. 실제 테스트 빌드는 별도 격리 Runner를 사용합니다.

## 5. 제품 저장소에 연결

1. 제품 저장소의 기본 브랜치가 main인지 확인합니다.
2. 이 프로젝트의 `deploy/pr-integrity.internal.yml`을 제품 저장소의 `.github/workflows/pr-integrity.yml`로 복사하여 관리자 리뷰 후 반영합니다.
3. 전용 Runner 경로/label을 실제 설치 환경과 맞춥니다. 외부 action을 호출하지 않으므로 checkout/upload-artifact 미러링이 필요하지 않습니다.
4. 개발 브랜치 baseline을 [운영 절차](OPERATIONS.md)에 따라 등록합니다.
5. 합성 샘플 PR로 동작 검증 후 main의 필수 검사 `pr-integrity`와 최신화 요구를 활성화합니다.
6. 회사 제품 CI는 별도로 필수 검사에 추가합니다. dev/qa 테스트 성공 여부를 이 에이전트가 대신 검증하지 않습니다.

연동은 `pull_request_target` 이벤트이므로 충돌 PR도 검사할 수 있습니다. **PR 코드를 checkout/실행하는 step을 이 워크플로에 추가하지 마세요.** 토큰은 contents read, pull-requests read, statuses write만 사용합니다. PR 댓글 생성/수정은 하지 않습니다.

개인 GitHub 저장소의 `.github/workflows/test.yml`은 GitHub-hosted 환경에서 합성 테스트만 실행합니다. 사내 적용 워크플로는 별도 템플릿으로 유지합니다.

## 6. 운영 전 승인 기준

[ACCEPTANCE.md](ACCEPTANCE.md) 시나리오를 모두 확인하고 실제 프로젝트의 제품 CI를 통과한 뒤 차단 모드를 사용합니다. 초기에 보호 규칙을 켜기 전 보고서를 관찰하는 기간을 두어 예상되는 의도적 수정의 차단 빈도를 확인할 수 있습니다. 에이전트 자체의 BLOCK 판정을 PASS로 바꾸는 설정은 없습니다.

버전 업데이트 시 기존 설치를 버전별 디렉터리에 보관하고 테스트한 소스로 교체합니다. baseline과 보고서는 코드 설치 디렉터리 밖에 있으므로 보존합니다. 문제 발생 시 이전 코드로 되돌리고 동일 base/head SHA를 재검사하세요. baseline을 삭제하거나 현재 main으로 갱신해 문제를 숨기지 않습니다.
