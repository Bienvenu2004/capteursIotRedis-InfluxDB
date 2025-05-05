Analyse et stockage des données temporelles pour capteurs IoT avec Redis (Time-Series) et InfluxDB
📝 Description du projet
Ce projet propose une solution complète pour collecter, stocker et analyser des données temporelles provenant de capteurs IoT répartis dans différentes pièces d'une maison. Il utilise :

Redis avec le module Time-Series pour le stockage haute performance des données de capteurs

True Sharding avec une instance Redis dédiée par emplacement (salon, chambre, etc.)

Redis Sentinel pour la haute disponibilité avec mécanismes de failover automatique

InfluxDB pour l'archivage à long terme et l'analyse des données

🛠 Prérequis
Avant de commencer, assurez-vous d'avoir installé :

Docker (version 20.10.7 ou ultérieure)

Docker Compose (optionnel)

PowerShell (pour exécuter les scripts sous Windows)

Python 3.8+ avec pip (pour les scripts de génération de données)

🚀 Installation et démarrage
1. Clonez le dépôt du projet

2. Démarrez l'infrastructure avec Docker
Le projet fournit des scripts PowerShell pour configurer l'environnement :

a. Démarrer Redis avec le sharding et Sentinel
powershell
.\docker-redis-sentinel-setup-windows.ps1
Ce script va :

Créer un réseau Docker redis-net

Démarrer 5 instances Redis (une par emplacement) avec leurs réplicas

Configurer 3 instances Sentinel par emplacement pour le monitoring et failover

Exposer les ports Redis de 6379 à 6388 et les ports Sentinel de 26379 à 26393

b. Démarrer InfluxDB pour l'archivage
powershell
.\setup-influxdb.ps1
Ce script va :

Créer un volume Docker pour la persistance des données

Démarrer InfluxDB 2.7 avec une configuration initiale

Configurer un utilisateur admin (admin/strongpassword)

Créer un bucket sensors_archive pour stocker les données

3. Générer les données de test
powershell
python .\generate_sharding_data.py
Ce script Python va :

Créer les séries temporelles dans chaque instance Redis

Générer des données historiques pour les 7 derniers jours

Démarrer la génération de données en temps réel

4. Démarrer l'archivage vers InfluxDB
powershell
python .\influxdb_archiver.py
Ce script va :

Se connecter à InfluxDB avec le token configuré

Archiver périodiquement les données Redis vers InfluxDB

Vérifier que l'archivage fonctionne correctement

🏗 Architecture du projet
.
├── deploy_influxdb.ps1          # Script de déploiement InfluxDB
├── deploy_redis.ps1             # Script de déploiement Redis
├── generate_sharding_data.py    # Script de génération de données
├── influxdb_archiver.py         # Script d'archivage vers InfluxDB
├── sharding_metadata/           # Dossier des métadonnées de sharding
└── test_failover.ps1            # Script de test de failover
📊 Structure des données
Données des capteurs
Chaque capteur est identifié par :

Type : temperature, humidity ou air_quality

Emplacement : salon, chambre1, chambre2, cuisine, salle_de_bain

ID : Numéro unique du capteur (1 à 3 par type et par emplacement)

Exemple de clé Redis : sensor:temperature:salon:1

Sharding
Chaque emplacement a son propre serveur Redis :

Salon : port 6379

Chambre1 : port 6381

Chambre2 : port 6383

Cuisine : port 6385

Salle de bain : port 6387

🔍 Fonctionnalités clés
1. Monitoring des shards
Le script Python fournit des fonctions pour vérifier l'état des shards :

python
sharding_system.get_shards_status()  # Statut de santé
sharding_system.get_shard_distribution_metrics()  # Distribution des données
2. Requêtes avancées
Requête par emplacement :

python
sharding_system.query_location_data("salon", "temperature", start_time, end_time)
Requête par unité de mesure (interroge tous les shards) :

python
sharding_system.query_by_unit_measure("celsius", start_time, end_time)
3. Test de failover
Le script test_failover.ps1 permet de tester le mécanisme de failover :

powershell
.\failover-test-script-powershell.ps1 -Location salon
Ce script va :

Arrêter le conteneur Redis master pour le salon

Surveiller les Sentinels pendant le processus de failover

Afficher le nouveau master promu

4. Archivage vers InfluxDB
L'archivage se fait automatiquement avec :

Archivage initial des données historiques

Archivage périodique toutes les 5 minutes

🛠 Maintenance
Redémarrer un conteneur Redis
Si un conteneur master a été arrêté pour un test de failover, vous pouvez le redémarrer :

powershell
docker start redis-salon-master
Il se reconnectera automatiquement comme réplica du nouveau master.

Accéder aux interfaces
InfluxDB UI : http://localhost:8086

Utilisateur : admin

Mot de passe : strongpassword

Redis Insight (optionnel) : Vous pouvez déployer Redis Insight pour une interface de gestion :

powershell
docker run -d --name redis-insight -p 8001:8001 redislabs/redisinsight
Puis accédez à http://localhost:8001

📈 Exemple de requêtes Flux pour InfluxDB
Une fois les données archivées, vous pouvez utiliser le langage Flux pour les analyser :

flux
from(bucket: "sensors_archive")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r.location == "salon")
  |> aggregateWindow(every: 1m, fn: mean)
🚨 Dépannage
Problèmes de connexion
Redis ne répond pas :

Vérifiez que les conteneurs sont en cours d'exécution : docker ps

Vérifiez les logs : docker logs redis-salon-master

Authentification InfluxDB échouée :

Régénérez le token admin :

powershell
docker exec influxdb influx auth create --user admin --org tp_iot --all-access
Mettez à jour le token dans influxdb_archiver.py

Problèmes de performances
Si le système est lent :

Augmentez les ressources Docker (CPU/Mémoire)

Réduisez la fréquence de génération de données dans generate_sharding_data.py

📚 Ressources
Documentation Redis Time-Series

Documentation InfluxDB

Guide Redis Sentinel
