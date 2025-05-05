# Script PowerShell pour tester le failover automatique de Redis Sentinel

# Verifier si un argument est fourni
param (
    [Parameter(Mandatory=$true)]
    [string]$Location
)

# Verifier si l'emplacement est valide
$validLocations = @("salon", "chambre1", "chambre2", "cuisine", "salle-de-bain")
if ($validLocations -notcontains $Location) {
    Write-Host "Emplacement non valide. Utilisez: salon, chambre1, chambre2, cuisine, salle-de-bain"
    exit 1
}

Write-Host "Emplacement valide: $Location"

# Arreter le maitre pour simuler une panne
$masterContainer = "redis-$Location-master"

Write-Host "Simulation d'une panne sur $masterContainer..."
docker stop $masterContainer

Write-Host "Maitre arrete. Verification du statut des sentinels pour $Location..."

# Fonction pour afficher l'etat d'un sentinel
function Check-SentinelStatus {
    param (
        [string]$sentinelContainer,
        [string]$masterName
    )

    Write-Host "Etat de $sentinelContainer"
    # Utiliser redis-cli pour verifier l'etat du sentinel
    docker exec $sentinelContainer redis-cli -p 26379 info sentinel
    docker exec $sentinelContainer redis-cli -p 26379 sentinel master $masterName | Select-String -Pattern "(ip|port|flags)"
}

# Determiner le nom du groupe maitre dans sentinel
if ($Location -eq "salle-de-bain") {
    $masterName = "sdb-master"
} else {
    $masterName = "$Location-master"
}

# Verifier tous les sentinels pour cet emplacement
For ($i=1; $i -le 3; $i++) {
    $sentinelContainer = "redis-$Location-sentinel$i"
    Check-SentinelStatus -sentinelContainer $sentinelContainer -masterName $masterName
    Write-Host "----------------------------------------"
}

Write-Host "Attendez quelques secondes pour que le failover se produise..."
Start-Sleep -Seconds 10

Write-Host "Verification apres failover..."
For ($i=1; $i -le 3; $i++) {
    $sentinelContainer = "redis-$Location-sentinel$i"
    Check-SentinelStatus -sentinelContainer $sentinelContainer -masterName $masterName
    Write-Host "----------------------------------------"
}

Write-Host "Test de failover termine. Le replica devrait maintenant etre promu en tant que nouveau maitre."
Write-Host "Pour redemarrer l'ancien maitre (qui deviendra un replica): docker start $masterContainer"