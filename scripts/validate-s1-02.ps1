$ErrorActionPreference = "Stop"

Write-Host "[S1-02] Starting PostgreSQL container..."
docker compose -f db/docker-compose.yml up -d
if ($LASTEXITCODE -ne 0) {
  throw "Failed to start PostgreSQL container via docker compose."
}

Write-Host "[S1-02] Verifying Docker daemon and container status..."
$container = docker ps --filter "name=fing-postgres" --format "{{.Names}} {{.Status}}"
if (-not $container) {
    throw "PostgreSQL container 'fing-postgres' is not running."
}
Write-Host "[S1-02] Container status: $container"

Write-Host "[S1-02] Running Flyway startup validation test using Dockerized Maven..."
docker run --rm `
  --add-host host.docker.internal:host-gateway `
  -e DB_URL=jdbc:postgresql://host.docker.internal:5432/fing `
  -e DB_USERNAME=fing `
  -e DB_PASSWORD=fing `
  -v ${PWD}/backend:/workspace `
  -w /workspace `
  maven:3.9.9-eclipse-temurin-21 `
  mvn -Dtest=FlywayStartupValidationTest test
if ($LASTEXITCODE -ne 0) {
    throw "Flyway startup validation test failed."
}

Write-Host "[S1-02] Validation completed successfully."
