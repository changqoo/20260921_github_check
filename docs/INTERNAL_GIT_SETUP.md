# 사내 Git 접속·인증 설정 안내서

파일 반입 후 **사내 Git 서버 주소와 인증을 새로 설정**하는 절차입니다. 아래 주소/계정은 예시이며 실제 사내 값으로 바꿉니다. 외부 개인 GitHub의 로그인·토큰·개인 키를 사내 서버에 복사하지 않습니다.

## 1. 관리자에게 받을 정보

| 항목 | 예시 / 확인 사항 |
|---|---|
| Git 서비스·버전 | GitHub Enterprise Server(GHES), Actions 활성화 여부 |
| 웹 주소 | `https://git.company.example` |
| 제품 clone URL | `https://git.company.example/TEAM/product.git` 또는 Code 메뉴의 SSH URL |
| REST API | GHES 예: `https://git.company.example/api/v3` |
| 조직/저장소 | `TEAM/product` — config와 baseline에서 동일하게 사용 |
| 계정·인증 정책 | 사내 계정, LDAP/SSO, PAT 종류·권한·만료·조직 승인 정책 |
| 네트워크 | 내부 DNS, HTTPS/SSH 포트, Runner의 접근 허용 |
| 인증서 | 관리자 제공 루트/중간 CA, SSH host key fingerprint |
| Runner | 등록 관리자, 전용 서비스 계정, label `pr-integrity` |

현재 자동 연동은 **GHES + Actions + HTTPS API/Git fetch**를 전제로 합니다. GitLab/Gitea 또는 Actions 미지원 서버는 URL만 바꾸어 자동 연동할 수 없으며 이벤트/API adapter 추가가 필요합니다. 로컬 `prguard check`는 Git 저장소에서 사용할 수 있습니다. 개발자가 SSH를 사용해도 현재 Runner는 HTTPS 접근이 필요합니다.

## 2. 인증을 설정하는 세 위치

| 위치 | 사용할 인증 | 저장/설정 위치 |
|---|---|---|
| 개발자 PC·baseline 관리자 clone | 사내 PAT 또는 사내 계정의 SSH 키 | 승인된 OS credential manager / SSH agent |
| 사내 GHES에 Runner 최초 등록 | GHES 등록 화면에서 발급한 시간 제한 등록 토큰 | Runner 등록 과정에서 입력 |
| PR 검사 중 fetch·API·status 등록 | 사내 Actions가 작업별로 발급한 `GITHUB_TOKEN` | 제공한 workflow의 env 매핑 |

Runner 등록 토큰과 작업용 API 토큰은 다릅니다. 사용자 PAT를 제품 config에 넣지 않습니다. 현재 `config.example.json`에는 주소와 허용 저장소를 설정하며 인증정보 필드는 없습니다.

## 3. 사내 PC에 Git 설치

사내 승인 Git 설치 파일을 반입하여 설치한 뒤 새 PowerShell/터미널에서 확인합니다. 외부 PC의 번들 Git 경로가 사내 PC에도 있다고 가정하지 않습니다.

```powershell
git --version
```

에이전트 검사에는 Git 2.50 이상이 필요합니다. 아래 인증 방식 중 사내 정책에 맞는 하나를 선택합니다.

## 4. HTTPS/PAT로 사내 제품 저장소 연결

1. 사내 Git 웹 주소에 사내 계정으로 로그인하여 대상 저장소가 보이는지 확인합니다.
2. 사내 GHES의 Settings → Developer settings → Personal access tokens에서 회사가 허용하는 PAT를 발급합니다. 메뉴와 지원 토큰 종류는 GHES 버전에 따라 다릅니다.
3. 대상 저장소에 필요한 최소 권한을 지정합니다. fine-grained 토큰 사용 시 읽기는 Contents read, 개발 push는 Contents write가 필요합니다. classic PAT만 허용되는 private 저장소는 `repo` scope가 필요할 수 있습니다. workflow 수정 권한, 조직 승인 및 만료 정책은 관리자에게 확인합니다.
4. 다음 명령의 인증 UI에서 사내 호스트/계정을 선택합니다. PAT 방식으로 Username/Password를 요청하면 Username에는 사내 사용자명, Password에는 PAT를 입력합니다. 토큰을 URL이나 명령 인자로 넣지 않습니다.

```powershell
git ls-remote https://git.company.example/TEAM/product.git refs/heads/main
git clone https://git.company.example/TEAM/product.git C:/work/product
cd C:/work/product
git config --local user.name "YOUR_NAME"
git config --local user.email "YOUR_COMPANY_EMAIL"
git fetch origin
```

`user.name`/`user.email`은 커밋 작성자 표시이며 로그인 설정이 아닙니다. 이메일은 baseline 등록의 `--owner`와 맞춥니다.

Windows에서 GCM을 사용하는 경우 `git credential-manager --version`으로 설치 여부를 확인합니다. 회사가 승인한 credential helper를 사용하며 사내 호스트에 인증합니다. 사내 OAuth/브라우저 로그인 지원은 서버 설정에 따라 달라집니다. 지원되지 않으면 관리자 지정 PAT 인증 절차를 따릅니다. Linux는 승인된 OS keyring 기반 helper를 사용하세요. 평문 `credential.helper store`는 사용하지 않습니다.

캐시된 다른 계정 또는 만료 토큰 때문에 실패하면 OS 자격 증명 관리 도구에서 **해당 사내 호스트의 Git 항목만** 갱신하여 재인증합니다. 외부 GitHub 인증을 지울 필요는 없습니다. 토큰을 발급한 사용자에게도 해당 제품 저장소 접근 권한이 있어야 합니다.

## 5. SSH를 사용하는 경우

사내 PC에서 회사가 허용한 알고리즘으로 새 키를 생성합니다. 다음은 Ed25519 예입니다. 기존 파일이 있으면 덮어쓰지 말고 다른 이름을 지정합니다.

```powershell
ssh-keygen -t ed25519 -C "YOUR_COMPANY_EMAIL" -f "$env:USERPROFILE/.ssh/id_ed25519_company"
```

passphrase를 설정하고 `.pub` 공개 키만 사내 GHES 계정의 SSH keys에 등록합니다. 개인 키는 공유하지 않습니다. 사용자 `.ssh/config`에 기존 설정을 보존하면서 다음을 추가합니다.

```sshconfig
Host company-git
    HostName git.company.example
    User git
    Port 22
    IdentityFile ~/.ssh/id_ed25519_company
    IdentitiesOnly yes
```

호스트·사용자명·포트는 사내 Code 메뉴의 clone URL에 맞춥니다. 첫 연결의 host key fingerprint는 관리자 제공 값과 대조 후 승인합니다.

```powershell
ssh -T company-git
git ls-remote git@company-git:TEAM/product.git refs/heads/main
git clone git@company-git:TEAM/product.git C:/work/product
```

SSH 테스트는 인증 성공과 shell 미제공 메시지를 함께 표시하거나 0이 아닌 종료 코드를 반환할 수 있으므로 `git ls-remote`까지 확인합니다. 개발자 SSH 키는 Runner의 HTTPS 토큰을 대체하지 않습니다.

## 6. 기존 clone의 접속 주소 변경

가능하면 사내 제품을 새 폴더에 clone합니다. **에이전트 배포 소스와 제품 소스는 별개**입니다. 에이전트를 사내 Git에도 보관하려면 `TEAM/pr-integrity-agent` 같은 별도 저장소를 사용합니다. 에이전트 소스를 기존 제품 저장소로 그대로 push하지 마세요.

동일 제품 이력을 가진 기존 clone을 재사용할 때만 그 제품 폴더에서 실행합니다.

```powershell
git status --short
git remote -v
git remote set-url origin https://git.company.example/TEAM/product.git
# 별도의 push URL도 사내 주소로 지정
git remote set-url --push origin https://git.company.example/TEAM/product.git
git remote get-url --all origin
git remote get-url --push --all origin
git fetch origin
git branch -r
```

fetch/push URL이 각각 사내 주소 하나인지 확인합니다. 과거 여러 push URL을 등록해 외부 주소가 남아 있다면 관리자와 정리한 뒤 진행합니다. origin이 없다면 `git remote add origin <사내 URL>`을 사용합니다. 반입 ZIP에는 `.git`이 없으므로 원격 교체가 아니라 별도 저장소 초기화가 필요합니다. 이 단계에서 main에 push하거나 force push하지 않습니다.

읽기 성공은 쓰기 권한을 보증하지 않습니다. 관리자 지정 테스트 저장소에서 임시 feature 브랜치 push와 PR을 확인하세요.

## 7. 사내 CA와 네트워크

브라우저 접속 성공만으로 Git/Python/Runner가 인증서를 신뢰한다고 판단하지 않습니다. 관리자 제공 CA를 각각 실행 환경에 설치합니다.

| 환경 | 설정 |
|---|---|
| Windows 개발자 Git | Windows 신뢰 루트/중간 CA 설치. Schannel을 사용하는 Git for Windows는 해당 저장소 사용 |
| Linux Runner의 Git | 배포판의 시스템 CA 저장소 갱신, 실제 Git TLS backend의 기본 CA 경로 확인 |
| Python API | 시스템 CA 사용. 필요 시 관리자 PEM bundle을 Runner 서비스 환경의 `SSL_CERT_FILE`로 지정 |
| Runner 서비스 | 해당 Runner/OS의 인증서 신뢰 설정 후 서비스 재시작 |

Debian/Ubuntu 관리자 예시:

```bash
sudo install -m 0644 company-root-ca.crt /usr/local/share/ca-certificates/company-root-ca.crt
sudo update-ca-certificates
```

RHEL 계열은 배포판의 `update-ca-trust` 절차를 사용합니다. **현재 에이전트는 전역 Git config와 `GIT_*` 환경변수를 격리합니다.** 개발자 clone의 `http.sslCAInfo`나 `GIT_SSL_CAINFO`만 설정해서는 검사 subprocess까지 적용되지 않습니다. Runner에서는 Git의 기본 TLS backend가 읽는 시스템 CA를 설정하고 실제 workflow의 fetch로 확인합니다. Python용 `SSL_CERT_FILE`은 Git CA 설정과 별개입니다.

`http.sslVerify=false`나 Runner TLS 검증 해제로 우회하지 않습니다. 현재 API/LLM client는 환경 proxy를 사용하지 않습니다. 내부 API까지 proxy를 거쳐야 하는 환경이면 직접 연결 경로를 마련하거나 별도 proxy 지원이 필요합니다.

## 8. 에이전트 config에 사내 접속값 입력

관리자가 `/etc/prguard/config.json`의 아래 필드를 바꿉니다. 이는 발췌이므로 모델/경로 설정 등 나머지 필드는 유지합니다.

```json
{
  "github_server_url": "https://git.company.example",
  "github_api_url": "https://git.company.example/api/v3",
  "allowed_repositories": ["TEAM/product"]
}
```

URL 끝에는 `/`를 붙이지 않고 `OWNER/REPO`는 실제 표기와 맞춥니다. baseline도 `--repository TEAM/product`로 등록합니다. Git remote 변경과 config 변경은 각각 필요하며 서로 자동으로 바뀌지 않습니다. 토큰은 이 파일에 추가하지 않습니다.

## 9. 사내 GHES에 Runner 재등록

1. 사내 제품 저장소/조직의 Settings → Actions → Runners → New self-hosted runner에서 해당 버전의 패키지와 등록 명령을 확인합니다.
2. 패키지를 승인된 경로로 준비합니다. 외부 github.com에 등록한 Runner 폴더/자격 증명을 복사하지 않습니다.
3. 사내 서버에서 화면이 안내한 config 명령을 실행합니다. `--url`이 사내 제품/조직 URL인지 확인하고, 화면이 발급한 시간 제한 등록 토큰을 입력합니다. 실제 토큰이 든 명령을 문서·공유 로그에 저장하지 않습니다.
4. label `pr-integrity`와 전용 서비스 계정을 설정하고 사내 Runners 화면에서 Idle/Online을 확인합니다.
5. [배포 가이드](OFFLINE_DEPLOYMENT.md)의 코드/config/baseline 권한을 적용합니다. 관리자 터미널과 서비스 계정의 CA·권한 차이를 확인합니다.
6. 사내 제품 저장소에 제공된 workflow를 설치합니다. 회사 정책에서 contents read, pull-requests read, statuses write를 허용해야 합니다.

workflow의 다음 매핑은 그대로 사용합니다.

```yaml
env:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  PRGUARD_CONFIG: /etc/prguard/config.json
```

`GITHUB_SERVER_URL`, `GITHUB_API_URL`, `GITHUB_REPOSITORY`, 이벤트 경로와 run ID는 **사내 Actions가 제공**합니다. github.com 값을 수동으로 복사하지 않습니다. config와 실행 환경 주소/저장소가 다르면 검사가 오류로 중단됩니다. 작업 토큰은 해당 저장소 검사에 사용하며 사용자 공용 PAT로 대체하지 않습니다.

## 10. 인수 테스트와 문제 해결

사내 DNS/포트 → CA → Git 읽기 → 임시 브랜치 쓰기 → Runner Online → baseline 등록 → 합성 PR status/보고서 → main 보호 규칙 순서로 확인합니다.

| 증상 | 확인할 내용 |
|---|---|
| git 명령 없음 | Git 설치·PATH, 새 터미널 |
| DNS 실패/timeout | 내부 DNS, 망 연결, 방화벽·포트 |
| 인증서 검증 실패 | Git/Python/Runner별 CA, 서버 hostname |
| 인증 반복/401 | 사내 계정·토큰 만료, 해당 호스트 credential cache |
| 403 | 계정/저장소 권한, 조직 승인, Actions statuses write 정책 |
| 404/Repository not found | URL 오기 또는 private 저장소 권한 부족 |
| SSH publickey 오류 | 사내 공개 키 등록, 선택한 키·포트·agent |
| Runner Offline | 사내 URL 등록, 서비스·CA·네트워크 |
| server/API mismatch | config의 외부 github.com/이전 서버 주소 잔존 |
| Repository not allowed | allowed_repositories 실제 OWNER/REPO 표기 |
| clone 성공, 검사 fetch 실패 | 개발자 인증과 작업 토큰·서비스 계정·격리된 Git CA 차이 |

실제 사내 접속값은 사내 config에만 작성합니다. PAT/개인 키는 공개 저장소나 채팅에 올리지 않습니다. PAT 만료, SSH 키 교체, 서비스 계정 변경 시 해당 인증 계층을 갱신하고 위 테스트를 반복하세요.

## 공식 참고

- [GHES 인증 방식](https://docs.github.com/en/enterprise-server@3.19/authentication/keeping-your-account-and-data-secure/about-authentication-to-github)
- [GHES 개인 액세스 토큰](https://docs.github.com/en/enterprise-server@3.21/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [GHES Runner 등록](https://docs.github.com/en/enterprise-server@3.20/actions/how-tos/manage-runners/self-hosted-runners/add-runners)
- [Git TLS 및 설정 옵션](https://git-scm.com/docs/git-config)

사내 서버 버전별 메뉴·기능·조직 정책은 해당 버전의 공식 문서로 대조하세요.
