$ErrorActionPreference = "Stop"

$repo = "firewelly/media-library-manager"
$tag = "v1.0.0"
$title = "Windows v1.0 - 完整版"
$releaseNotes = @"
Windows平台完整版，包含所有工具和用户手册

主要功能：
- 📦 完整的媒体库管理功能
- 📖 内置用户手册（HTML格式）
- 🕷️ 20+ 数据爬虫工具
- 🔧 媒体库维护工具
- 🤖 AI视频分析工具

修复内容：
- 修复Windows下路径匹配问题
- 添加Windows用户手册
- 更新README文档

安装方式：
1. 下载ZIP文件
2. 解压到任意目录
3. 双击MediaLibrary.exe启动程序
4. 双击用户手册.exe查看详细说明
"@

$zipFile = "d:\bin\media\release\MediaLibrary\MediaLibrary-Windows-Complete.zip"

if (-not (Test-Path $zipFile)) {
    Write-Error "ZIP文件不存在：$zipFile"
    exit 1
}

Write-Host "文件大小: $((Get-Item $zipFile).Length / 1GB) GB" -ForegroundColor Yellow

Write-Host "`n请提供GitHub Personal Access Token (PAT):" -ForegroundColor Cyan
Write-Host "获取方式：GitHub Settings -> Developer settings -> Personal access tokens -> Tokens (classic)" -ForegroundColor Gray
Write-Host "需要的权限：repo (full control of private repositories)" -ForegroundColor Gray
$token = Read-Host "Token" -MaskInput

$headers = @{
    Authorization = "Bearer $token"
    Accept = "application/vnd.github.v3+json"
}

Write-Host "`n创建release..." -ForegroundColor Cyan
$releaseBody = @{
    tag_name = $tag
    name = $title
    body = $releaseNotes
    draft = $false
    prerelease = $false
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases" -Method Post -Headers $headers -Body $releaseBody -ContentType "application/json"
    Write-Host "Release创建成功: $($response.html_url)" -ForegroundColor Green
    
    Write-Host "`n开始上传ZIP文件（约7.3GB）..." -ForegroundColor Yellow
    Write-Host "这可能需要较长时间，请耐心等待..." -ForegroundColor Yellow
    
    $uploadUrl = $response.upload_url -replace '\{.*\}', "?name=MediaLibrary-Windows-Complete.zip"
    
    $uploadHeaders = @{
        Authorization = "Bearer $token"
        Accept = "application/vnd.github.v3+json"
        "Content-Type" = "application/zip"
    }
    
    $uploadResponse = Invoke-RestMethod -Uri $uploadUrl -Method Post -Headers $uploadHeaders -InFile $zipFile
    Write-Host "文件上传成功！" -ForegroundColor Green
    Write-Host "下载链接: $($uploadResponse.browser_download_url)" -ForegroundColor Cyan
    
} catch {
    Write-Error "操作失败: $_"
    Write-Error $_.Exception.Message
    exit 1
}

Write-Host "`n完成！" -ForegroundColor Green
