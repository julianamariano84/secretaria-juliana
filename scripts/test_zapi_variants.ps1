<#
scripts/test_zapi_variants.ps1
Teste automático de variantes Z-API (PowerShell)

Usage examples:
.\scripts\test_zapi_variants.ps1 -Token 'FE235...' -InstanceId '3E68F...' -Phone '5522988045181'
or
.\scripts\test_zapi_variants.ps1 -BaseUrl 'https://api.z-api.io/instances/.../token/.../send-text' -Phone '5522988045181'

#>

param(
    [string]$BaseUrl = "",
    [string]$InstanceId = "",
    [string]$Token = "",
    [string]$Phone = "5522988045181",
    [switch]$VerboseOut
)

function TryRequest {
    param($url, $headers, $payload, $label)

    Write-Host "==== TRY: $label ====" -ForegroundColor Cyan
    Write-Host "URL: $url"
    Write-Host "HEADERS: $(($headers.Keys | ForEach-Object { "$_=$($headers[$_])" }) -join '; ')"
    Write-Host "PAYLOAD: $payload"
    try {
        $resp = Invoke-WebRequest -Uri $url -Method Post -Body $payload -ContentType 'application/json' -Headers $headers -UseBasicParsing -ErrorAction Stop
        Write-Host "`nStatusCode: $($resp.StatusCode) - $($resp.StatusDescription)"
        Write-Host "`nHeaders:"
        $resp.Headers.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Name): $($_.Value)" }
        Write-Host "`nBody:`n$($resp.Content)`n"
    } catch {
        # If server returned an HTTP error, try to read the response body
        Write-Host "`nERROR: $($_.Exception.Message)" -ForegroundColor Yellow
        if ($_.Exception.Response) {
            $r = $_.Exception.Response
            try {
                $stream = $r.GetResponseStream(); $reader = New-Object System.IO.StreamReader($stream); $text = $reader.ReadToEnd()
                Write-Host "`nStatusCode (error): $($r.StatusCode.Value__)"
                Write-Host "`nBody:`n$text`n"
            } catch {
                Write-Host "Could not read response body."
            }
        }
    }
    Write-Host "==== END ====`n"
}

# Build candidate base URLs
$urls = @()
if ($BaseUrl -ne "") {
    $urls += $BaseUrl.TrimEnd('/')
} else {
    if ($InstanceId -and $Token) {
        $root = "https://api.z-api.io/instances/$InstanceId"
        $urls += ("$root/token/$Token/send-text")
        $urls += ("$root/token/$Token/send-message")
        $urls += ("$root/send-text")
        $urls += ("$root/send-message")
        $urls += ("$root/send-text?token=$Token")
        $urls += ("$root/send-message?token=$Token")
    } elseif ($InstanceId) {
        $root = "https://api.z-api.io/instances/$InstanceId"
        $urls += ("$root/send-text")
        $urls += ("$root/send-message")
    } else {
        Write-Host 'Either -BaseUrl or -InstanceId must be provided.' -ForegroundColor Red
        exit 1
    }
}

# Deduplicate
$urls = $urls | Select-Object -Unique

# Payload variants
$payloads = @()
$payloads += @{ phone = $Phone; message = 'Teste diagnóstico - phone/message' } 
$payloads += @{ to = $Phone; message = 'Teste diagnóstico - to/message' }
$payloads += @{ to = "$Phone@c.us"; message = 'Teste diagnóstico - to@c.us' }
$payloads += @{ to = $Phone; type = 'text'; text = @{ body = 'Teste diagnóstico - text.body' } }
$payloads += @{ chatId = $Phone; body = 'Teste diagnóstico - chatId/body' }
$payloads += @{ number = $Phone; message = 'Teste diagnóstico - number/message' }

# Header combos
$headerCombos = @()
# 1) Bearer
$headerCombos += @{ Authorization = "Bearer $Token" }
# 2) Client-Token
$headerCombos += @{ 'Client-Token' = $Token }
# 3) Both
$headerCombos += @{ Authorization = "Bearer $Token"; 'Client-Token' = $Token }
# 4) No auth
$headerCombos += @{}

# Try combinations
$attempt = 0
foreach ($u in $urls) {
    foreach ($h in $headerCombos) {
        foreach ($p in $payloads) {
            $attempt++
            $label = "#${attempt} url=$u headers=$(($h.Keys -join ',') -replace '^$','none') payload_type=$(($p.Keys -join ','))"
            $json = $p | ConvertTo-Json -Depth 10
            TryRequest -url $u -headers $h -payload $json -label $label
            Start-Sleep -Milliseconds 250
        }
    }
}

Write-Host "All attempts finished. Review output above for StatusCode and Body. Look for attempts that returned a successful message object (no error)." -ForegroundColor Green
 
Invoke-History