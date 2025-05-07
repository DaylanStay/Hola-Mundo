using UnityEngine;
using TMPro;
using System;
using System.Net.Sockets;
using System.Text;
using System.Threading;

public class GestoSocketReader : MonoBehaviour
{
    public TextMeshPro texto;
    
    [Header("Configuración de Socket")]
    public string hostIP = "127.0.0.1";
    public int puerto = 12345;
    
    private TcpClient clienteSocket;
    private NetworkStream flujoRed;
    private Thread hiloLectura;
    private bool hiloActivo = false;
    private string gestoActual = " ";
    private string estadoConexion = "Desconectado";
    private bool reconectarEnSiguienteFrame = false;
    private float tiempoUltimoIntento = 0f;
    private float intervaloReconexion = 2f; // segundos

    void Start()
    {
        Debug.Log("Iniciando cliente de gestos...");
        IniciarConexion();
    }

    void Update()
    {
        // Actualizar texto con el gesto actual y estado de conexión
        texto.text = $"Gesto: {gestoActual}";
        
        // Intentar reconectar si es necesario
        if (reconectarEnSiguienteFrame && Time.time - tiempoUltimoIntento > intervaloReconexion)
        {
            tiempoUltimoIntento = Time.time;
            IniciarConexion();
        }
    }

    void IniciarConexion()
    {
        // Cerrar conexión anterior si existe
        CerrarConexion();
        
        try
        {
            Debug.Log($"Conectando a {hostIP}:{puerto}...");
            estadoConexion = "Conectando...";
            
            clienteSocket = new TcpClient();
            
            // Intentar conectar con un timeout
            IAsyncResult resultado = clienteSocket.BeginConnect(hostIP, puerto, null, null);
            bool exito = resultado.AsyncWaitHandle.WaitOne(2000);
            
            if (!exito)
            {
                // Timeout en la conexión
                clienteSocket.Close();
                throw new Exception("Timeout al conectar");
            }
            
            // Finalizar conexión
            clienteSocket.EndConnect(resultado);
            
            // Obtener flujo de red
            flujoRed = clienteSocket.GetStream();
            
            // Iniciar hilo de lectura
            hiloActivo = true;
            hiloLectura = new Thread(LeerDatos);
            hiloLectura.IsBackground = true;
            hiloLectura.Start();
            
            estadoConexion = "Conectado";
            reconectarEnSiguienteFrame = false;
            Debug.Log("Conexion establecida correctamente");
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"Error al conectar: {ex.Message}");
            estadoConexion = "Error: " + ex.Message;
            reconectarEnSiguienteFrame = true;
        }
    }

    void LeerDatos()
    {
        byte[] buffer = new byte[1024];
        
        while (hiloActivo && clienteSocket != null && clienteSocket.Connected)
        {
            try
            {
                // Leer datos del servidor
                int bytesLeidos = flujoRed.Read(buffer, 0, buffer.Length);
                
                if (bytesLeidos > 0)
                {
                    string mensaje = Encoding.UTF8.GetString(buffer, 0, bytesLeidos);
                    gestoActual = mensaje.Trim();
                }
                else
                {
                    break;
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"Error en la lectura de datos: {ex.Message}");
                break;
            }
        }
        
        // Si salimos del bucle, la conexión se perdió
        if (hiloActivo)
        {
            // Usar una acción para ejecutar en el hilo principal
            UnityMainThreadDispatcher.Instance().Enqueue(() => {
                Debug.LogWarning("Conexion perdida, intentando reconectar...");
                estadoConexion = "Reconectando...";
                reconectarEnSiguienteFrame = true;
            });
        }
    }

    void CerrarConexion()
    {
        hiloActivo = false;
        
        if (hiloLectura != null && hiloLectura.IsAlive)
        {
            try
            {
                hiloLectura.Abort();
            }
            catch (Exception) { }
            hiloLectura = null;
        }
        
        if (flujoRed != null)
        {
            flujoRed.Close();
            flujoRed = null;
        }
        
        if (clienteSocket != null)
        {
            if (clienteSocket.Connected)
                clienteSocket.Close();
            clienteSocket = null;
        }
    }

    void OnApplicationQuit()
    {
        CerrarConexion();
    }

    void OnDestroy()
    {
        CerrarConexion();
    }
}

// Clase auxiliar para ejecutar acciones en el hilo principal de Unity
// Esta clase permite enviar acciones desde hilos secundarios al hilo principal
public class UnityMainThreadDispatcher : MonoBehaviour
{
    private static UnityMainThreadDispatcher _instance;
    private readonly System.Collections.Generic.Queue<Action> _executionQueue = new System.Collections.Generic.Queue<Action>();
    private readonly object _lock = new object();

    public static UnityMainThreadDispatcher Instance()
    {
        if (_instance == null)
        {
            var go = new GameObject("UnityMainThreadDispatcher");
            _instance = go.AddComponent<UnityMainThreadDispatcher>();
            DontDestroyOnLoad(go);
        }
        return _instance;
    }

    void Awake()
    {
        if (_instance == null)
        {
            _instance = this;
            DontDestroyOnLoad(gameObject);
        }
    }

    public void Enqueue(Action action)
    {
        lock (_lock)
        {
            _executionQueue.Enqueue(action);
        }
    }

    void Update()
    {
        lock (_lock)
        {
            while (_executionQueue.Count > 0)
            {
                _executionQueue.Dequeue().Invoke();
            }
        }
    }
}