param(
    [string]$Root = (Join-Path $PSScriptRoot '../../local/upstream'),
    [string]$SevenZip = '7z.exe'
)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath($Root)

function Get-VerifiedPackage([string]$Url, [string]$Path, [string]$Sha256) {
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Force ([IO.Path]::GetDirectoryName($Path)) | Out-Null
        Invoke-WebRequest $Url -OutFile $Path
    }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Sha256) {
        throw "Package hash mismatch: $Path"
    }
}

$SdkZip = Join-Path $Root 'rexglue/sdk.zip'
$SdkDir = Join-Path $Root 'rexglue/sdk'
$SdkExe = Join-Path $SdkDir 'win-amd64/bin/rexglue.exe'
Get-VerifiedPackage 'https://github.com/rexglue/rexglue-sdk/releases/download/v0.10.0/rexglue-sdk-0.10.0-win-amd64.zip' $SdkZip 'AD4485DA853FBE932E9F5DBB643F9B5FE85DC73775EBBAD4DF6879FE6DF0C11B'
if (-not (Test-Path -LiteralPath $SdkDir)) { Expand-Archive -LiteralPath $SdkZip -DestinationPath $SdkDir }
if ((Get-FileHash -LiteralPath $SdkExe -Algorithm SHA256).Hash -ne '04014C2E5EEF3C40BDDC490D413E910E5BA98D81AA3DA1C1F5D43DD29728EE3A') {
    throw 'SDK executable hash mismatch'
}

$LlvmPackage = Join-Path $Root 'llvm/LLVM-20.1.8-win64.exe'
$LlvmDir = Join-Path $Root 'llvm/unpacked'
$Compiler = Join-Path $LlvmDir 'bin/clang-cl.exe'
Get-VerifiedPackage 'https://github.com/llvm/llvm-project/releases/download/llvmorg-20.1.8/LLVM-20.1.8-win64.exe' $LlvmPackage '3197846A2B19063687DD56E93E34CD941E3548D907F23A6131571321BDF9FE7B'
if (-not (Test-Path -LiteralPath $LlvmDir)) {
    # Read the NSIS archive with 7-Zip; never execute the installer.
    & $SevenZip x $LlvmPackage "-o$LlvmDir" 'bin/clang-cl.exe' 'bin/clang.exe' 'bin/clang++.exe' 'lib/clang/*' 'LICENSE*' -y
    if ($LASTEXITCODE -ne 0) { throw "LLVM archive extraction exit=$LASTEXITCODE" }
}
if ((Get-FileHash -LiteralPath $Compiler -Algorithm SHA256).Hash -ne '57E32B1EA2456F12F97BF802453171BBFF12D56B2C486B4ECA0C75343C0CDA2C') {
    throw 'Clang executable hash mismatch'
}
& $Compiler --version
if ($LASTEXITCODE -ne 0) { throw "Clang version probe exit=$LASTEXITCODE" }
[PSCustomObject]@{SdkZip=$SdkZip; SdkExe=$SdkExe; LlvmPackage=$LlvmPackage; Compiler=$Compiler; Installation='local extraction only; no global changes'}
