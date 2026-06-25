#Requires -Version 5.1
# Quick health check for the local dev stack.
$urls = @(
    @{ Name = "ai-core"; Url = "http://localhost:8090/health" },
    @{ Name = "be";      Url = "http://localhost:8080/health" },
    @{ Name = "fe";      Url = "http://localhost:3000" },
    @{ Name = "desktop"; Url = "http://localhost:5173" }
)

foreach ($u in $urls) {
    try {
        $r = Invoke-WebRequest -Uri $u.Url -UseBasicParsing -TimeoutSec 5
        Write-Host ("OK  {0,-10} {1} -> {2}" -f $u.Name, $u.Url, $r.StatusCode)
    } catch {
        Write-Host ("FAIL {0,-10} {1}" -f $u.Name, $u.Url)
    }
}
