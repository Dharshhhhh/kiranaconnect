$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Check-Step($label) {
    if ($LASTEXITCODE -ne 0) { throw "$label failed. Check the message above." }
}
if (!(Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    $content = Get-Content '.env' -Raw
    foreach ($role in @('OWNER')) {
        $password = [guid]::NewGuid().ToString('N')
        $content = $content.Replace("${role}_PASSWORD=", "${role}_PASSWORD=$password")
    }
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot '.env'), $content)
    Write-Host 'Created local owner password. Open .env to see them.'
}
if (!(Test-Path '.venv/Scripts/python.exe')) {
    py -3.12 -m venv .venv
    Check-Step 'Creating Python 3.12 environment'
}
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $python -m pip install -r requirements.txt
Check-Step 'Installing dependencies'
& $python -m backend.seed
Check-Step 'Seeding'
Write-Host 'Open http://127.0.0.1:8000 and sign in as owner.'
& $python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
