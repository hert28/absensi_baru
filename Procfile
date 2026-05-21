web: python run_migration.py && gunicorn -b 0.0.0.0:$PORT -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app
