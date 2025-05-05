# Écrire un point de test
docker exec influxdb influx write `
    --bucket sensors_archive `
    --precision ns `
    "test_measurement location=test value=42"

# Vérifier la lecture
docker exec influxdb influx query 'from(bucket:"sensors_archive") |> range(start:-1h)'