$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$release = Get-Date -Format "yyyyMMdd-HHmmss"
$archive = Join-Path ([System.IO.Path]::GetTempPath()) "physais-grade-dashboard-$release.tar.gz"
$remoteArchive = "/tmp/physais-grade-dashboard-$release.tar.gz"
$remoteConfig = "/tmp/stat.physais.ru.conf"

try {
    Write-Host "==> Package dashboard"
    tar.exe -czf $archive -C (Join-Path $projectRoot "dist") .

    Write-Host "==> Upload release"
    scp $archive "physics-ai-vds:$remoteArchive"
    if ($LASTEXITCODE -ne 0) { throw "Dashboard upload failed with exit code $LASTEXITCODE" }
    scp (Join-Path $projectRoot "deploy\nginx-stat.physais.ru.conf") "physics-ai-vds:$remoteConfig"
    if ($LASTEXITCODE -ne 0) { throw "Nginx config upload failed with exit code $LASTEXITCODE" }

    Write-Host "==> Activate release and Nginx site"
    ssh physics-ai-vds "set -e; mkdir -p /var/www/physais-grade-dashboard/releases/$release; tar -xzf $remoteArchive -C /var/www/physais-grade-dashboard/releases/$release; ln -sfn /var/www/physais-grade-dashboard/releases/$release /var/www/physais-grade-dashboard/current; install -m 644 $remoteConfig /etc/nginx/sites-available/stat.physais.ru; ln -sfn /etc/nginx/sites-available/stat.physais.ru /etc/nginx/sites-enabled/stat.physais.ru; nginx -t; systemctl reload nginx; rm -f $remoteArchive $remoteConfig; sleep 1; curl -fsS https://stat.physais.ru/ >/dev/null"
    if ($LASTEXITCODE -ne 0) { throw "Remote activation failed with exit code $LASTEXITCODE" }

    Write-Host "==> HTTPS deployment ready: https://stat.physais.ru"
}
finally {
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }
}
