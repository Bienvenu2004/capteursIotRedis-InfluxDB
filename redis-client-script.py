import redis
import time
import sys
import argparse
from datetime import datetime


def connect_to_sentinel(sentinel_host, sentinel_port, master_name, password=None):
    """Connexion à Redis via Sentinel pour obtenir l'adresse du maître actuel"""
    sentinel = redis.Sentinel([(sentinel_host, sentinel_port)], socket_timeout=0.5, password=password)

    try:
        # Obtenir le maître actuel
        master_host, master_port = sentinel.discover_master(master_name)
        print(f"Master découvert: {master_host}:{master_port}")

        # Se connecter au maître
        master = sentinel.master_for(
            master_name,
            socket_timeout=0.5,
            password=password
        )

        # Vérifier la connexion
        master.ping()
        return master, sentinel
    except Exception as e:
        print(f"Erreur lors de la connexion au sentinel ou au maître: {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(description='Client Redis avec support Sentinel')
    parser.add_argument('--location', required=True,
                        help='Emplacement à tester (salon, chambre1, chambre2, cuisine, salle-de-bain)')
    args = parser.parse_args()

    # Mapper les emplacements aux noms des maîtres dans Sentinel
    location_map = {
        'salon': 'salon-master',
        'chambre1': 'chambre1-master',
        'chambre2': 'chambre2-master',
        'cuisine': 'cuisine-master',
        'salle-de-bain': 'sdb-master'
    }

    if args.location not in location_map:
        print(f"Emplacement '{args.location}' non reconnu. Utilisez un des: {', '.join(location_map.keys())}")
        sys.exit(1)

    master_name = location_map[args.location]

    # Connexion via le sentinel (premier sentinel pour chaque emplacement)
    sentinel_host = "localhost"
    sentinel_port = 26379  # Port par défaut du premier sentinel
    password = "strongpassword"

    master, sentinel = connect_to_sentinel(sentinel_host, sentinel_port, master_name, password)
    if not master:
        sys.exit(1)

    # Simuler l'envoi de données de capteurs IoT
    sensors = ["temperature", "humidity", "motion", "light", "airquality"]

    try:
        counter = 0
        while True:
            timestamp = int(time.time())
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for sensor in sensors:
                key = f"{args.location}:{sensor}:{timestamp}"
                # Simulation de valeurs pour les capteurs
                if sensor == "temperature":
                    value = 20 + (counter % 5)
                elif sensor == "humidity":
                    value = 40 + (counter % 20)
                elif sensor == "motion":
                    value = counter % 2  # 0 ou 1
                elif sensor == "light":
                    value = 200 + (counter % 300)
                else:  # airquality
                    value = 50 + (counter % 30)

                try:
                    # Écrire sur le maître
                    master.set(key, value)
                    print(f"[{timestamp_str}] Écrit sur le maître: {key} = {value}")

                    # Lire du maître pour confirmer
                    read_value = master.get(key)
                    print(
                        f"[{timestamp_str}] Lu du maître: {key} = {read_value.decode('utf-8') if read_value else 'None'}")

                    # Si vous avez un accès direct aux réplicas, vous pourriez également vérifier la réplication
                    # ici en lisant directement depuis le réplica
                except redis.RedisError as e:
                    print(f"Erreur Redis: {e}")
                    # Essayer de reconnecter via Sentinel qui détectera le nouveau maître
                    print("Tentative de reconnexion via Sentinel...")
                    master, sentinel = connect_to_sentinel(sentinel_host, sentinel_port, master_name, password)
                    if not master:
                        print("Échec de reconnexion, attente avant nouvel essai...")
                        time.sleep(5)

            counter += 1
            time.sleep(2)  # Attendre 2 secondes entre chaque envoi

    except KeyboardInterrupt:
        print("Programme arrêté par l'utilisateur")


if __name__ == "__main__":
    main()