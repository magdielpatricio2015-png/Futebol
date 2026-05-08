from flask import Flask, render_template_string, request
import unicodedata

app = Flask(__name__)

FORCA_BASE = {
    "Flamengo": 120,
    "Palmeiras": 115,
    "Botafogo": 105,
    "Atlético Mineiro": 100,
    "São Paulo": 95,
    "Fluminense": 90,
    "Grêmio": 88,
    "Internacional": 86,
    "Corinthians": 84,
    "Cruzeiro": 82,
    "Vasco": 78,
    "Bahia": 76,
    "Santos": 74,
    "Athletico Paranaense": 72,
    "Fortaleza": 70,
    "Ceará": 68,
    "Sport": 65,
    "Vitória": 62,
    "Juventude": 60,
    "Mirassol": 58,
}

POSICOES = {
    "Flamengo": {"posicao": 1},
    "Palmeiras": {"posicao": 2},
    "Botafogo": {"posicao": 3},
    "Atlético Mineiro": {"posicao": 4},
    "São Paulo": {"posicao": 5},
    "Fluminense": {"posicao": 6},
    "Grêmio": {"posicao": 7},
    "Internacional": {"posicao": 8},
    "Corinthians": {"posicao": 9},
    "Cruzeiro": {"posicao": 10},
    "Vasco": {"posicao": 11},
    "Bahia": {"posicao": 12},
    "Santos": {"posicao": 13},
    "Athletico Paranaense": {"posicao": 14},
    "Fortaleza": {"posicao": 15},
    "Ceará": {"posicao": 16},
    "Sport": {"posicao": 17},
    "Vitória": {"posicao": 18},
    "Juventude": {"posicao": 19},
    "Mirassol": {"posicao": 20},
}


def nome_limpo(texto):
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


def normalizar(texto):
    return nome_limpo(texto).lower()


def forca_inicial(time, posicoes=None):
    """
    Retorna rating inicial Elo baseado em:
    1. posição oficial da liga;
    2. força base cadastrada;
    3. fallback pelo nome do time.
    """

    time_normalizado = normalizar(time)

    if posicoes:
        for nome_time, dados in posicoes.items():
            if normalizar(nome_time) == time_normalizado:
                posicao = dados.get("posicao", 10)

                try:
                    posicao = int(posicao)
                except (TypeError, ValueError):
                    posicao = 10

                posicao = max(1, min(posicao, 20))

                rating_max = 2000
                rating_min = 1300
                total_posicoes = 20

                rating = rating_max - (posicao - 1) * (
                    (rating_max - rating_min) / (total_posicoes - 1)
                )

                return round(rating, 2)

    for nome, valor in FORCA_BASE.items():
        if normalizar(nome) == time_normalizado:
            return round(1700 + valor * 2, 2)

    seed = sum(ord(c) for c in nome_limpo(time))
    return 1700 + (seed % 200) - 100


def chance_vitoria(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def analisar_jogo(time_a, time_b):
    rating_a = forca_inicial(time_a, POSICOES)
    rating_b = forca_inicial(time_b, POSICOES)

    chance_a = chance_vitoria(rating_a, rating_b)
    chance_b = chance_vitoria(rating_b, rating_a)

    empate = 0.26

    chance_a_final = chance_a * (1 - empate)
    chance_b_final = chance_b * (1 - empate)

    total = chance_a_final + chance_b_final + empate

    chance_a_final = chance_a_final / total * 100
    chance_b_final = chance_b_final / total * 100
    empate_final = empate / total * 100

    if chance_a_final > chance_b_final:
        favorito = time_a
    elif chance_b_final > chance_a_final:
        favorito = time_b
    else:
        favorito = "Equilibrado"

    return {
        "time_a": time_a,
        "time_b": time_b,
        "rating_a": round(rating_a, 2),
        "rating_b": round(rating_b, 2),
        "chance_a": round(chance_a_final, 1),
        "chance_b": round(chance_b_final, 1),
        "empate": round(empate_final, 1),
        "favorito": favorito,
    }


HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Analisador de Futebol</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            background: linear-gradient(135deg, #071b12, #0f3d25, #128c4a);
            color: white;
            min-height: 100vh;
        }

        .container {
            width: 95%;
            max-width: 980px;
            margin: auto;
            padding: 40px 0;
        }

        .hero {
            text-align: center;
            margin-bottom: 35px;
        }

        .hero h1 {
            font-size: 42px;
            margin-bottom: 10px;
        }

        .hero p {
            color: #d7ffe7;
            font-size: 18px;
        }

        .card {
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.25);
            backdrop-filter: blur(12px);
            border-radius: 22px;
            padding: 28px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.35);
        }

        form {
            display: grid;
            grid-template-columns: 1fr 1fr auto;
            gap: 15px;
            align-items: end;
        }

        label {
            font-weight: bold;
            display: block;
            margin-bottom: 8px;
        }

        select, input {
            width: 100%;
            padding: 14px;
            border-radius: 14px;
            border: none;
            outline: none;
            font-size: 16px;
        }

        button {
            padding: 14px 24px;
            border-radius: 14px;
            border: none;
            background: #00e676;
            color: #062112;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: 0.2s;
        }

        button:hover {
            background: #69f0ae;
            transform: translateY(-2px);
        }

        .resultado {
            margin-top: 30px;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 18px;
        }

        .box {
            background: rgba(0, 0, 0, 0.28);
            border-radius: 18px;
            padding: 22px;
            text-align: center;
        }

        .box h2 {
            margin: 0;
            font-size: 20px;
        }

        .numero {
            font-size: 38px;
            font-weight: bold;
            margin: 14px 0;
            color: #00e676;
        }

        .favorito {
            margin-top: 25px;
            background: rgba(0, 230, 118, 0.18);
            border: 1px solid rgba(0, 230, 118, 0.5);
            border-radius: 18px;
            padding: 20px;
            text-align: center;
            font-size: 22px;
            font-weight: bold;
        }

        .ratings {
            margin-top: 22px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 18px;
        }

        .rating-card {
            background: rgba(255, 255, 255, 0.10);
            padding: 18px;
            border-radius: 16px;
            text-align: center;
        }

        .times {
            margin-top: 35px;
        }

        .grid-times {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
        }

        .team {
            background: rgba(255, 255, 255, 0.10);
            padding: 12px;
            border-radius: 14px;
            text-align: center;
            font-size: 14px;
        }

        footer {
            text-align: center;
            margin-top: 35px;
            color: #c8f7dc;
            font-size: 14px;
        }

        @media (max-width: 760px) {
            form {
                grid-template-columns: 1fr;
            }

            .resultado {
                grid-template-columns: 1fr;
            }

            .ratings {
                grid-template-columns: 1fr;
            }

            .hero h1 {
                font-size: 32px;
            }
        }
    </style>
</head>

<body>
    <div class="container">

        <div class="hero">
            <h1>⚽ Analisador de Futebol</h1>
            <p>Simule chances de vitória usando rating Elo, força base e posição na tabela.</p>
        </div>

        <div class="card">
            <form method="POST">
                <div>
                    <label>Time da Casa</label>
                    <select name="time_a" required>
                        {% for time in times %}
                            <option value="{{ time }}" {% if resultado and resultado.time_a == time %}selected{% endif %}>
                                {{ time }}
                            </option>
                        {% endfor %}
                    </select>
                </div>

                <div>
                    <label>Time Visitante</label>
                    <select name="time_b" required>
                        {% for time in times %}
                            <option value="{{ time }}" {% if resultado and resultado.time_b == time %}selected{% endif %}>
                                {{ time }}
                            </option>
                        {% endfor %}
                    </select>
                </div>

                <button type="submit">Analisar</button>
            </form>

            {% if resultado %}
                <div class="resultado">
                    <div class="box">
                        <h2>{{ resultado.time_a }}</h2>
                        <div class="numero">{{ resultado.chance_a }}%</div>
                        <p>Chance de vitória</p>
                    </div>

                    <div class="box">
                        <h2>Empate</h2>
                        <div class="numero">{{ resultado.empate }}%</div>
                        <p>Probabilidade estimada</p>
                    </div>

                    <div class="box">
                        <h2>{{ resultado.time_b }}</h2>
                        <div class="numero">{{ resultado.chance_b }}%</div>
                        <p>Chance de vitória</p>
                    </div>
                </div>

                <div class="ratings">
                    <div class="rating-card">
                        <h3>{{ resultado.time_a }}</h3>
                        <p>Rating Elo: <strong>{{ resultado.rating_a }}</strong></p>
                    </div>

                    <div class="rating-card">
                        <h3>{{ resultado.time_b }}</h3>
                        <p>Rating Elo: <strong>{{ resultado.rating_b }}</strong></p>
                    </div>
                </div>

                <div class="favorito">
                    Favorito: {{ resultado.favorito }}
                </div>
            {% endif %}
        </div>

        <div class="times">
            <h2>Times cadastrados</h2>

            <div class="grid-times">
                {% for time in times %}
                    <div class="team">
                        {{ time }}
                    </div>
                {% endfor %}
            </div>
        </div>

        <footer>
            Sistema Flask com cálculo simples de força Elo.
        </footer>

    </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    resultado = None
    times = sorted(FORCA_BASE.keys())

    if request.method == "POST":
        time_a = request.form.get("time_a")
        time_b = request.form.get("time_b")

        if time_a and time_b:
            resultado = analisar_jogo(time_a, time_b)

    return render_template_string(
        HTML,
        times=times,
        resultado=resultado
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
