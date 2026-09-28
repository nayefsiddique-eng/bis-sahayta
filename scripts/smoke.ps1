# PowerShell smoke test script for BIS Sahayta API
$ErrorActionPreference = "Stop"

$baseUrl = "http://localhost:8000"
$headers = @{ "X-API-Key" = "demo-key-123" }

Write-Host "1. Testing /health..."
$health = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get
if ($health.status -ne "ok") { throw "Health check failed" }
Write-Host "Health check OK."

Write-Host "2. Testing /ready..."
$ready = Invoke-RestMethod -Uri "$baseUrl/ready" -Method Get
if ($ready.status -ne "ready" -and $ready.status -ne "degraded") { throw "Ready check failed" }
Write-Host "Ready check OK."

Write-Host "3. Testing POST /api/chat (Message 1)..."
$body1 = @{ query = "What is IS 302?"; lang = "en"; use_rag = $true } | ConvertTo-Json
$chat1 = Invoke-RestMethod -Uri "$baseUrl/api/chat" -Method Post -Headers $headers -ContentType "application/json" -Body $body1
$sessionId = $chat1.session_id
if (-not $sessionId) { throw "Chat 1 failed to return session_id" }
Write-Host "Chat 1 OK. Session ID: $sessionId"

Write-Host "4. Testing POST /api/chat (Message 2 with same session)..."
$body2 = @{ query = "Tell me more about safety requirements.", session_id = $sessionId, lang = "en" } | ConvertTo-Json
$chat2 = Invoke-RestMethod -Uri "$baseUrl/api/chat" -Method Post -Headers $headers -ContentType "application/json" -Body $body2
if ($chat2.session_id -ne $sessionId) { throw "Chat 2 session ID mismatch" }
Write-Host "Chat 2 OK."

Write-Host "5. Testing GET /sessions..."
$sessions = Invoke-RestMethod -Uri "$baseUrl/sessions" -Method Get -Headers $headers
if ($sessions.Count -lt 1) { throw "GET /sessions returned no sessions" }
Write-Host "GET /sessions OK."

Write-Host "6. Testing GET /sessions/$sessionId/messages..."
$messages = Invoke-RestMethod -Uri "$baseUrl/sessions/$sessionId/messages" -Method Get -Headers $headers
if ($messages.Count -lt 4) { throw "GET messages returned fewer messages than expected" }
Write-Host "GET messages OK."

Write-Host "SMOKE TEST PASSED SUCCESSFULLY."
