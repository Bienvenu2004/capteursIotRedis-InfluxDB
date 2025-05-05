# Supprimer l'ancien conteneur InfluxDB s'il existe
docker rm -f influxdb 2>$null

# Supprimer l'ancien volume pour repartir de zéro
docker volume rm influxdb-data 2>$null

# Créer le volume
docker volume create influxdb-data

# Démarrer InfluxDB avec une configuration simplifiée
docker run -d --name influxdb --network redis-net `
    -p 8086:8086 `
    -v influxdb-data:/var/lib/influxdb2 `
    -e DOCKER_INFLUXDB_INIT_MODE=setup `
    -e DOCKER_INFLUXDB_INIT_USERNAME=admin `
    -e DOCKER_INFLUXDB_INIT_PASSWORD=strongpassword `
    -e DOCKER_INFLUXDB_INIT_ORG=tp_iot `
    -e DOCKER_INFLUXDB_INIT_BUCKET=sensors_archive `
    -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=my-super-secret-token `
    influxdb:2.7

# Attendre que le service soit prêt
Write-Host "Attente du démarrage d'InfluxDB..."
Start-Sleep -Seconds 10

# Obtenir le token depuis le conteneur Docker
Write-Host "Récupération du token InfluxDB:"
docker exec influxdb influx auth list --user admin -o tp_iot --json | Out-Host

Write-Host "`nInfluxDB est prêt sur http://localhost:8086"
Write-Host "Login: admin / strongpassword"