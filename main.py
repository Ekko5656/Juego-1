import math
import os
import random
import sys

import pygame

# ---------- Configuración (cambiá estos números para ajustar el juego) ----------
ANCHO, ALTO = 900, 650
FPS = 60
VIDAS = 5
VELOCIDAD = 320          # velocidad de avance
EMPUJE = 1500            # fuerza del gas lateral
FRICCION = 4.0
VIDA_BOSS = 30
DANIO_ESPERA = 0.25      # segundos entre disparos

# Mundo 3D
MITAD_PISTA = 300
PISO = -70
FOCAL = 500
HORIZONTE = 180
DIST_CAMARA = 260
ALTURA_CAMARA = 130
LEJOS = 2600

# Obstáculos: (tipo, distancia, duración del ciclo en segundos, desfase)
OBSTACULOS = [
    ("laser", 900, 2.6, 0.0),
    ("puerta", 1800, 3.2, 1.0),
    ("martillo", 2700, 2.8, 0.0),
    ("laser", 3500, 2.0, 0.7),
    ("puerta", 4300, 2.6, 0.3),
    ("martillo", 5100, 2.2, 1.1),
    ("laser", 5700, 1.8, 0.2),
]
INICIO_BOSS = 6500

NEGRO = (15, 10, 30)
BLANCO = (255, 255, 255)


# ================= LÓGICA =================
def nuevo_juego():
    return {
        "x": 0.0, "vx": 0.0, "z": 0.0, "vel": VELOCIDAD, "t": 0.0,
        "vidas": VIDAS, "invulnerable": 0.0, "recarga": 0.0,
        "estado": "jugando", "boss": None,
        "balas": [],     # [x, z]
        "fuego": [],     # [x, z, vx]
        "gases": [],     # [x, y, z, vx, vida]
    }


def fase(obstaculo, t):
    """Valor entre 0 y 1 que indica en qué parte del ciclo está el obstáculo."""
    _, _, ciclo, desfase = obstaculo
    return ((t + desfase) / ciclo) % 1.0


def laser_encendido(obstaculo, t):
    return fase(obstaculo, t) < 0.55


def hueco_puerta(obstaculo, t):
    """Mitad del ancho del hueco entre las dos puertas."""
    apertura = max(0.0, math.sin(fase(obstaculo, t) * 2 * math.pi))
    return min(1.0, apertura * 1.5) * 190


def x_martillo(obstaculo, t):
    return math.sin(fase(obstaculo, t) * 2 * math.pi) * 230


def golpea(obstaculo, x, t):
    tipo = obstaculo[0]
    if tipo == "laser":
        return laser_encendido(obstaculo, t)
    if tipo == "puerta":
        return abs(x) + 30 > hueco_puerta(obstaculo, t)
    return abs(x - x_martillo(obstaculo, t)) < 130


def perder_vida(j):
    if j["invulnerable"] > 0:
        return
    j["vidas"] -= 1
    j["invulnerable"] = 1.5
    if j["vidas"] <= 0:
        j["estado"] = "perdiste"


def actualizar(j, dt, izquierda, derecha, frenar, disparar):
    for g in j["gases"]:
        g[0] += g[3] * dt
        g[4] -= dt
    j["gases"] = [g for g in j["gases"] if g[4] > 0]

    if j["estado"] != "jugando":
        return

    j["t"] += dt
    j["invulnerable"] = max(0.0, j["invulnerable"] - dt)
    j["recarga"] = max(0.0, j["recarga"] - dt)

    # Movimiento lateral a gas
    direccion = int(derecha) - int(izquierda)
    if direccion:
        j["vx"] += direccion * EMPUJE * dt
        for _ in range(2):
            j["gases"].append([
                j["x"] - direccion * 55, random.uniform(-10, 10), j["z"],
                -direccion * random.uniform(120, 260), random.uniform(0.15, 0.4),
            ])
    j["vx"] -= j["vx"] * min(1.0, FRICCION * dt)
    j["x"] += j["vx"] * dt
    limite = MITAD_PISTA - 40
    if abs(j["x"]) > limite:
        j["x"] = max(-limite, min(limite, j["x"]))
        j["vx"] = 0

    if j["boss"] is None:
        avanzar(j, dt, frenar)
    else:
        pelear(j, dt, disparar)


def avanzar(j, dt, frenar):
    objetivo = 0 if frenar else VELOCIDAD
    j["vel"] += (objetivo - j["vel"]) * min(1.0, 12 * dt)
    z_antes = j["z"]
    j["z"] += j["vel"] * dt

    for obstaculo in OBSTACULOS:
        z = obstaculo[1]
        if z_antes < z <= j["z"] and golpea(obstaculo, j["x"], j["t"]):
            perder_vida(j)
            j["z"] = z - 220      # rebota para volver a intentar
            j["vel"] = 0

    if j["z"] >= INICIO_BOSS:
        j["boss"] = {"x": 0.0, "vida": VIDA_BOSS, "t": 0.0, "ataque": 2.0, "golpe": 0.0}
        j["invulnerable"] = 1.5


def pelear(j, dt, disparar):
    boss = j["boss"]
    boss["t"] += dt
    boss["golpe"] = max(0.0, boss["golpe"] - dt)
    boss["x"] = math.sin(boss["t"] * 0.9) * 200
    furioso = boss["vida"] <= VIDA_BOSS / 2

    boss["ataque"] -= dt
    if boss["ataque"] <= 0:
        boss["ataque"] = 0.9 if furioso else 1.4
        tiempo_vuelo = 900 / 650
        apuntar = (j["x"] - boss["x"]) / tiempo_vuelo
        desvios = (-170, 0, 170) if furioso else (0,)
        for d in desvios:
            j["fuego"].append([boss["x"], j["z"] + 900, apuntar + d])

    if disparar and j["recarga"] <= 0:
        j["balas"].append([j["x"], j["z"] + 40])
        j["recarga"] = DANIO_ESPERA

    for b in j["balas"][:]:
        b[1] += 1500 * dt
        if b[1] >= j["z"] + 900:
            if abs(b[0] - boss["x"]) < 100:
                boss["vida"] -= 1
                boss["golpe"] = 0.12
            j["balas"].remove(b)

    for f in j["fuego"][:]:
        f[0] += f[2] * dt
        f[1] -= 650 * dt
        if f[1] <= j["z"]:
            if abs(f[0] - j["x"]) < 65:
                perder_vida(j)
            j["fuego"].remove(f)

    if boss["vida"] <= 0 and j["estado"] == "jugando":
        j["estado"] = "ganaste"
        j["fuego"].clear()


# ================= BOTONES TÁCTILES =================
# nombre: (x, y, radio)
BOTONES = {
    "izquierda": (75, 575, 62),
    "derecha": (220, 575, 62),
    "frenar": (680, 575, 62),
    "disparar": (825, 575, 62),
}


def botones_tocados(puntos):
    """Devuelve los nombres de los botones que están bajo algún dedo."""
    return {nombre for nombre, (bx, by, r) in BOTONES.items()
            for x, y in puntos if (x - bx) ** 2 + (y - by) ** 2 <= (r + 12) ** 2}


def a_juego(px, py, ancho, alto):
    """Pasa un punto de la pantalla del celular a las coordenadas del juego."""
    escala = min(ancho / ANCHO, alto / ALTO)
    return ((px - (ancho - ANCHO * escala) / 2) / escala,
            (py - (alto - ALTO * escala) / 2) / escala)


def dibujar_botones(pantalla, fuente, activos):
    etiquetas = {"izquierda": "<", "derecha": ">", "frenar": "FRENO", "disparar": "FUEGO"}
    for nombre, (x, y, r) in BOTONES.items():
        relleno = (255, 80, 130) if nombre in activos else (40, 30, 90)
        pygame.draw.circle(pantalla, relleno, (x, y), r)
        pygame.draw.circle(pantalla, (0, 240, 255), (x, y), r, 4)
        texto = fuente.render(etiquetas[nombre], True, BLANCO)
        pantalla.blit(texto, texto.get_rect(center=(x, y)))


# ================= DIBUJO 3D =================
def proyectar(x, y, z, camx, camz):
    """Convierte un punto 3D en un punto de la pantalla."""
    d = max(20.0, z - camz)
    escala = FOCAL / d
    return (ANCHO / 2 + (x - camx) * escala,
            HORIZONTE - (y - ALTURA_CAMARA) * escala)


def cara(pantalla, puntos, color, borde=2):
    """Polígono con contorno oscuro, estilo anime."""
    pygame.draw.polygon(pantalla, color, puntos)
    if borde:
        pygame.draw.polygon(pantalla, NEGRO, puntos, borde)


def caja(pantalla, x1, x2, y1, y2, z1, z2, color, camx, camz):
    def p(x, y, z):
        return proyectar(x, y, z, camx, camz)

    oscuro = tuple(int(c * 0.55) for c in color)
    claro = tuple(min(255, int(c * 1.3)) for c in color)
    if x1 > camx:       # cara izquierda visible
        cara(pantalla, [p(x1, y1, z1), p(x1, y2, z1), p(x1, y2, z2), p(x1, y1, z2)], oscuro)
    if x2 < camx:       # cara derecha visible
        cara(pantalla, [p(x2, y1, z1), p(x2, y2, z1), p(x2, y2, z2), p(x2, y1, z2)], oscuro)
    if y2 < ALTURA_CAMARA:
        cara(pantalla, [p(x1, y2, z1), p(x2, y2, z1), p(x2, y2, z2), p(x1, y2, z2)], claro)
    cara(pantalla, [p(x1, y1, z1), p(x2, y1, z1), p(x2, y2, z1), p(x1, y2, z1)], color)


def dibujar_fondo(pantalla, estrellas, camx, camz, t):
    for y in range(0, ALTO, 5):
        k = y / ALTO
        pygame.draw.rect(pantalla, (int(20 + 70 * k), int(10 + 15 * k), int(50 + 80 * k)),
                         (0, y, ANCHO, 5))
    for x, y, r in estrellas:
        brillo = 180 + int(70 * math.sin(t * 3 + x))
        pygame.draw.circle(pantalla, (brillo, brillo, 255), (x, y), r)
    pygame.draw.circle(pantalla, (255, 120, 170), (ANCHO // 2, HORIZONTE - 40), 70)
    pygame.draw.circle(pantalla, (255, 190, 200), (ANCHO // 2, HORIZONTE - 40), 52)

    # Pista en perspectiva
    cerca, lejos = camz + 60, camz + LEJOS
    esquinas = [proyectar(-MITAD_PISTA, PISO, cerca, camx, camz),
                proyectar(MITAD_PISTA, PISO, cerca, camx, camz),
                proyectar(MITAD_PISTA, PISO, lejos, camx, camz),
                proyectar(-MITAD_PISTA, PISO, lejos, camx, camz)]
    pygame.draw.polygon(pantalla, (30, 20, 70), esquinas)
    z = (int(cerca) // 150 + 1) * 150
    while z < lejos:
        pygame.draw.line(pantalla, (90, 70, 190),
                         proyectar(-MITAD_PISTA, PISO, z, camx, camz),
                         proyectar(MITAD_PISTA, PISO, z, camx, camz), 2)
        z += 150
    for x in range(-MITAD_PISTA, MITAD_PISTA + 1, 100):
        color = (0, 240, 255) if abs(x) == MITAD_PISTA else (90, 70, 190)
        pygame.draw.line(pantalla, color,
                         proyectar(x, PISO, cerca, camx, camz),
                         proyectar(x, PISO, lejos, camx, camz), 3)


def dibujar_obstaculo(pantalla, obstaculo, t, camx, camz):
    tipo, z = obstaculo[0], obstaculo[1]
    m = MITAD_PISTA
    if tipo == "laser":
        for lado in (-m - 30, m):
            caja(pantalla, lado, lado + 30, PISO, 100, z, z + 30, (110, 120, 160), camx, camz)
        f = fase(obstaculo, t)
        if f < 0.55:
            color, grosor = (255, 40, 90), 7
        elif f > 0.85:
            color, grosor = (255, 220, 40), 2     # aviso: se va a encender
        else:
            return
        for y in (-45, -5, 35, 75):
            a = proyectar(-m, y, z, camx, camz)
            b = proyectar(m, y, z, camx, camz)
            pygame.draw.line(pantalla, color, a, b, grosor)
            if grosor > 2:
                pygame.draw.line(pantalla, BLANCO, a, b, 2)
    elif tipo == "puerta":
        hueco = hueco_puerta(obstaculo, t)
        caja(pantalla, -m, -hueco, PISO, 90, z, z + 40, (60, 170, 230), camx, camz)
        caja(pantalla, hueco, m, PISO, 90, z, z + 40, (60, 170, 230), camx, camz)
    else:
        x = x_martillo(obstaculo, t)
        caja(pantalla, x - 90, x + 90, PISO, 90, z, z + 80, (240, 150, 40), camx, camz)


def dibujar_nave(pantalla, j, camx, camz):
    if j["invulnerable"] > 0 and int(j["t"] * 12) % 2 == 0:
        return
    t = pygame.time.get_ticks() / 1000
    flotar = math.sin(t * 5) * 4
    inclinacion = -j["vx"] / 900

    def p(x, y, z):
        # Rota el punto para que la nave se incline al doblar
        c, s = math.cos(inclinacion), math.sin(inclinacion)
        return proyectar(j["x"] + x * c - y * s, x * s + y * c + flotar,
                         j["z"] + z, camx, camz)

    # Alas
    for s in (-1, 1):
        cara(pantalla, [p(s * 15, 0, 25), p(s * 85, -8, -30), p(s * 80, -8, -48),
                        p(s * 15, -3, -35)], (240, 245, 255))
        cara(pantalla, [p(s * 52, -4, -6), p(s * 85, -8, -30), p(s * 80, -8, -48),
                        p(s * 52, -5, -41)], (255, 60, 110))
        cara(pantalla, [p(s * 80, -8, -30), p(s * 92, 28, -52), p(s * 80, -8, -48)],
             (80, 90, 220))
    # Cuerpo
    punta, atras = p(0, 0, 80), p(0, 24, -35)
    cara(pantalla, [punta, p(-25, 0, -30), p(0, -16, -35)], (140, 150, 200))
    cara(pantalla, [punta, p(25, 0, -30), p(0, -16, -35)], (140, 150, 200))
    cara(pantalla, [punta, p(-25, 0, -30), atras], (255, 255, 255))
    cara(pantalla, [punta, p(25, 0, -30), atras], (200, 210, 245))
    # Cabina con brillo
    cara(pantalla, [p(0, 12, 42), p(-12, 17, 5), p(0, 29, -8), p(12, 17, 5)], (40, 220, 255))
    pygame.draw.line(pantalla, BLANCO, p(-3, 16, 30), p(-8, 19, 8), 3)
    # Aleta trasera
    cara(pantalla, [p(0, 22, -8), p(0, 55, -48), p(0, 20, -35)], (255, 60, 110))
    # Turbinas con fuego animado
    largo = 8 if j["vel"] < 50 else 24 + math.sin(t * 40) * 7
    for s in (-1, 1):
        cx, cy = p(s * 17, -4, -38)
        pygame.draw.circle(pantalla, NEGRO, (int(cx), int(cy)), 17)
        pygame.draw.circle(pantalla, (80, 90, 220), (int(cx), int(cy)), 14)
        for color, k in (((60, 150, 255), 1.0), ((130, 230, 255), 0.65), (BLANCO, 0.3)):
            ancho = 12 * k
            cara(pantalla, [(cx - ancho, cy), (cx, cy + largo * 2 * k),
                            (cx + ancho, cy), (cx, cy - ancho)], color, 0)


def dibujar_boss(pantalla, fuente, j, camx, camz):
    """Gauto, el buitre."""
    boss = j["boss"]
    cx, cy = proyectar(boss["x"], 50 + math.sin(boss["t"] * 4) * 15,
                       j["z"] + 900, camx, camz)
    # Aparece creciendo
    e = min(1.0, 0.3 + boss["t"]) * FOCAL / (900 + DIST_CAMARA) * 2.1

    def p(x, y):
        return (cx + x * e, cy - y * e)

    furioso = boss["vida"] <= VIDA_BOSS / 2
    golpeado = boss["golpe"] > 0
    plumas = BLANCO if golpeado else ((130, 30, 40) if furioso else (70, 50, 60))
    puntas = BLANCO if golpeado else (35, 25, 35)
    aleteo = math.sin(boss["t"] * 7) * 45

    # Alas que aletean
    for s in (-1, 1):
        cara(pantalla, [p(s * 35, 5), p(s * 100, 45 + aleteo * 0.6), p(s * 190, 40 + aleteo),
                        p(s * 165, 10 + aleteo * 0.8), p(s * 180, -12 + aleteo * 0.7),
                        p(s * 135, -15 + aleteo * 0.5), p(s * 140, -40 + aleteo * 0.4),
                        p(s * 90, -30), p(s * 40, -45)], plumas, 3)
        cara(pantalla, [p(s * 135, 38 + aleteo * 0.8), p(s * 190, 40 + aleteo),
                        p(s * 165, 10 + aleteo * 0.8)], puntas, 3)
    # Patas
    for s in (-1, 1):
        for dedo in (-12, 0, 12):
            pygame.draw.line(pantalla, (230, 180, 60), p(s * 22, -65),
                             p(s * 22 + dedo, -95), max(2, int(6 * e)))
    # Cuerpo
    cara(pantalla, [p(-50, 5), p(0, 25), p(50, 5), p(38, -55), p(0, -75), p(-38, -55)],
         plumas, 3)
    # Collar de plumas blancas
    cara(pantalla, [p(-55, 12), p(-35, 28), p(0, 35), p(35, 28), p(55, 12), p(38, -8),
                    p(25, 6), p(12, -16), p(0, 2), p(-12, -16), p(-25, 6), p(-38, -8)],
         (240, 240, 235), 3)
    # Cabeza pelada
    piel = BLANCO if golpeado else (225, 120, 125)
    cara(pantalla, [p(-18, 30), p(-32, 60), p(-26, 88), p(0, 100), p(26, 88), p(32, 60),
                    p(18, 30)], piel, 3)
    # Ojos enojados
    for s in (-1, 1):
        cara(pantalla, [p(s * 5, 66), p(s * 27, 80), p(s * 24, 63), p(s * 11, 60)],
             (255, 230, 40), 2)
        pygame.draw.circle(pantalla, NEGRO, p(s * 16, 67), max(2, int(4 * e)))
        pygame.draw.line(pantalla, NEGRO, p(s * 3, 70), p(s * 30, 87), max(2, int(5 * e)))
    # Pico ganchudo (se abre antes de atacar)
    abierta = 16 if boss["ataque"] < 0.35 else 0
    if abierta:
        cara(pantalla, [p(-14, 45), p(14, 45), p(0, 8 - abierta)], (255, 140, 30), 2)
    cara(pantalla, [p(-13, 62), p(13, 62), p(17, 45), p(8, 30), p(0, 14), p(-3, 32),
                    p(-17, 45)], (245, 190, 50), 3)

    # Barra de vida
    pygame.draw.rect(pantalla, NEGRO, (248, 58, 404, 20))
    pygame.draw.rect(pantalla, (255, 50, 80),
                     (250, 60, 400 * max(0, boss["vida"]) / VIDA_BOSS, 16))
    texto = fuente.render("GAUTO", True, BLANCO)
    pantalla.blit(texto, texto.get_rect(center=(ANCHO / 2, 38)))


def dibujar_bola(pantalla, x, y, z, camx, camz, colores, radio, t):
    sx, sy = proyectar(x, y, z, camx, camz)
    r = radio * FOCAL / max(60.0, z - camz)
    for i, color in enumerate(colores):
        pulso = 1 + 0.15 * math.sin(t * 30 + i * 2)
        pygame.draw.circle(pantalla, color, (int(sx), int(sy)),
                           max(1, int(r * (1 - i * 0.3) * pulso)))


def dibujar(pantalla, fuente, grande, j, estrellas):
    camx = j["x"] * 0.6
    camz = j["z"] - DIST_CAMARA
    t = j["t"]
    dibujar_fondo(pantalla, estrellas, camx, camz, t)

    # Primero lo lejano, después lo cercano
    for obstaculo in sorted(OBSTACULOS, key=lambda o: -o[1]):
        if j["z"] < obstaculo[1] < camz + LEJOS:
            dibujar_obstaculo(pantalla, obstaculo, t, camx, camz)

    if j["boss"]:
        dibujar_boss(pantalla, fuente, j, camx, camz)
    for x, z in j["balas"]:
        dibujar_bola(pantalla, x, 0, z, camx, camz,
                     [(40, 200, 255), (160, 240, 255), BLANCO], 14, t)
    for x, z, _ in sorted(j["fuego"], key=lambda f: -f[1]):
        dibujar_bola(pantalla, x, 0, z, camx, camz,
                     [(220, 40, 20), (255, 140, 20), (255, 240, 120)], 42, t)

    for x, y, z, _, vida in j["gases"]:
        sx, sy = proyectar(x, y, z, camx, camz)
        pygame.draw.circle(pantalla, (180, 235, 255), (int(sx), int(sy)), int(3 + vida * 22))
    dibujar_nave(pantalla, j, camx, camz)

    pantalla.blit(fuente.render(f"Vidas: {max(0, j['vidas'])}", True, BLANCO), (15, 12))
    if not j["boss"]:
        avance = min(100, int(j["z"] / INICIO_BOSS * 100))
        pantalla.blit(fuente.render(f"Recorrido: {avance}%", True, BLANCO), (ANCHO - 230, 12))
    ayuda = "FUEGO: disparar" if j["boss"] else "FRENO: esperar"
    texto = fuente.render(ayuda, True, (255, 230, 120))
    pantalla.blit(texto, texto.get_rect(center=(ANCHO / 2, ALTO - 22)))

    if j["estado"] != "jugando":
        mensaje = "¡VENCISTE A GAUTO!" if j["estado"] == "ganaste" else "PERDISTE"
        for i, (f, linea) in enumerate([(grande, mensaje),
                                        (fuente, "Tocá la pantalla para reiniciar")]):
            texto = f.render(linea, True, BLANCO)
            rect = texto.get_rect(center=(ANCHO / 2, ALTO / 2 + i * 60))
            pygame.draw.rect(pantalla, NEGRO, rect.inflate(30, 14))
            pantalla.blit(texto, rect)


def main():
    pygame.init()
    if "ANDROID_ARGUMENT" in os.environ:      # celular: pantalla completa
        ventana = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:                                     # PC: ventana normal
        ventana = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Nave 3D contra Gauto")
    pantalla = pygame.Surface((ANCHO, ALTO))
    reloj = pygame.time.Clock()
    fuente = pygame.font.Font(None, 34)
    grande = pygame.font.Font(None, 72)
    estrellas = [(random.randrange(ANCHO), random.randrange(HORIZONTE), random.choice((1, 1, 2)))
                 for _ in range(90)]
    j = nuevo_juego()
    dedos = {}                                # dedo -> posición
    fin = 0.0                                 # tiempo desde que terminó la partida

    while True:
        dt = min(reloj.tick(FPS) / 1000, 0.05)
        ancho, alto = ventana.get_size()
        fin = fin + dt if j["estado"] != "jugando" else 0.0
        reiniciar = False

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_AC_BACK:      # botón "atrás" de Android
                    pygame.quit()
                    sys.exit()
                if evento.key == pygame.K_r:
                    reiniciar = True
            if evento.type in (pygame.FINGERDOWN, pygame.FINGERMOTION):
                dedos[evento.finger_id] = a_juego(evento.x * ancho, evento.y * alto,
                                                  ancho, alto)
                if evento.type == pygame.FINGERDOWN and fin > 1:
                    reiniciar = True
            if evento.type == pygame.FINGERUP:
                dedos.pop(evento.finger_id, None)
            if evento.type == pygame.MOUSEBUTTONDOWN and fin > 1:
                reiniciar = True

        if reiniciar:
            j = nuevo_juego()

        puntos = list(dedos.values())
        if pygame.mouse.get_pressed()[0]:       # para probar con el mouse en la PC
            puntos.append(a_juego(*pygame.mouse.get_pos(), ancho, alto))
        activos = botones_tocados(puntos)

        k = pygame.key.get_pressed()
        actualizar(j, dt,
                   k[pygame.K_LEFT] or "izquierda" in activos,
                   k[pygame.K_RIGHT] or "derecha" in activos,
                   k[pygame.K_DOWN] or "frenar" in activos,
                   k[pygame.K_SPACE] or "disparar" in activos)
        dibujar(pantalla, fuente, grande, j, estrellas)
        dibujar_botones(pantalla, fuente, activos)

        # Agrandar el dibujo hasta llenar la pantalla sin deformarlo
        escala = min(ancho / ANCHO, alto / ALTO)
        tam = (int(ANCHO * escala), int(ALTO * escala))
        ventana.fill((0, 0, 0))
        ventana.blit(pygame.transform.scale(pantalla, tam),
                     ((ancho - tam[0]) // 2, (alto - tam[1]) // 2))
        pygame.display.flip()


if __name__ == "__main__":
    main()
