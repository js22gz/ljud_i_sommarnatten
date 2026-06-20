# Ljud i sommarnatten

Fågelanalys av trädgårdsinspelningar med **BirdNET** (Cornell Lab).

## Installation

```bash
python3 -m venv .venv --without-pip
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
.venv/bin/pip install -r requirements.txt
```

## Lägg till en inspelning

```bash
cp -r sessions/_template sessions/min_session
# lägg in ljudfil + redigera session.json
.venv/bin/python run.py min_session --serve
```

Öppna http://127.0.0.1:8765/

## Kommandon

```bash
.venv/bin/python run.py --list
.venv/bin/python run.py midsommardagen_08_20
.venv/bin/python run.py midsommardagen_08_20 --serve
```

Allt för en inspelning finns i `sessions/<id>/` — ljud, config, results och visualizer.