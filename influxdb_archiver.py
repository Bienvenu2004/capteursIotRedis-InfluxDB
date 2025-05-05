import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timedelta
import time
import subprocess
import json
import os

import generate_sharding_data


class InfluxDBArchiver:
    def __init__(self, token=None, url="http://localhost:8086", org="tp_iot", bucket="sensors_archive"):
        # Configuration
        self.url = url
        self.org = org
        self.bucket = bucket

        # Obtenir le token
        if token:
            self.token = token
        else:
            self.token = self.get_influxdb_token()

        print(f"\nConnexion à InfluxDB avec les paramètres:")
        print(f"URL: {self.url}")
        print(f"Token: {self.token[:5]}...{self.token[-3:] if len(self.token) > 8 else ''}")
        print(f"Org: {self.org}")
        print(f"Bucket: {self.bucket}")

        try:
            self.client = influxdb_client.InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org,
                timeout=30_000
            )

            # Test de connexion par vérification de la santé
            health = self.client.health()
            if health and health.status == "pass":
                print(f"✅ InfluxDB est en bonne santé: {health.status}")
            else:
                print(f"⚠️ InfluxDB santé: {health.status if health else 'inconnu'}")

            # Test de connexion par vérification des buckets
            try:
                buckets_api = self.client.buckets_api()
                buckets = buckets_api.find_buckets().buckets
                if buckets:
                    print(f"✅ Buckets disponibles: {[b.name for b in buckets]}")
                else:
                    print("⚠️ Aucun bucket trouvé")
            except Exception as bucket_error:
                print(f"❌ Erreur lors de la récupération des buckets: {bucket_error}")

            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()

            print("✅ Client InfluxDB initialisé avec succès")

        except Exception as e:
            print(f"❌ Erreur d'initialisation du client InfluxDB: {e}")
            raise

    def get_influxdb_token(self):
        """Tente de récupérer automatiquement un token valide pour InfluxDB"""
        print("Tentative de récupération automatique du token InfluxDB...")

        # Option 1: Utiliser le token prédéfini
        default_token = "my-super-secret-tok"

        # Option 2: Essayer de récupérer le token via Docker
        try:
            cmd = ["docker", "exec", "influxdb", "influx", "auth", "list", "--user", "admin", "-o", "tp_iot", "--json"]
            process = subprocess.run(cmd, capture_output=True, text=True)

            if process.returncode == 0 and process.stdout:
                try:
                    auth_data = json.loads(process.stdout)
                    if isinstance(auth_data, list) and len(auth_data) > 0:
                        # Utiliser le premier token trouvé pour l'utilisateur admin
                        token = auth_data[0].get("token", "")
                        if token:
                            print("✅ Token récupéré avec succès via Docker!")
                            return token
                except json.JSONDecodeError:
                    print("⚠️ Format de réponse non valide lors de la récupération du token")

            print("⚠️ Impossible de récupérer le token via Docker")
        except Exception as e:
            print(f"⚠️ Erreur lors de l'exécution de la commande Docker: {e}")

        # Option 3: Demander à l'utilisateur
        user_token = input(f"Entrez le token InfluxDB manuellement (laissez vide pour utiliser '{default_token}'): ")
        if user_token:
            return user_token

        print(f"Utilisation du token par défaut: {default_token[:5]}...")
        return default_token

    def ensure_bucket_exists(self):
        """S'assure que le bucket existe, le crée si nécessaire"""
        try:
            bucket_api = self.client.buckets_api()
            bucket = bucket_api.find_bucket_by_name(self.bucket)
            if bucket:
                print(f"✅ Le bucket '{self.bucket}' existe")
                return True

            print(f"⚠️ Le bucket '{self.bucket}' n'existe pas. Tentative de création...")
            orgs = self.client.organizations_api().find_organizations()
            if not orgs:
                print("❌ Aucune organisation trouvée")
                return False

            org_id = orgs[0].id
            bucket_api.create_bucket(bucket_name=self.bucket, org_id=org_id)
            print(f"✅ Bucket '{self.bucket}' créé avec succès")
            return True
        except Exception as e:
            print(f"❌ Erreur lors de la vérification/création du bucket: {e}")
            return False

    def archive_redis_data(self, redis_system, days_back=7):
        """Archive les données Redis vers InfluxDB"""
        try:
            if not self.ensure_bucket_exists():
                print("❌ Impossible de continuer l'archivage sans bucket valide")
                return False

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)
            print(f"\nArchivage des données du {start_time} au {end_time}...")

            points = []
            for location in redis_system.locations:
                if location not in redis_system.connections:
                    continue

                conn = redis_system.get_connection_for_location(location)
                for sensor_type in redis_system.sensor_types:
                    for sensor_id in range(1, redis_system.num_sensors + 1):
                        key = f"sensor:{sensor_type}:{location}:{sensor_id}"
                        try:
                            data = conn.execute_command("TS.RANGE", key,
                                                        int(start_time.timestamp() * 1000),
                                                        int(end_time.timestamp() * 1000))
                            for timestamp_ms, value in data:
                                point = influxdb_client.Point(sensor_type) \
                                    .tag("location", location) \
                                    .tag("sensor_id", str(sensor_id)) \
                                    .field("value", float(value)) \
                                    .time(int(timestamp_ms) * 1_000_000)  # Conversion ms -> ns
                                points.append(point)

                        except Exception as e:
                            print(f"⚠️ Erreur sur {key}: {str(e)[:100]}...")

            if points:
                print(f"Tentative d'écriture de {len(points)} points...")
                try:
                    self.write_api.write(bucket=self.bucket, org=self.org, record=points)
                    print("✅ Données écrites avec succès")

                    # Vérification
                    query = f'from(bucket:"{self.bucket}") |> range(start:-1h) |> limit(n:1)'
                    result = self.query_api.query(query)
                    print(f"Vérification : {len(result)} tables trouvées")

                    return True
                except Exception as write_error:
                    print(f"❌ Erreur d'écriture: {write_error}")
                    return False
            else:
                print("⚠️ Aucune donnée à archiver")
                return True

        except Exception as e:
            print(f"❌ Erreur lors de l'archivage: {e}")
            return False


def main():
    try:
        # Initialisation du système Redis
        print("Initialisation du système Redis de True Sharding...")
        redis_system = generate_sharding_data.RedisTrueShardingSystem()

        # Initialisation de l'archiveur InfluxDB avec récupération automatique du token
        influx_archiver = InfluxDBArchiver()

        # Test initial d'archivage
        print("\nTest initial d'archivage (1 jour de données)...")
        success = influx_archiver.archive_redis_data(redis_system, days_back=1)

        if not success:
            print("\n❌ Le test initial d'archivage a échoué. Vérifiez les paramètres et recommencez.")
            return

        print("\n✅ Test initial réussi! Démarrage de la boucle principale...")
        print("Appuyez sur Ctrl+C pour arrêter le programme")

        # Boucle principale
        try:
            while True:
                # Générer des données en direct
                redis_system.generate_live_data(interval_seconds=30)

                # Archivage périodique toutes les 5 minutes
                current_time = datetime.now()
                if current_time.minute % 5 == 0 and current_time.second < 30:
                    print(f"\n⏰ {current_time} - Archivage périodique...")
                    influx_archiver.archive_redis_data(redis_system, days_back=0.1)  # ~2.4 heures
                    time.sleep(60)  # Éviter les doubles exécutions

        except KeyboardInterrupt:
            print("\n\n🛑 Interruption détectée. Arrêt propre du système...")

    except KeyboardInterrupt:
        print("\n🛑 Arrêt du système")
    except Exception as e:
        print(f"\n❌ Erreur critique: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()