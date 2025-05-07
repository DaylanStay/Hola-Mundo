import cv2
import mediapipe as mp
import numpy as np
import socket
import threading
import time

# Configuración del servidor socket
HOST = '127.0.0.1'  # Localhost
PORT = 12345        # Puerto arbitrario
servidor = None
cliente_conectado = False
mensaje_lock = threading.Lock()
ultimo_gesto = " "

# Inicializar MediaPipe y cámara
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7, model_complexity=1)
mp_draw = mp.solutions.drawing_utils
cap = cv2.VideoCapture(0)

def calcular_angulo(punto1, punto2, punto3):
    """Calcula el ángulo formado por tres puntos en el espacio 3D"""
    a = np.array([punto1.x, punto1.y, punto1.z])
    b = np.array([punto2.x, punto2.y, punto2.z])
    c = np.array([punto3.x, punto3.y, punto3.z])
    
    ba = a - b
    bc = c - b
    
    # Calcular el ángulo usando el producto escalar
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    
    return np.degrees(angle)

def detectar_dedo_extendido(landmarks, base, medio, punta, umbral=160):
    """Determina si un dedo está extendido basado en el ángulo entre articulaciones"""
    angulo = calcular_angulo(landmarks[base], landmarks[medio], landmarks[punta])
    return 1 if angulo > umbral else 0

def obtener_dedos_por_angulo(hand_landmarks):
    """Detecta dedos extendidos usando el método del ángulo entre articulaciones"""
    landmarks = hand_landmarks.landmark
    dedos = []
    
    # Pulgar (usa diferentes puntos de referencia)
    angulo_pulgar = calcular_angulo(landmarks[1], landmarks[2], landmarks[4])
    dedos.append(1 if angulo_pulgar > 150 else 0)
    
    # Índice
    dedos.append(detectar_dedo_extendido(landmarks, 5, 6, 8))
    
    # Medio
    dedos.append(detectar_dedo_extendido(landmarks, 9, 10, 12))
    
    # Anular
    dedos.append(detectar_dedo_extendido(landmarks, 13, 14, 16))
    
    # Meñique
    dedos.append(detectar_dedo_extendido(landmarks, 17, 18, 20))
    
    return dedos

def detectar_gesto(dedos):
    """Determina el gesto basado en los dedos extendidos"""
    # Piedra: todos los dedos cerrados
    if sum(dedos) <= 1:  # Permitimos cierta flexibilidad para el pulgar
        return "Piedra"
    
    # Tijera: solo índice y medio extendidos
    elif dedos[1] == 1 and dedos[2] == 1 and dedos[3] == 0 and dedos[4] == 0:
        return "Tijera"
    
    # Papel: todos o la mayoría de los dedos extendidos
    elif sum(dedos) >= 4:
        return "Papel"
    
    else:
        return " "

def manejar_cliente(conn, addr):
    global cliente_conectado, ultimo_gesto
    cliente_conectado = True
    
    try:
        while True:
            # Enviar el último gesto detectado
            with mensaje_lock:
                mensaje = ultimo_gesto
            
            try:
                conn.sendall(mensaje.encode('utf-8'))
                time.sleep(0.1)
            except:
                break
    except:
        pass
    finally:
        conn.close()
        cliente_conectado = False

def iniciar_servidor():
    """Inicia el servidor de sockets y espera conexiones"""
    global servidor
    
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        servidor.bind((HOST, PORT))
        servidor.listen(1)
        
        while True:
            conn, addr = servidor.accept()
            thread = threading.Thread(target=manejar_cliente, args=(conn, addr))
            thread.daemon = True
            thread.start()
    except Exception as e:
        print(f"Error en el servidor: {e}")
    finally:
        if servidor:
            servidor.close()

# Iniciar el servidor en un hilo separado
servidor_thread = threading.Thread(target=iniciar_servidor)
servidor_thread.daemon = True
servidor_thread.start()

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Voltear horizontalmente para una vista tipo espejo
        frame = cv2.flip(frame, 1)
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        gesto = " "
        texto_debug = ""

        if results.multi_hand_landmarks:
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # Dibujar landmarks
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                
                # Detectar dedos usando método de ángulos
                dedos = obtener_dedos_por_angulo(hand_landmarks)
                
                # Detectar gesto
                gesto = detectar_gesto(dedos)
                
                # Información de depuración
                texto_debug = f"Dedos: {dedos}"
        
        # Actualizar el último gesto detectado
        if gesto != ultimo_gesto:
            with mensaje_lock:
                ultimo_gesto = gesto
        
        # Estado de conexión
        estado_conexion = "Conectado" if cliente_conectado else "Esperando conexion..."
        
        # Mostrar información en pantalla
        cv2.putText(frame, f"Gesto: {gesto}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, texto_debug, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 1)
        cv2.putText(frame, f"Cliente: {estado_conexion}", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 1)
        
        # Mostrar la imagen
        cv2.imshow("Detector de gestos", frame)
        
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    # Limpieza
    cap.release()
    cv2.destroyAllWindows()
    if servidor:
        servidor.close()
    print("Programa finalizado")