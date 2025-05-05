import redis
import time
import random
from datetime import datetime, timedelta
import json
import os


class RedisTrueShardingSystem:
    def __init__(self):
        # Configuration pour le true sharding - une instance Redis par emplacement
        self.locations = ["salon", "chambre1", "chambre2", "cuisine", "salle_de_bain"]

        # Mot de passe pour l'authentification Redis
        self.redis_password = "strongpassword"

        # Configuration des shards - uniquement les masters pour éviter les erreurs "read only replica"
        self.shards = {
            "salon": {"host": "localhost", "port": 6379, "container": "redis-salon-master"},
            "chambre1": {"host": "localhost", "port": 6381, "container": "redis-chambre1-master"},
            "chambre2": {"host": "localhost", "port": 6383, "container": "redis-chambre2-master"},
            "cuisine": {"host": "localhost", "port": 6385, "container": "redis-cuisine-master"},
            "salle_de_bain": {"host": "localhost", "port": 6387, "container": "redis-salle-de-bain-master"}
        }

        # Paramètres de simulation
        self.sensor_types = ["temperature", "humidity", "air_quality"]
        self.num_sensors = 3  # Nombre de capteurs par type et par emplacement

        # Définir les unités de mesure pour chaque type de capteur
        self.unit_measures = {
            "temperature": "celsius",
            "humidity": "percent",
            "air_quality": "aqi"
        }

        # Connexion aux instances Redis
        self.connections = {}
        for location, config in self.shards.items():
            try:
                # Utilisation explicite de l'option decode_responses pour éviter les problèmes de bytes vs string
                self.connections[location] = redis.Redis(
                    host=config["host"],
                    port=config["port"],
                    password=self.redis_password,
                    decode_responses=True
                )
                # Vérification que le serveur répond et n'est pas en lecture seule
                if not self.connections[location].ping():
                    raise Exception("Le serveur ne répond pas au ping")

                # Vérifier si le serveur est en lecture seule
                if self.connections[location].info("replication").get("role") == "slave":
                    raise Exception("Ce serveur est un réplica en lecture seule")

                print(f"Connecté au shard {location}: {config['host']}:{config['port']} ({config['container']})")
            except Exception as e:
                print(f"Erreur de connexion au shard {location}: {e}")
                # Si la connexion échoue, retirer ce shard de la liste des connexions
                if location in self.connections:
                    del self.connections[location]

        # Création d'un répertoire pour stocker la configuration et les méta-données
        os.makedirs("sharding_metadata", exist_ok=True)

        # Sauvegarder la configuration du sharding
        self.save_sharding_config()

    def save_sharding_config(self):
        """Sauvegarde la configuration de sharding dans un fichier JSON"""
        config = {
            "shards": {loc: {k: v for k, v in cfg.items() if k != "password"}
                       for loc, cfg in self.shards.items()},  # Ne pas inclure le mot de passe
            "locations": self.locations,
            "sensor_types": self.sensor_types,
            "unit_measures": self.unit_measures
        }
        with open("sharding_metadata/true_sharding_config.json", "w") as f:
            json.dump(config, f, indent=2)
        print("Configuration de true sharding sauvegardée")

    def get_connection_for_location(self, location):
        """Récupère la connexion Redis pour une localisation spécifique"""
        if location in self.connections:
            return self.connections[location]
        else:
            raise ValueError(f"Location '{location}' non prise en charge ou connexion non disponible")

    def create_time_series(self):
        """Crée les séries temporelles pour chaque capteur dans son shard dédié"""
        # Utiliser uniquement les emplacements pour lesquels nous avons une connexion valide
        for location in list(self.connections.keys()):
            conn = self.get_connection_for_location(location)
            for sensor_type in self.sensor_types:
                unit_measure = self.unit_measures[sensor_type]
                for sensor_id in range(1, self.num_sensors + 1):
                    key = f"sensor:{sensor_type}:{location}:{sensor_id}"
                    try:
                        # Vérifier si la série existe déjà
                        conn.execute_command("TS.INFO", key)
                        print(f"La série temporelle existe déjà : {key} dans le shard {location}")
                    except redis.exceptions.ResponseError as e:
                        # Si l'erreur n'est pas due à l'absence de la clé, propager l'erreur
                        if not str(e).startswith("TSDB: key does not exist"):
                            print(f"Erreur lors de la vérification de la série {key}: {e}")
                            continue

                        try:
                            # Créer la série temporelle avec une rétention de 30 jours
                            retention = 30 * 24 * 60 * 60 * 1000  # 30 jours en millisecondes
                            conn.execute_command(
                                "TS.CREATE", key,
                                "RETENTION", retention,
                                "LABELS",
                                "sensorId", str(sensor_id),
                                "type", sensor_type,
                                "location", location,
                                "unit_measure", unit_measure
                            )
                            print(f"Série temporelle créée : {key} (unité: {unit_measure}) dans le shard {location}")
                        except Exception as create_error:
                            print(f"Erreur lors de la création de la série {key}: {create_error}")

    def generate_sensor_value(self, sensor_type):
        """Génération de valeurs réalistes selon le type de capteur"""
        if sensor_type == "temperature":
            return round(random.uniform(15.0, 30.0), 1)
        elif sensor_type == "humidity":
            return round(random.uniform(30.0, 70.0), 1)
        elif sensor_type == "air_quality":
            return round(random.uniform(20.0, 150.0), 1)

    def generate_historical_data(self, days_back=7):
        """Génère des données historiques pour chaque capteur dans son shard dédié"""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        current_time = start_time

        # Intervalle de 5 minutes
        interval = timedelta(minutes=5)
        total_points = 0

        # Fichier de log pour le suivi
        with open("sharding_metadata/historical_data_log.txt", "w") as log_file:
            while current_time <= end_time:
                timestamp_ms = int(current_time.timestamp() * 1000)

                for location in list(self.connections.keys()):
                    conn = self.get_connection_for_location(location)
                    for sensor_type in self.sensor_types:
                        for sensor_id in range(1, self.num_sensors + 1):
                            key = f"sensor:{sensor_type}:{location}:{sensor_id}"
                            value = self.generate_sensor_value(sensor_type)
                            try:
                                conn.execute_command("TS.ADD", key, timestamp_ms, value)
                                total_points += 1
                            except Exception as e:
                                log_message = f"Erreur d'ajout pour {key} à {current_time}: {e}"
                                print(log_message)
                                log_file.write(log_message + "\n")

                current_time += interval
                # Afficher et logger la progression
                if random.random() < 0.01:  # Afficher environ 1% des points
                    log_message = f"Données générées pour: {current_time}, total: {total_points} points"
                    print(log_message)
                    log_file.write(log_message + "\n")
                    log_file.flush()

        print(f"Génération historique terminée - {total_points} points de données générés")

    def generate_live_data(self, interval_seconds=30):
        """Génère des données en continu pour chaque capteur dans son shard dédié"""
        try:
            while True:
                timestamp_ms = int(time.time() * 1000)  # Timestamp actuel en ms
                points_added = 0

                for location in list(self.connections.keys()):
                    conn = self.get_connection_for_location(location)
                    for sensor_type in self.sensor_types:
                        for sensor_id in range(1, self.num_sensors + 1):
                            key = f"sensor:{sensor_type}:{location}:{sensor_id}"
                            value = self.generate_sensor_value(sensor_type)
                            try:
                                conn.execute_command("TS.ADD", key, timestamp_ms, value)
                                points_added += 1
                            except Exception as e:
                                print(f"Erreur d'ajout pour {key}: {e}")

                print(
                    f"Données générées à {datetime.now()} - {points_added} points ajoutés sur {len(self.connections)} shards")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nArrêt de la génération de données en direct.")

    def query_location_data(self, location, sensor_type, start_time, end_time):
        """Interroge les données d'un type de capteur pour un emplacement spécifique"""
        if location not in self.connections:
            return f"Emplacement {location} non trouvé ou connexion non disponible"

        conn = self.get_connection_for_location(location)
        results = {}

        # Convertir les dates en timestamp milliseconds
        start_ts = int(start_time.timestamp() * 1000)
        end_ts = int(end_time.timestamp() * 1000)

        for sensor_id in range(1, self.num_sensors + 1):
            key = f"sensor:{sensor_type}:{location}:{sensor_id}"
            try:
                # Récupérer les données de la plage temporelle
                data = conn.execute_command("TS.RANGE", key, start_ts, end_ts)
                results[f"sensor_{sensor_id}"] = data
            except Exception as e:
                results[f"sensor_{sensor_id}"] = f"Erreur: {e}"

        return results

    def query_by_unit_measure(self, unit_measure, start_time, end_time):
        """
        Interroge toutes les séries temporelles ayant une unité de mesure spécifique
        à travers tous les shards
        """
        results = {}

        # Convertir les dates en timestamp milliseconds
        start_ts = int(start_time.timestamp() * 1000)
        end_ts = int(end_time.timestamp() * 1000)

        # Trouver les types de capteurs avec cette unité
        sensor_types_with_unit = [
            st for st, um in self.unit_measures.items() if um == unit_measure
        ]

        if not sensor_types_with_unit:
            return f"Aucun capteur avec l'unité de mesure '{unit_measure}' trouvé"

        # Pour chaque emplacement
        for location in list(self.connections.keys()):
            location_results = {}
            conn = self.get_connection_for_location(location)

            # Pour chaque type de capteur ayant l'unité demandée
            for sensor_type in sensor_types_with_unit:
                sensor_results = {}

                for sensor_id in range(1, self.num_sensors + 1):
                    key = f"sensor:{sensor_type}:{location}:{sensor_id}"
                    try:
                        data = conn.execute_command("TS.RANGE", key, start_ts, end_ts)
                        sensor_results[f"sensor_{sensor_id}"] = data
                    except Exception as e:
                        sensor_results[f"sensor_{sensor_id}"] = f"Erreur: {e}"

                location_results[sensor_type] = sensor_results

            results[location] = location_results

        return results

    def get_shards_status(self):
        """Vérifie le statut de tous les shards"""
        status = {}
        for location, config in self.shards.items():
            try:
                # Vérifier si nous avons une connexion active pour ce shard
                if location not in self.connections:
                    status[location] = {
                        "status": "offline",
                        "error": "Pas de connexion disponible",
                        "container": config["container"]
                    }
                    continue

                conn = self.connections[location]
                # Vérifier si le serveur répond
                ping_result = conn.ping()
                # Obtenir des informations sur la mémoire et la réplication
                info_memory = conn.info("memory")
                info_replication = conn.info("replication")
                # Compter les séries temporelles pour ce shard
                keys = conn.keys("sensor:*")

                status[location] = {
                    "status": "online" if ping_result else "offline",
                    "role": info_replication.get("role", "unknown"),
                    "used_memory": info_memory.get("used_memory_human", "N/A"),
                    "keys": len(keys),
                    "container": config["container"]
                }
            except Exception as e:
                status[location] = {
                    "status": "offline",
                    "error": str(e),
                    "container": config["container"]
                }

        return status

    def get_shard_distribution_metrics(self):
        """Calcule des métriques sur la distribution des données entre les shards"""
        metrics = {
            "total_sensors": 0,
            "sensors_per_shard": {},
            "data_points_per_shard": {},
            "total_data_points": 0
        }

        for location in list(self.connections.keys()):
            conn = self.get_connection_for_location(location)
            sensor_count = 0
            data_points = 0

            for sensor_type in self.sensor_types:
                for sensor_id in range(1, self.num_sensors + 1):
                    key = f"sensor:{sensor_type}:{location}:{sensor_id}"
                    try:
                        # Vérifier si la série existe
                        info = conn.execute_command("TS.INFO", key)
                        sensor_count += 1

                        # Obtenir le nombre de points dans cette série
                        # Recherche de "totalSamples" ou b"totalSamples" dans la réponse
                        total_samples = None
                        for i, item in enumerate(info):
                            if isinstance(item, (str, bytes)):
                                item_str = item.decode() if isinstance(item, bytes) else item
                                if item_str == "totalSamples" and i + 1 < len(info):
                                    total_samples = int(info[i + 1])
                                    break

                        if total_samples is not None:
                            data_points += total_samples
                    except Exception as e:
                        print(f"Erreur lors de la récupération des métriques pour {key}: {e}")

            metrics["sensors_per_shard"][location] = sensor_count
            metrics["data_points_per_shard"][location] = data_points
            metrics["total_sensors"] += sensor_count
            metrics["total_data_points"] += data_points

        return metrics


# Fonctions d'utilitaire pour l'administration
def print_shard_status(sharding_system):
    """Affiche un rapport de statut des shards"""
    status = sharding_system.get_shards_status()
    print("\n===== STATUT DES SHARDS =====")
    for location, info in status.items():
        if info["status"] == "online":
            role_info = f", rôle: {info.get('role', 'unknown')}"
            print(
                f"✅ {location} ({info['container']}): ONLINE{role_info} - {info['keys']} clés, {info['used_memory']} mémoire utilisée")
        else:
            print(f"❌ {location} ({info['container']}): OFFLINE - {info.get('error', 'Erreur inconnue')}")
    print("============================\n")


def print_distribution_metrics(sharding_system):
    """Affiche des métriques sur la distribution des données"""
    metrics = sharding_system.get_shard_distribution_metrics()
    print("\n===== MÉTRIQUES DE DISTRIBUTION =====")
    print(f"Total des capteurs: {metrics['total_sensors']}")
    print(f"Total des points de données: {metrics['total_data_points']}")
    print("\nDistribution des capteurs par shard:")
    for location, count in metrics['sensors_per_shard'].items():
        print(f"  - {location}: {count} capteurs")
    print("\nDistribution des points de données par shard:")
    for location, count in metrics['data_points_per_shard'].items():
        percentage = 0
        if metrics['total_data_points'] > 0:
            percentage = (count / metrics['total_data_points']) * 100
        print(f"  - {location}: {count} points ({percentage:.1f}%)")
    print("====================================\n")


# Exécution du script
if __name__ == "__main__":
    try:
        print("Initialisation du système de true sharding (un shard par emplacement)...")
        sharding_system = RedisTrueShardingSystem()

        # Vérifier si nous avons au moins une connexion valide
        if not sharding_system.connections:
            print("ERREUR: Aucune connexion valide aux shards Redis. Vérifiez que vos serveurs Redis sont en ligne.")
            exit(1)

        print("\nCréation des séries temporelles dans chaque shard...")
        sharding_system.create_time_series()

        # Afficher le statut initial des shards
        print_shard_status(sharding_system)

        print("\nGénération de données historiques (7 derniers jours)...")
        sharding_system.generate_historical_data(days_back=7)

        # Afficher les métriques de distribution après la génération historique
        print_distribution_metrics(sharding_system)

        # Exemple de requête par unité de mesure
        print("\nExemple de requête par unité de mesure (celsius):")
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        celsius_data = sharding_system.query_by_unit_measure("celsius", one_hour_ago, now)

        # Trouver le premier emplacement disponible pour l'exemple
        available_locations = list(sharding_system.connections.keys())
        if available_locations:
            sample_location = available_locations[0]
            print(
                f"Échantillon de données pour {sample_location}: {celsius_data[sample_location]['temperature'] if sample_location in celsius_data else 'Aucune donnée'}")
        else:
            print("Aucun emplacement disponible pour l'exemple.")

        # Démarrer la génération en temps réel
        print("\nDémarrage de la génération de données en temps réel...")
        sharding_system.generate_live_data()

    except KeyboardInterrupt:
        print("\nArrêt du système de sharding.")
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback

        traceback.print_exc()