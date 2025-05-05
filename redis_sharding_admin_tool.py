import argparse
import json
import os
from datetime import datetime, timedelta
from tabulate import tabulate
import matplotlib.pyplot as plt
import numpy as np

# Import notre module de sharding
from generate_sharding_data import RedisTrueShardingSystem


class RedisShardingAdmin:
    def __init__(self):
        print("Initialisation du système d'administration du sharding Redis...")
        self.sharding_system = RedisTrueShardingSystem()
        self.output_dir = "sharding_admin_reports"
        os.makedirs(self.output_dir, exist_ok=True)

    def status(self):
        """Affiche et sauvegarde le statut des shards"""
        status = self.sharding_system.get_shards_status()

        # Préparer les données pour tabulate
        headers = ["Shard", "Statut", "Container", "Clés", "Mémoire"]
        rows = []

        for location, info in status.items():
            rows.append([
                location,
                info["status"],
                info["container"],
                info.get("keys", "N/A"),
                info.get("used_memory", "N/A")
            ])

        # Afficher le tableau
        print("\nStatut des Shards Redis:")
        print(tabulate(rows, headers=headers, tablefmt="grid"))

        # Sauvegarder le rapport
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"{self.output_dir}/status_report_{timestamp}.json", "w") as f:
            json.dump(status, f, indent=2)

        print(f"Rapport sauvegardé: status_report_{timestamp}.json")

    def distribution(self):
        """Affiche et visualise la distribution des données"""
        metrics = self.sharding_system.get_shard_distribution_metrics()

        # Afficher les statistiques
        print("\nDistribution des données:")
        print(f"Total des capteurs: {metrics['total_sensors']}")
        print(f"Total des points de données: {metrics['total_data_points']}")

        # Préparer les données pour tabulate
        headers = ["Shard", "Capteurs", "Points de données", "Pourcentage"]
        rows = []

        for location, count in metrics['sensors_per_shard'].items():
            data_points = metrics['data_points_per_shard'].get(location, 0)
            percentage = 0
            if metrics['total_data_points'] > 0:
                percentage = (data_points / metrics['total_data_points']) * 100
            rows.append([
                location,
                count,
                data_points,
                f"{percentage:.1f}%"
            ])

        # Afficher le tableau
        print("\nDistribution par shard:")
        print(tabulate(rows, headers=headers, tablefmt="grid"))

        # Créer une visualisation
        self._create_distribution_chart(metrics)

        # Sauvegarder le rapport
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"{self.output_dir}/distribution_report_{timestamp}.json", "w") as f:
            json.dump(metrics, f, indent=2)

        print(f"Rapport sauvegardé: distribution_report_{timestamp}.json")

    def _create_distribution_chart(self, metrics):
        """Crée un graphique de distribution des données"""
        try:
            locations = list(metrics['data_points_per_shard'].keys())
            data_points = list(metrics['data_points_per_shard'].values())

            plt.figure(figsize=(12, 6))

            # Graphique en barres
            plt.subplot(1, 2, 1)
            bars = plt.bar(locations, data_points, color='skyblue')
            plt.title('Points de données par shard')
            plt.xlabel('Shard')
            plt.ylabel('Nombre de points')

            # Ajouter les valeurs sur les barres
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width() / 2., height,
                         f'{int(height)}',
                         ha='center', va='bottom')

            # Graphique en camembert
            plt.subplot(1, 2, 2)
            plt.pie(data_points, labels=locations, autopct='%1.1f%%', startangle=90)
            plt.axis('equal')
            plt.title('Distribution des données (%)')

            # Sauvegarder le graphique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/distribution_chart_{timestamp}.png")
            print(f"Graphique sauvegardé: distribution_chart_{timestamp}.png")

        except Exception as e:
            print(f"Erreur lors de la création du graphique: {e}")

    def query(self, unit_measure=None, location=None, sensor_type=None, hours=1):
        """Interroge les données selon différents critères"""
        now = datetime.now()
        start_time = now - timedelta(hours=hours)

        print(f"\nRequête de données du {start_time} au {now} ({hours} heure(s)):")

        if unit_measure:
            print(f"Filtrage par unité de mesure: {unit_measure}")
            results = self.sharding_system.query_by_unit_measure(unit_measure, start_time, now)
            self._display_query_summary(results, unit_measure=unit_measure)

        elif location and sensor_type:
            print(f"Filtrage par emplacement: {location} et type de capteur: {sensor_type}")
            results = self.sharding_system.query_location_data(location, sensor_type, start_time, now)
            self._display_query_summary({location: {sensor_type: results}})

        else:
            print("Veuillez spécifier soit une unité de mesure, soit un emplacement et un type de capteur.")

    def _display_query_summary(self, results, unit_measure=None):
        """Affiche un résumé des résultats de requête"""
        if isinstance(results, str):
            print(f"Résultat: {results}")
            return

        total_points = 0
        summary = []

        for location, location_data in results.items():
            for sensor_type, sensors in location_data.items():
                for sensor_id, data in sensors.items():
                    if isinstance(data, list):
                        num_points = len(data)
                        total_points += num_points
                        if data:
                            first_value = data[0][1] if len(data[0]) > 1 else 'N/A'
                            last_value = data[-1][1] if len(data[-1]) > 1 else 'N/A'
                        else:
                            first_value = 'N/A'
                            last_value = 'N/A'

                        summary.append([
                            location,
                            sensor_type,
                            sensor_id,
                            num_points,
                            first_value,
                            last_value
                        ])

        # Afficher le résumé
        if summary:
            headers = ["Emplacement", "Type", "Capteur", "Points", "Première valeur", "Dernière valeur"]
            print("\nRésumé des données:")
            print(tabulate(summary, headers=headers, tablefmt="grid"))
            print(f"\nTotal des points de données: {total_points}")
        else:
            print("Aucune donnée trouvée pour la période spécifiée.")

    def reset(self, confirm=False):
        """Réinitialise toutes les données des shards (DANGER!)"""
        if not confirm:
            print("\n⚠️  ATTENTION: Cette opération va supprimer toutes les données des shards!")
            confirmation = input("Tapez 'OUI' pour confirmer: ")
            if confirmation != "OUI":
                print("Opération annulée.")
                return

        print("\nRéinitialisation des shards en cours...")

        for location in self.sharding_system.locations:
            conn = self.sharding_system.get_connection_for_location(location)
            try:
                # Supprimer toutes les clés
                keys = conn.keys("sensor:*")
                if keys:
                    deleted = conn.delete(*keys)
                    print(f"Shard {location}: {deleted} clé(s) supprimée(s)")
                else:
                    print(f"Shard {location}: aucune clé à supprimer")
            except Exception as e:
                print(f"Erreur lors de la réinitialisation du shard {location}: {e}")

        print("\nRéinitialisation terminée.")


def parse_arguments():
    parser = argparse.ArgumentParser(description='Outil d\'administration pour Redis Sharding')

    subparsers = parser.add_subparsers(dest='command', help='Commande à exécuter')

    # Commande status
    status_parser = subparsers.add_parser('status', help='Afficher le statut des shards')

    # Commande distribution
    dist_parser = subparsers.add_parser('distribution', help='Afficher la distribution des données')

    # Commande query
    query_parser = subparsers.add_parser('query', help='Interroger les données')
    query_parser.add_argument('--unit', type=str, help='Filtrer par unité de mesure (celsius, percent, aqi)')
    query_parser.add_argument('--location', type=str, help='Filtrer par emplacement')
    query_parser.add_argument('--type', type=str, help='Filtrer par type de capteur')
    query_parser.add_argument('--hours', type=int, default=1, help='Nombre d\'heures à considérer (par défaut: 1)')

    # Commande reset
    reset_parser = subparsers.add_parser('reset', help='Réinitialiser toutes les données (DANGER!)')
    reset_parser.add_argument('--force', action='store_true', help='Forcer la réinitialisation sans confirmation')

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    admin = RedisShardingAdmin()

    if args.command == 'status':
        admin.status()
    elif args.command == 'distribution':
        admin.distribution()
    elif args.command == 'query':
        admin.query(args.unit, args.location, args.type, args.hours)
    elif args.command == 'reset':
        admin.reset(args.force)
    else:
        print("Commande non reconnue. Utilisez --help pour voir les options disponibles.")