import html
import json
import re
from pathlib import Path


def markdown(result):
    def safe(value):
        value = html.escape(str(value)).replace("\n", " ").replace("\r", " ").replace("|", "&#124;")
        return re.sub(r"([\\`*_[\]{}()#+.!-])", r"\\\1", value)
    lines = [f"# {'✅' if result['status'] == 'PASS' else '🛑'} PR Integrity: {result['status']}", "",
             f"**{safe(result['branch'])} → {safe(result['target'])}**", "",
             f"- 기준 SHA: `{result.get('origin_sha', '미등록')}`",
             f"- 대상 SHA: `{result['base_sha']}`", f"- PR SHA: `{result['head_sha']}`",
             f"- 보존 후보: {'생성됨 · 별도 테스트 필요' if result['candidate_available'] else '생성되지 않음'}", "",
             "| 검사 | 결과 | 파일 |", "|---|---|---|"]
    for finding in result["findings"]:
        lines.append(f"| {safe(finding['code'])} | {safe(finding['message'])} | {safe(', '.join(finding['files']))} |")
    lines += ["", "## Gemma 3 보조 설명", ""]
    llm = result["llm"]
    if llm["status"] == "ok":
        lines += [safe(llm["summary"]), ""] + ["- " + safe(s) for s in llm["next_steps"]]
    else:
        lines.append("미사용 또는 연결 실패: Git 판정은 유지됩니다. " + safe(llm.get("error", "")))
    lines += ["", "## 다음 행동", "",
              "- BLOCK이면 기존 PR 병합을 중단하고 충돌/소유 범위를 확인하세요.",
              "- candidate.patch는 기록된 대상 SHA 위에 적용하는 후보입니다. 제외된 변경을 확인하고 dev/qa 테스트를 다시 실행하세요.",
              "- candidate_files는 자동 반영 후보 목록, origin_conflicts는 제외/보존 검토가 필요한 파일입니다.",
              "- main/PR SHA가 변경되면 다시 검사하세요. PASS는 기능 정합성 또는 변경 소유권의 완전한 증명이 아닙니다."]
    return "\n".join(lines) + "\n"


def write_report(directory, result, candidate=None, suppressed=None):
    out = Path(directory)
    # A fresh directory prevents stale patches being reused after a failed check.
    out.mkdir(parents=True, exist_ok=False)
    (out / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md = markdown(result)
    (out / "report.md").write_text(md, encoding="utf-8")
    color = "#107a55" if result["status"] == "PASS" else "#c43838"
    rows = "".join("<tr><td>" + html.escape(f["code"]) + "</td><td>" + html.escape(f["message"]) + "</td><td>" + html.escape(", ".join(f["files"])) + "</td></tr>" for f in result["findings"])
    doc = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>PR Integrity Report</title><style>body{font:16px/1.65 system-ui,sans-serif;background:#f3f5f9;color:#19273c;margin:0;padding:32px}main{max-width:1100px;margin:auto}h1{font-size:36px}table{width:100%;border-collapse:collapse;background:white}td,th{text-align:left;padding:16px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:24px;border-radius:12px}.badge{color:white;border-radius:12px;padding:16px 24px;display:inline-block}a{color:#1457a6}</style><main>'''
    doc += f'<p>LOCAL GIT + GEMMA 3</p><h1>PR 정합성 검사</h1><h2 class="badge" style="background:{color}">{result["status"]}</h2>'
    doc += "<p>" + html.escape(result["branch"] + " → " + result["target"]) + "</p>"
    doc += "<table><tr><th>검사</th><th>판정 근거</th><th>관련 파일</th></tr>" + rows + "</table>"
    doc += "<h2>세부 정보 및 조치</h2><pre>" + html.escape(md) + "</pre></main></html>"
    (out / "report.html").write_text(doc, encoding="utf-8")
    if candidate is not None:
        (out / "candidate.patch").write_bytes(candidate)
    if suppressed is not None:
        (out / "excluded.patch").write_bytes(suppressed)
    return md
