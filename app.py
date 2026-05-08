def forca_inicial(time, posicoes=None):
    """Retorna rating inicial Elo (~1300-2000) baseado na posição oficial da liga."""
    nt = normalizar(time)
    if posicoes and time in posicoes:
        pos = posicoes[time].get("posicao", 10)
        # Rating = 2000 para 1º colocado, 1300 para 20º (queda linear)
        rating = 2000 - (pos - 1) * (700 / 19)  # 19 é a diferença máxima (20-1)
        return rating
    # Fallback: FORCA_BASE ou valor médio 1700
    for nome, valor in FORCA_BASE.items():
        if normalizar(nome) == nt:
            return 1700 + valor * 2   # reduzido para não dominar
    seed = sum(ord(c) for c in nome_limpo(time))
    return 1700 + (seed % 200) - 100   # entre 1600 e 1800
