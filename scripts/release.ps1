param(
  [ValidateSet("patch", "minor", "major")]
  [string]$Part = "patch",

  [string]$Remote = "origin",
  [string]$Branch = "main",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Run-Git {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)

  $command = "git $($Args -join ' ')"
  Write-Host $command

  if (-not $DryRun) {
    & git @Args
    if ($LASTEXITCODE -ne 0) {
      exit $LASTEXITCODE
    }
  }
}

function Get-LatestVersionTag {
  $tags = git tag --list "v[0-9]*.[0-9]*.[0-9]*" --sort=-v:refname
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }

  foreach ($tag in $tags) {
    if ($tag -match "^v(\d+)\.(\d+)\.(\d+)$") {
      return [pscustomobject]@{
        Tag = $tag
        Major = [int]$Matches[1]
        Minor = [int]$Matches[2]
        Patch = [int]$Matches[3]
      }
    }
  }

  return [pscustomobject]@{
    Tag = $null
    Major = 0
    Minor = 0
    Patch = 0
  }
}

function Set-VersionInFile {
  param(
    [string]$Path,
    [string]$Pattern,
    [string]$Replacement
  )

  $content = Get-Content -LiteralPath $Path -Raw
  $updated = $content -replace $Pattern, $Replacement

  if ($content -eq $updated) {
    throw "Version pattern was not found in $Path"
  }

  if ($DryRun) {
    Write-Host "Would update $Path"
  } else {
    Set-Content -LiteralPath $Path -Value $updated -NoNewline
  }
}

$status = git status --porcelain
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

if ($status) {
  throw "Working tree is not clean. Commit or stash your changes before releasing."
}

Run-Git fetch $Remote --tags
Run-Git checkout $Branch
Run-Git pull --ff-only $Remote $Branch

$latest = Get-LatestVersionTag
$major = $latest.Major
$minor = $latest.Minor
$patch = $latest.Patch

switch ($Part) {
  "major" {
    $major += 1
    $minor = 0
    $patch = 0
  }
  "minor" {
    $minor += 1
    $patch = 0
  }
  "patch" {
    $patch += 1
  }
}

$version = "$major.$minor.$patch"
$tag = "v$version"

Write-Host "Latest tag: $(if ($latest.Tag) { $latest.Tag } else { '<none>' })"
Write-Host "Next tag:   $tag"

if ((git tag --list $tag) -contains $tag) {
  throw "Tag $tag already exists."
}

Set-VersionInFile `
  -Path "pyproject.toml" `
  -Pattern 'version = "\d+\.\d+\.\d+"' `
  -Replacement "version = `"$version`""

Set-VersionInFile `
  -Path "packaging\npu.iss" `
  -Pattern '#define AppVersion "\d+\.\d+\.\d+"' `
  -Replacement "#define AppVersion `"$version`""

Set-VersionInFile `
  -Path "npu\__init__.py" `
  -Pattern '__version__ = "\d+\.\d+\.\d+"' `
  -Replacement "__version__ = `"$version`""

Run-Git add pyproject.toml packaging\npu.iss npu\__init__.py
Run-Git commit -m "Release $tag"
Run-Git tag $tag
Run-Git push $Remote $Branch
Run-Git push $Remote $tag

Write-Host "Release tag pushed. GitHub Actions should build and publish $tag."
