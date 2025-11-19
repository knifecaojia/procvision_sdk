param(
    [Parameter(Mandatory=$true)]
    [string]$TagName
)

# Check if tag name is provided as parameter
if (-not $TagName) {
    Write-Host "Usage: .\tag-recreate.ps1 <tag-name>"
    exit 1
}

# Delete local tag
Write-Host "Deleting local tag $TagName..."
git tag -d $TagName
if ($LASTEXITCODE -eq 0) {
    Write-Host "Successfully deleted local tag $TagName"
} else {
    Write-Host "Failed to delete local tag or tag does not exist"
}

# Delete remote tag
Write-Host "Deleting remote tag $TagName..."
git push origin --delete $TagName
if ($LASTEXITCODE -eq 0) {
    Write-Host "Successfully deleted remote tag $TagName"
} else {
    Write-Host "Failed to delete remote tag or tag does not exist"
}

# Recreate local tag
Write-Host "Recreating local tag $TagName..."
git tag $TagName
if ($LASTEXITCODE -eq 0) {
    Write-Host "Successfully created local tag $TagName"
} else {
    Write-Host "Failed to create local tag"
    exit 1
}

# Push new tag to remote
Write-Host "Pushing tag $TagName to remote..."
git push origin $TagName
if ($LASTEXITCODE -eq 0) {
    Write-Host "Successfully pushed tag $TagName to remote"
} else {
    Write-Host "Failed to push tag to remote"
    exit 1
}

Write-Host "Tag $TagName has been successfully recreated and pushed to remote!"