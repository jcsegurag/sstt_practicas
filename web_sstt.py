# coding=utf-8
#!/usr/bin/env python3

import socket
import selectors    #https://docs.python.org/3/library/selectors.html
import select
import types        # Para definir el tipo de datos data
import argparse     # Leer parametros de ejecución
import os           # Obtener ruta y extension
from datetime import datetime, timedelta # Fechas de los mensajes HTTP
import time         # Timeout conexión
import sys          # sys.exit
import re           # Analizador sintáctico
import logging      # Para imprimir logs



BUFSIZE = 8192 # Tamaño máximo del buffer que se puede utilizar
TIMEOUT_CONNECTION = 20 # Timout para la conexión persistente
MAX_ACCESOS = 10
diccionario={}

# Extensiones admitidas (extension, name in HTTP)
filetypes = {"gif":"image/gif", "jpg":"image/jpg", "jpeg":"image/jpeg", "png":"image/png", "htm":"text/htm", 
             "html":"text/html", "css":"text/css", "js":"text/js"}

# Configuración de logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s.%(msecs)03d] [%(levelname)-7s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()

#Expresión regular para crear diccionario con atributos de la solicitud
atributos = r'(?P<clave>[A-Z].): (?P<valor>.)'

def enviar_mensaje(cs, data):
    """ Esta función envía datos (data) a través del socket cs
        Devuelve el número de bytes enviados.
    """
    return cs.send(data.encode())


def recibir_mensaje(cs):
    """ Esta función recibe datos a través del socket cs
        Leemos la información que nos llega. recv() devuelve un string con los datos.
    """
    return cs.recv(BUFSIZE).decode()


def cerrar_conexion(cs):
    """ Esta función cierra una conexión activa.
    """
    cs.close()

def enviar_recurso(ruta, header, tam ,cs):
    tamano_todo = len(header) + tam
    if(tamano_todo <= BUFSIZE):
        print("Enviar recurso < bufsize")
        fichero = open(ruta, "rb")
        datos = fichero.read()
        para_enviar = header.encode() + datos
        cs.send(para_enviar)
        print("Salir enviar recurso < bufsize")

    else:
        print("Enviar recurso > bufsize")
        enviar_mensaje(cs, header)
        print("Cabecera enviada")
        fichero = open(ruta, "rb")
        while(True):
            print("Envio datos porque es muy grande el archivo")
            datos = fichero.read(BUFSIZE)
            if(not datos):
                print("Ya no hay datos")
                break
            cs.send(datos)
            print("Salir enviar recurso > bufsize")


def process_cookies(headers,  cs):
    """ Esta función procesa la cookie cookie_counter
        1. Se analizan las cabeceras en headers para buscar la cabecera Cookie
        2. Una vez encontrada una cabecera Cookie se comprueba si el valor es cookie_counter
        3. Si no se encuentra cookie_counter , se devuelve 1
        4. Si se encuentra y tiene el valor MAX_ACCESSOS se devuelve MAX_ACCESOS
        5. Si se encuentra y tiene un valor 1 <= x < MAX_ACCESOS se incrementa en 1 y se devuelve el valor
    """
    lineas = headers.split(sep = "\r\n", maxsplit = -1)
    i=0
    for linea in lineas:
        cabeceras = linea[i].split(sep = ' ', maxsplit = -1)
        i = i+1
        if (cabeceras[0] == "Cookie: ") & cabeceras[1] != "1" & cabeceras[1] != str(MAX_ACCESOS):
            return cabeceras[1] + 1
        if (cabeceras[0] == "Cookie: ") & (cabeceras[1] == MAX_ACCESOS):
            return MAX_ACCESOS
        else:
            return 1


    


def process_web_request(cs, webroot):
        #Procesamiento principal de los mensajes recibidos.
        #Típicamente se seguirá un procedimiento similar al siguiente (aunque el alumno puede modificarlo si lo desea)
    while(True):
        # Bucle para esperar hasta que lleguen datos en la red a través del socket cs con select()
        # Se comprueba si hay que cerrar la conexión por exceder TIMEOUT_CONNECTION segundos
        #  sin recibir ningún mensaje o hay datos. Se utiliza select.select
        (rsublist, _, _) = select.select([cs], [], [cs], TIMEOUT_CONNECTION)
        if not rsublist: 
            break
        # Si no es por timeout y hay datos en el socket cs.
        # Leer los datos con recv.
        data  = recibir_mensaje(cs)
        print(data)
        
        # Analizar que la línea de solicitud y comprobar está bien formateada según HTTP 1.1
        lineas = data.split(sep = "\r\n", maxsplit = -1)
        lineas_solicitud = lineas[0].split(sep = ' ', maxsplit = -1)
        
        # Devuelve una lista con los atributos de las cabeceras.
        for linea in lineas:
            comp = re.compile(atributos).fullmatch(str(lineas))
            if comp:
                diccionario = {comp.group('clave'): comp.group('valor')}

        # Comprobar si la versión de HTTP es 1.1
        if(lineas_solicitud[2] != "HTTP/1.1"):
            print("La versidon HTTP no es la 1.1")

        # Comprobar si es un método GET. Si no devolver un error Error 405 "Method Not Allowed".
        if(lineas_solicitud[0] != "GET"):
            ruta = "./405.html"
            terminacion = lineas_solicitud[1].split(sep = '.', maxsplit = -1)
            if(terminacion[0] == "/"):
                terminacion = "html"
            else:
                terminacion = terminacion[1]
            content = " "
            for clave in filetypes:
                if(clave == terminacion):
                    content = filetypes[clave]
            header = "HTTP/1.1 405 Method Not Allowed\r\n" + "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT\r\n')) + "Server: iotforyou03.org\r\n" + "Content-Length: " + str(os.stat("./405.html").st_size) + "\r\n" + "Connection: Connection Close\r\n" + "Content-Type: " + content + "\r\n\r\n" 
            tam5 = os.stat("./405.html").st_size
            enviar_recurso(ruta, header, tam5, cs)
            cerrar_conexion(cs)
        # Leer URL y eliminar parámetros si los hubiera
        #TODO
        # Comprobar si el recurso solicitado es /, En ese caso el recurso es index.html
        recurso = " "
        if(lineas_solicitud[1] == "/"):
            recurso = "/index.html"
        else:
            recurso = lineas_solicitud[1]

        # Construir la ruta absoluta del recurso (webroot + recurso solicitado)
        ruta = webroot + recurso

        print("Ruta: " + ruta)
        # Comprobar que el recurso (fichero) existe, si no devolver Error 404 "Not found"
        if not (os.path.isfile(ruta)):
            ruta = "./404.html"
            terminacion = lineas_solicitud[1].split(sep = '.', maxsplit = -1)
            if(terminacion[0] == "/"):
                terminacion = "html"
            else:
                terminacion = terminacion[1]
            content = " "
            for clave in filetypes:
                if(clave == terminacion):
                    content = filetypes[clave]
            header = "HTTP/1.1 404 Method Not Allowed\r\n" + "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT\r\n')) + "Server: iotforyou03.org\r\n" + "Content-Length: " + str(os.stat("./404.html").st_size) + "\r\n" + "Connection: Connection Close\r\n" + "Content-Type: " + content +"\r\n\r\n" 
            tam4 = os.stat("./404.html").st_size
            enviar_recurso(ruta, header, tam4, cs)
        # Analizar las cabeceras. Imprimir cada cabecera y su valor. Si la cabecera es Cookie comprobar
          #el valor de cookie_counter para ver si ha llegado a MAX_ACCESOS.
          #Si se ha llegado a MAX_ACCESOS devolver un Error "403 Forbidden"
        # Obtener el tamaño del recurso en bytes.            
        # Extraer extensión para obtener el tipo de archivo. Necesario para la cabecera Content-Type       
        # Preparar respuesta con código 200. Construir una respuesta que incluya: la línea de respuesta y
          #las cabeceras Date, Server, Connection, Set-Cookie (para la cookie cookie_counter),
          #Content-Length y Content-Type.
        #TODO Cookie counter
        """cookie_counter = process_cookies(data, cs)
        if cookie_counter == MAX_ACCESOS:
            ruta = "./403.html"
            terminacion = lineas_solicitud[1].split(sep = '.', maxsplit = -1)
            if(terminacion[0] == "/"):
                terminacion = "html"
            else:
                terminacion = terminacion[1]
            content = " "
            for clave in filetypes:
                if(clave == terminacion):
                    content = filetypes[clave]
            header = "HTTP/1.1 403 Forbidden\r\n" + "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT\r\n')) + "Server: iotforyou03.org\r\n" + "Content-Length: " + str(os.stat("./405.html").st_size) + "\r\n" + "Connection: Connection Close\r\n" + "Content-Type: " + content + "\r\n\r\n" 
            tam5 = os.stat("./405.html").st_size
            enviar_recurso(ruta, header, tam5, cs)
        else :
            respuesta = "Set-Cookie: cookie_counter: " + str(cookie_counter) + "\r\n" """
        



        datos_cabecera = "HTTP/1.1 200 OK\r\n" + "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT\r\n')) + "Server: iotforyou03.org\r\n"                 
        content_length = "Content-Length: " + str(os.stat(ruta).st_size) + "\r\n"
        datos_cabecera = datos_cabecera + content_length
        datos_cabecera = datos_cabecera + "Keep-Alive: timeout=" + str(40) + ", max=" + str(40) + "\r\n"
        datos_cabecera = datos_cabecera + "Connection: Keep-Alive\r\n"

        terminacion = lineas_solicitud[1].split(sep = '.', maxsplit = -1)
        if(terminacion[0] == "/"):
            terminacion = "html"
        else:
            terminacion = terminacion[1]
        content = " "
        for clave in filetypes:
            if(clave == terminacion):
                content = filetypes[clave]
        datos_cabecera = datos_cabecera + "Content-Type: " + content + "\r\n" + "\r\n"
        print(datos_cabecera)
        # Leer y enviar el contenido del fichero a retornar en el cuerpo de la respuesta.
        # Se abre el fichero en modo lectura y modo binario
            # Se lee el fichero en bloques de BUFSIZE bytes (8KB)
            # Cuando ya no hay más información para leer, se corta el bucle
            # Si es por timeout, se cierra el socket tras el período de persistencia.
                # NOTA: Si hay algún error, enviar una respuesta de error con una pequeña página HTML que informe del error.
        tam = os.stat(ruta).st_size
        print("Tamano del archivo: " + str(tam))
        enviar_recurso(ruta, datos_cabecera, tam, cs)
    cerrar_conexion(cs)
    sys.exit()


def main():
    """ Función principal del servidor
    """

    try:

        # Argument parser para obtener la ip y puerto de los parámetros de ejecución del programa. IP por defecto 0.0.0.0
        parser = argparse.ArgumentParser()
        parser.add_argument("-p", "--port", help="Puerto del servidor", type=int, required=True)
        parser.add_argument("-ip", "--host", help="Dirección IP del servidor o localhost", required=True)
        parser.add_argument("-wb", "--webroot", help="Directorio base desde donde se sirven los ficheros (p.ej. /home/user/mi_web)")
        parser.add_argument('--verbose', '-v', action='store_true', help='Incluir mensajes de depuración en la salida')
        args = parser.parse_args()


        if args.verbose:
            logger.setLevel(logging.DEBUG)

        logger.info('Enabling server in address {} and port {}.'.format(args.host, args.port))

        logger.info("Serving files from {}".format(args.webroot))

        """ Funcionalidad a realizar
        * Crea un socket TCP (SOCK_STREAM)
        * Permite reusar la misma dirección previamente vinculada a otro proceso. Debe ir antes de sock.bind
        * Vinculamos el socket a una IP y puerto elegidos
        * Escucha conexiones entrantes
        * Bucle infinito para mantener el servidor activo indefinidamente
            - Aceptamos la conexión
            - Creamos un proceso hijo
            - Si es el proceso hijo se cierra el socket del padre y procesar la petición con process_web_request()
            - Si es el proceso padre cerrar el socket que gestiona el hijo.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((args.host, args.port))
        sock.listen()
        while(True):
            #try:
            socket_cliente, addr_cliente = sock.accept()
            hijo = os.fork()
            if(hijo == 0):
                cerrar_conexion(sock)
                process_web_request(socket_cliente, args.webroot)
            else:
                cerrar_conexion(socket_cliente)
            #except socket.error:
                #break
    except KeyboardInterrupt:
        True
        
if __name__== "__main__":
    main()