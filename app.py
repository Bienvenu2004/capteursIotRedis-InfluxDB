from flask import Flask, render_template, request, jsonify
import redis
import time
from datetime import datetime, timedelta
import plotly.graph_objs as go
from plotly.utils import PlotlyJSONEncoder
import json

app = Flask(__name__)

# Configuration Redis
redis_host = "localhost"
redis_port = 6379
r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

# Liste des emplacements et types de capteurs (doit correspondre à votre configuration)
LOCATIONS = ["salon", "chambre1", "chambre2", "cuisine", "salle_de_bain"]
SENSOR_TYPES = ["temperature", "humidity", "air_quality"]


@app.route('/')
def dashboard():
    return render_template('dashboard.html',
                           locations=LOCATIONS,
                           sensor_types=SENSOR_TYPES)


@app.route('/get_sensor_data', methods=['POST'])
def get_sensor_data():
    data = request.json
    location = data.get('location')
    sensor_type = data.get('sensor_type')
    sensor_id = data.get('sensor_id', 1)
    time_range = data.get('time_range', '1h')  # 1h, 24h, 7d, 30d

    # Calculer les timestamps de début et fin
    now = int(time.time() * 1000)

    if time_range == '1h':
        start_time = now - 3600 * 1000
    elif time_range == '24h':
        start_time = now - 24 * 3600 * 1000
    elif time_range == '7d':
        start_time = now - 7 * 24 * 3600 * 1000
    elif time_range == '30d':
        start_time = now - 30 * 24 * 3600 * 1000
    else:
        start_time = now - 3600 * 1000  # Par défaut 1h

    key = f"sensor:{sensor_type}:{location}:{sensor_id}"

    try:
        # Récupérer les données de la série temporelle
        raw_data = r.execute_command('TS.RANGE', key, start_time, now)

        # Traiter les données pour Plotly
        timestamps = [datetime.fromtimestamp(int(point[0]) / 1000) for point in raw_data]
        values = [float(point[1]) for point in raw_data]

        # Créer le graphique
        trace = go.Scatter(
            x=timestamps,
            y=values,
            mode='lines+markers',
            name=f"{sensor_type} - {location} - {sensor_id}"
        )

        layout = go.Layout(
            title=f"{sensor_type.capitalize()} dans {location} (Capteur {sensor_id})",
            xaxis=dict(title='Temps'),
            yaxis=dict(title=sensor_type.capitalize())
        )

        fig = go.Figure(data=[trace], layout=layout)
        graph_json = json.dumps(fig, cls=PlotlyJSONEncoder)

        # Statistiques de base
        if values:
            stats = {
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'count': len(values)
            }
        else:
            stats = {}

        return jsonify({
            'status': 'success',
            'graph': graph_json,
            'stats': stats
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })


@app.route('/get_sensor_count', methods=['POST'])
def get_sensor_count():
    data = request.json
    location = data.get('location')
    sensor_type = data.get('sensor_type', None)

    try:
        counts = []

        def parse_ts_info(info):
            """Convertit la réponse TS.INFO (liste) en dictionnaire"""
            if isinstance(info, dict):
                return info
            return {info[i]: info[i + 1] for i in range(0, len(info), 2)}

        if sensor_type:
            # Recherche pour un type spécifique
            for sensor_id in range(1, 4):
                key = f"sensor:{sensor_type}:{location}:{sensor_id}"
                try:
                    raw_info = r.execute_command('TS.INFO', key)
                    info = parse_ts_info(raw_info)
                    counts.append({
                        'sensor_id': sensor_id,
                        'count': info.get('totalSamples', 0)
                    })
                except redis.exceptions.ResponseError:
                    counts.append({
                        'sensor_id': sensor_id,
                        'count': 0,
                        'error': 'sensor_not_found'
                    })
                    continue
        else:
            # Recherche pour tous les types
            for st in SENSOR_TYPES:
                for sensor_id in range(1, 4):
                    key = f"sensor:{st}:{location}:{sensor_id}"
                    try:
                        raw_info = r.execute_command('TS.INFO', key)
                        info = parse_ts_info(raw_info)
                        counts.append({
                            'sensor_type': st,
                            'sensor_id': sensor_id,
                            'count': info.get('totalSamples', 0)
                        })
                    except redis.exceptions.ResponseError:
                        counts.append({
                            'sensor_type': st,
                            'sensor_id': sensor_id,
                            'count': 0,
                            'error': 'sensor_not_found'
                        })
                        continue

        return jsonify({
            'status': 'success',
            'counts': counts,
            '_metadata': {
                'location': location,
                'sensor_type_filter': sensor_type or 'all'
            }
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            '_debug': {
                'error_type': type(e).__name__,
                'timestamp': datetime.now().isoformat()
            }
        })


@app.route('/search_data', methods=['POST'])
def search_data():
    data = request.json
    query = data.get('query', '').lower().strip()

    try:
        results = []
        matching_keys = []

        for key in r.scan_iter("sensor:*"):
            if query in key.lower():
                matching_keys.append(key)
                try:
                    # Version adaptée pour les réponses en liste
                    info = r.execute_command('TS.INFO', key)

                    # Transformation de la liste en dictionnaire
                    info_dict = {
                        'totalSamples': info[1],
                        'firstTimestamp': info[3],
                        'lastTimestamp': info[5]
                    }

                    parts = key.split(':')
                    results.append({
                        'key': key,
                        'sensor_type': parts[1],
                        'location': parts[2],
                        'sensor_id': parts[3],
                        'samples': info_dict['totalSamples'],
                        'first_timestamp': datetime.fromtimestamp(int(info_dict['firstTimestamp']) / 1000).strftime(
                            '%Y-%m-%d %H:%M:%S'),
                        'last_timestamp': datetime.fromtimestamp(int(info_dict['lastTimestamp']) / 1000).strftime(
                            '%Y-%m-%d %H:%M:%S')
                    })
                except IndexError as e:
                    print(f"Structure incorrecte pour {key}: {info}")
                    continue
                except Exception as e:
                    print(f"Erreur traitement {key}: {str(e)}")
                    continue

        return jsonify({
            'status': 'success',
            'results': results,
            '_debug': {
                'query': query,
                'keys_found': len(matching_keys),
                'keys_processed': len(results)
            }
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True)