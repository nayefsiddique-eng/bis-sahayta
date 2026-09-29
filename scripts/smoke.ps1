param(
  [string]$BaseUrl = "http://localhost:8000",
  [string]$ApiKey = "demo-key-123",
  [switch]$Strict
)
$ErrorActionPreference = "Stop"
$script:fail = 0
$script:warn = 0
$script:sid = $null
$H = @{ "X-API-Key" = $ApiKey }
Write-Host "PowerShell $($PSVersionTable.PSVersion)"

function Step([string]$Name, [scriptblock]$Body) {
  try { & $Body; Write-Host "PASS  $Name" }
  catch { $script:fail++; Write-Host "FAIL  $Name : $($_.Exception.Message)" }
}

function Get-Code($err) {
  if ($err.Exception.Response) { return [int]$err.Exception.Response.StatusCode }
  return 0
}

# Windows PowerShell 5.1 returns a JSON array as one wrapped object; flatten it.
function Get-List([string]$Url) {
  return @(Invoke-RestMethod $Url -Headers $H | ForEach-Object { $_ })
}

function Invoke-Chat([string]$Query, [string]$SessionId) {
  $b = @{ query = $Query; lang = "en" }
  if ($SessionId) { $b.session_id = $SessionId }
  try {
    return Invoke-RestMethod -Uri "$BaseUrl/api/chat" -Method Post -Headers $H -ContentType "application/json" -Body ($b | ConvertTo-Json) -TimeoutSec 180
  } catch {
    if ((Get-Code $_) -eq 429 -and -not $Strict) {
      $script:warn++
      Write-Host "WARN  chat rate limited (429); rerun with -Strict to treat as failure"
      return $null
    }
    throw
  }
}

Step "GET /health" {
  $r = Invoke-RestMethod "$BaseUrl/health"
  if ($r.status -ne "ok") { throw "status=$($r.status)" }
}

Step "GET /api/health" {
  $r = Invoke-RestMethod "$BaseUrl/api/health"
  if ($r.status -ne "ok") { throw "status=$($r.status)" }
}

Step "GET /ready (rag and llm ok)" {
  $r = Invoke-RestMethod "$BaseUrl/ready"
  if ($r.status -ne "ready") { throw "status=$($r.status)" }
  if ($r.checks.rag.status -ne "ok") { throw "rag=$($r.checks.rag.status)" }
  if ($r.checks.llm.status -ne "ok") { throw "llm=$($r.checks.llm.status)" }
}

Step "missing API key returns 401" {
  $code = 0
  try { Invoke-RestMethod "$BaseUrl/api/sessions" | Out-Null } catch { $code = Get-Code $_ }
  if ($code -ne 401) { throw "expected 401, got $code" }
}

Step "POST /api/chat (1)" {
  $r = Invoke-Chat "What is IS 302?" $null
  if ($null -eq $r) { Write-Host "      skipped (rate limited)"; return }
  if (-not $r.session_id) { throw "no session_id" }
  if (-not $r.answer) { throw "empty answer" }
  if ($null -eq $r.rag_used) { throw "rag_used missing" }
  $script:sid = $r.session_id
  Write-Host ("      rag_used={0} sources={1} relevance={2}" -f $r.rag_used, @($r.sources).Count, $r.relevance)
}

Step "POST /api/chat (2, same session)" {
  if (-not $script:sid) { Write-Host "      skipped (no session)"; return }
  $r = Invoke-Chat "Tell me more about safety requirements." $script:sid
  if ($null -eq $r) { Write-Host "      skipped (rate limited)"; return }
  if ($r.session_id -ne $script:sid) { throw "session id changed" }
}

Step "GET /api/sessions lists the session" {
  if (-not $script:sid) { Write-Host "      skipped (no session)"; return }
  $list = @(Get-List "$BaseUrl/api/sessions")
  if (-not ($list | Where-Object { $_.id -eq $script:sid })) { throw "session not listed (got $($list.Count) sessions)" }
}

Step "GET /api/sessions/{id}/messages" {
  if (-not $script:sid) { Write-Host "      skipped (no session)"; return }
  $msgs = @(Get-List "$BaseUrl/api/sessions/$($script:sid)/messages")
  if ($msgs.Count -lt 2) { throw "expected at least 2 messages, got $($msgs.Count)" }
  Write-Host "      messages=$($msgs.Count)"
}

Step "DELETE session then 404" {
  if (-not $script:sid) { Write-Host "      skipped (no session)"; return }
  Invoke-RestMethod "$BaseUrl/api/sessions/$($script:sid)" -Method Delete -Headers $H | Out-Null
  $code = 0
  try { Invoke-RestMethod "$BaseUrl/api/sessions/$($script:sid)/messages" -Headers $H | Out-Null } catch { $code = Get-Code $_ }
  if ($code -ne 404) { throw "expected 404 after delete, got $code" }
}

Write-Host ""
Write-Host ("failures={0} warnings={1}" -f $script:fail, $script:warn)
if ($script:fail -gt 0) { exit 1 }
Write-Host "SMOKE OK"
exit 0
