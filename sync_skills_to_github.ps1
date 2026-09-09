$ErrorActionPreference = "Stop"

$repo = "D:\Android\Project\20260813\demo"
Set-Location $repo

# Only sync project skills, related Python scripts/reports, and this sync task script.
git add -- .trae/skills "scripts/*.py" "scripts/*.md" sync_skills_to_github.ps1

if (-not (git diff --cached --quiet)) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "自动同步技能和跟踪文件 $stamp"
    git push origin main
}
