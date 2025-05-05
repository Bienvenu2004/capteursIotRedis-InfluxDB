# Supprimer les anciens conteneurs
docker ps -a -q --filter "name=redis-*" | ForEach-Object { docker stop $_; docker rm $_ }

# Supprimer l'ancien réseau (s'il existe)
docker network rm redis-net 2>$null

# Supprimer les anciens volumes
docker volume ls -q --filter "name=redis-*" | ForEach-Object { docker volume rm $_ }

# Créer un réseau Docker
docker network create redis-net

# Liste des emplacements
$locations = @("salon", "chambre1", "chambre2", "cuisine", "salle-de-bain")

# Configuration des ports de base
$baseRedisPort = 6379
$baseSentinelPort = 26379

# Dictionnaire pour stocker les IPs des masters
$masterIPs = @{}

foreach ($loc in $locations) {
    $locSlug = $loc -replace '-', '_'

    # Ports dynamiques
    $redisPortMaster = $baseRedisPort
    $baseRedisPort++
    $redisPortReplica = $baseRedisPort
    $baseRedisPort++

    # --- Maître ---
    docker run -d --name "redis-$loc-master" --network redis-net -p "${redisPortMaster}:6379" `
        -v "redis-$loc-master-data:/data" `
        -e "REDIS_ARGS=--requirepass strongpassword --masterauth strongpassword --appendonly yes" `
        redis/redis-stack

    # Attendre que le conteneur soit prêt
    Start-Sleep -Seconds 3

    # Récupérer l'adresse IP du master
    $masterIP = docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "redis-$loc-master"
    $masterIPs[$loc] = $masterIP
    Write-Host "Master $loc IP: $masterIP"

    # --- Réplica ---
    docker run -d --name "redis-$loc-replica" --network redis-net -p "${redisPortReplica}:6379" `
        -v "redis-$loc-replica-data:/data" `
        -e "REDIS_ARGS=--requirepass strongpassword --masterauth strongpassword --appendonly yes --replicaof redis-$loc-master 6379" `
        redis/redis-stack

    # Attendre avant de démarrer les sentinels
    Start-Sleep -Seconds 2
}

# Démarrer les sentinels après avoir configuré tous les masters
foreach ($loc in $locations) {
    # Récupérer l'IP stockée
    $masterIP = $masterIPs[$loc]

    # --- Sentinels ---
    for ($i=1; $i -le 3; $i++) {
        $sentinelName = "redis-$loc-sentinel$i"
        $tempDir = "C:\Temp\$sentinelName"
        if (-not (Test-Path $tempDir)) {
            New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
        }

        if ($loc -eq "salle-de-bain") {
            $sentinelId = "sdb-master"
        } else {
            $sentinelId = "$loc-master"
        }

        @"
sentinel monitor $sentinelId $masterIP 6379 2
sentinel down-after-milliseconds $sentinelId 5000
sentinel failover-timeout $sentinelId 60000
sentinel parallel-syncs $sentinelId 1
sentinel auth-pass $sentinelId strongpassword
"@ | Out-File -FilePath "$tempDir\sentinel.conf" -Encoding ascii

        docker run -d --name $sentinelName --network redis-net `
            -p "$($baseSentinelPort):26379" `
            -v "${tempDir}:/etc/redis/" `
            redis:latest redis-sentinel /etc/redis/sentinel.conf

        $baseSentinelPort++
    }
}

# Résultat
Write-Host "`n✅ Déploiement terminé. Conteneurs Redis Stack en cours d'exécution :"
docker ps --filter "name=redis-*"

# Créer le répertoire pour les métadonnées du sharding s'il n'existe pas
if (-not (Test-Path "sharding_metadata")) {
    New-Item -ItemType Directory -Path "sharding_metadata" -Force | Out-Null
    Write-Host "Répertoire 'sharding_metadata' créé"
}