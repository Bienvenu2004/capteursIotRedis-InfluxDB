# Instructions pour Windows PowerShell

Pour exécuter la configuration Redis avec réplication et failover automatique sur Windows 11 avec PowerShell, suivez les instructions ci-dessous.

## Préparation

1. Assurez-vous que Docker Desktop est en cours d'exécution sur votre système Windows.

2. Créez un dossier temporaire pour les fichiers de configuration de Sentinel :
   ```powershell
   New-Item -ItemType Directory -Path "C:\Temp" -Force
   ```

## Installation

1. **Enregistrez le script PowerShell** pour la configuration Redis :
   - Copiez le contenu du script `docker-redis-sentinel-setup-windows.ps1` dans un fichier texte
   - Enregistrez-le avec l'extension `.ps1` (par exemple, `C:\Users\VotreNom\redis-setup.ps1`)

2. **Exécutez le script** pour créer tous les conteneurs :
   ```powershell
   # Accédez au dossier où vous avez enregistré le script
   cd C:\Users\VotreNom
   
   # Exécutez le script PowerShell
   .\redis-setup.ps1
   ```

## Vérification de l'installation

Vérifiez que tous les conteneurs ont été créés avec succès :
```powershell
docker ps -a --filter "name=redis-*"
```

Vous devriez voir 25 conteneurs au total (5 maîtres, 5 réplicas et 15 sentinels).

## Test de la réplication

Pour tester la configuration et l'envoi de données :

1. **Enregistrez le script Python** de test client :
   - Copiez le contenu du script `redis-client-script.py` dans un fichier texte
   - Enregistrez-le avec l'extension `.py` (par exemple, `C:\Users\VotreNom\redis-client.py`)

2. **Installez les dépendances Python** :
   ```powershell
   pip install redis
   ```

3. **Exécutez le script client** :
   ```powershell
   python C:\Users\VotreNom\redis-client.py --location salon
   ```

## Test du failover automatique

Pour vérifier que le failover fonctionne correctement :

1. **Enregistrez le script PowerShell** pour tester le failover :
   - Copiez le contenu du script `failover-test-script-powershell.ps1` dans un fichier texte
   - Enregistrez-le avec l'extension `.ps1` (par exemple, `C:\Users\VotreNom\test-failover.ps1`)

2. **Exécutez le script de test** :
   ```powershell
   # Simuler une panne dans le salon
   .\test-failover.ps1 -Location salon
   ```

## Commandes utiles pour Windows PowerShell

- **Vérifier l'état de réplication** : 
  ```powershell
  docker exec -it redis-salon-master redis-cli -a strongpassword info replication
  ```

- **Vérifier l'état des sentinels** : 
  ```powershell
  docker exec -it redis-salon-sentinel1 redis-cli -p 26379 info sentinel
  ```

- **Forcer manuellement un failover** (si nécessaire) : 
  ```powershell
  docker exec -it redis-salon-sentinel1 redis-cli -p 26379 sentinel failover salon-master
  ```

- **Redémarrer un conteneur** : 
  ```powershell
  docker restart redis-salon-master
  ```

- **Arrêter tous les conteneurs Redis** (en cas de besoin) :
  ```powershell
  docker ps -a -q --filter "name=redis-*" | ForEach-Object { docker stop $_ }
  ```

## Résolution des problèmes

1. **Problème de montage des volumes** : Si vous rencontrez des problèmes avec les volumes Docker, essayez d'utiliser un chemin absolu au lieu de noms de volumes :
   ```powershell
   # Exemple de modification pour le montage de volume
   -v "C:\Docker\redis-data\salon-master:/data"
   ```

2. **Problème d'accès à C:\Temp** : Si PowerShell signale un problème d'accès au dossier temporaire, utilisez un autre emplacement pour les fichiers de configuration, par exemple :
   ```powershell
   $tempDir = "$env:USERPROFILE\Documents\redis-config\redis-salon-sentinel$i"
   ```

3. **Problème de connexion réseau** : Vérifiez que le réseau `redis-net` a été correctement créé :
   ```powershell
   docker network inspect redis-net
   ```