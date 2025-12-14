"""
Módulo de configuración interactiva para la herramienta de migración de WordPress.

Este módulo se encarga de recopilar de forma interactiva toda la información
necesaria para establecer las conexiones SSH con los servidores de origen y
destino. Proporciona utilidades para mostrar banners y secciones, solicitar
entradas al usuario con valores predeterminados, validar datos básicos y
confirmar la configuración antes de iniciar el proceso de migración.

Los valores predeterminados pueden cargarse desde variables de entorno mediante
dotenv, lo que permite automatizar parcialmente la configuración o
integrar la herramienta en flujos no completamente interactivos.

Funciones:
    print_banner: Muestra el banner inicial de la aplicación.
    print_section: Muestra un encabezado de sección en consola.
    get_input: Solicita una entrada al usuario con valor predeterminado opcional.
    get_yes_no: Solicita una confirmación de sí/no al usuario.
    validate_ip_or_hostname: Valida el formato de una dirección IP o nombre de host.
    validate_port: Valida un número de puerto.
    validate_file_path: Verifica la existencia de un archivo en el sistema.
    get_server_config: Recopila la configuración SSH de un servidor.
    display_configuration_summary: Muestra un resumen de la configuración recopilada.
    collect_server_configurations: Ejecuta el flujo completo de configuración interactiva.

Ejemplo:
    from config import collect_server_configurations
    
    source_config, dest_config = collect_server_configurations()
"""

import sys
import os
import getpass
from dotenv import load_dotenv
load_dotenv()


def print_banner():
    """Imprimir banner de la aplicación"""
    print("\n" + "=" * 60)
    print("    WPMIG: Migrador de WordPress - Configuración inicial")
    print("=" * 60 + "\n")


def print_section(title: str):
    """Imprimir encabezado"""
    print(f"\n{'─' * 60}")
    print(f"    {title}")
    print('─' * 60)


def get_input(prompt: str, default: str = None) -> str:
    """
    Obtiene una entrada del usuario con un valor predeterminado opcional.

    Args:
        prompt: Mensaje que se mostrará al usuario.
        default: Valor predeterminado si el usuario presiona Enter.

    Returns:
        La entrada proporcionada por el usuario o el valor predeterminado.
    """
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        user_input = input(f"{prompt}: ").strip()
        while not user_input:
            print(":!: Este campo no puede quedar vacío. Por favor intente de nuevo.")
            user_input = input(f"{prompt}: ").strip()
        return user_input


def get_yes_no(prompt: str, default: bool = True) -> bool:
    """
    Obtiene una confirmación de sí/no por parte del usuario.

    Args:
        prompt: Pregunta que se mostrará al usuario.
        default: Valor predeterminado (True para sí, False para no).

    Returns:
        Respuesta booleana.
    """
    if default:
        default_str = "S/n"
    else:
        default_str = "s/N"

    response = input(f"{prompt} [{default_str}]: ").strip().lower()
    
    if not response:
        return default
    
    return response in ['y', 'yes', 's', 'si', 'sí']


def validate_ip_or_hostname(value: str) -> bool:
    """
    Realiza una validación básica de una dirección IP o un nombre de host.

    Args:
        value: Cadena que representa la dirección IP o el nombre de host.

    Returns:
        True si el formato es válido.
    """
    # Validación básica - no vacío y de longitud razonable
    if not value or len(value) < 1 or len(value) > 253:
        return False
    
    # Validar si parece un a IP o hostname
    parts = value.split('.')
    
    # Si no es una dirección IP (4 partes, todas numéricas)
    if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
        return True
    
    # Si es un hostname (contiene caracteres alfanuméricos y puntos/guiones)
    if all(c.isalnum() or c in '.-' for c in value):
        return True
    
    return False


def validate_port(port_str: str) -> bool:
    """
    Valida un número de puerto.

    Args:
        port_str: Número de puerto como cadena.

    Returns:
        True si el puerto es válido (1–65535).
    """
    try:
        port = int(port_str)
        return 1 <= port <= 65535
    except ValueError:
        return False


def validate_file_path(path: str) -> bool:
    """
    Verifica si un archivo existe.

    Args:
        path: Ruta del archivo.

    Returns:
        True si el archivo existe.
    """
    return os.path.isfile(path)


def get_server_config(server_name: str) -> dict:
    """
    Obtiene los parámetros de conexión SSH para un servidor (Origen o Destino),
    admitiendo valores predeterminados opcionales cargados desde variables de 
    entorno mediante python-dotenv.

    Las variables de entorno (por ejemplo, SOURCE_HOST, DESTINATION_USER, etc.)
    se utilizan como valores predeterminados cuando están disponibles. Cuando no lo están,
    la función solicita los datos al usuario de forma interactiva.

    Args:
        server_name: Nombre del servidor ("Origen" o "Destino").

    Returns:
        Diccionario con la configuración de conexión del servidor.
    """
    print_section(f"{server_name}: Configuración del Servidor")

    config = {}

    # Normaliza nombre del servidor para búsqueda en .env
    SERVER_NAME_MAP = {
        "origen": "SOURCE",
        "destino": "DESTINATION",
        "source": "SOURCE",
        "destination": "DESTINATION"
    }

    normalized_name = server_name.strip().lower()
    env_prefix = SERVER_NAME_MAP.get(normalized_name, server_name.upper())

    # Hostname / IP
    default_host = os.getenv(f"{env_prefix}_HOST")

    while True:
        host = get_input(
            f"{server_name} — Hostname o dirección IP",
            default=default_host
        )
        if validate_ip_or_hostname(host):
            config['host'] = host
            break
        else:
            print(":!: Hostname o dirección IP inválida. Por favor intente de nuevo.")

    # Puerto SSH
    default_port = os.getenv(f"{env_prefix}_PORT", "22")

    while True:
        port = get_input("Puerto SSH", default=default_port)
        if validate_port(port):
            config['port'] = int(port)
            break
        else:
            print(":!: Número de puerto inávlido (debe ser 1-65535).")

    # Nombre de usuario
    default_user = os.getenv(f"{env_prefix}_USER")
    config['username'] = get_input("Usuario SSH", default=default_user)

    # Método de autenticación
    print(f"\n{server_name} — Método de autenticación:")
    print("  1) Llave SSH (recomendado)")
    print("  2) Contraseña")

    default_auth = os.getenv(f"{env_prefix}_AUTH_METHOD", "1")
    auth_choice = get_input("Seleccione el método de autenticación [1/2]", default=default_auth)

    # Autenticación SSH por llave
    if auth_choice == "1":
        default_key = os.getenv(f"{env_prefix}_KEY_PATH")

        while True:
            key_path = get_input("Ruta de la llave SSH privada", default=default_key)
            key_path = os.path.expanduser(key_path)

            if validate_file_path(key_path):
                config['key_path'] = key_path
                print(f":✓: LLave SSH encontrada: {key_path}")
                break
            else:
                print(f":!: Archivo no encontrado: {key_path}")
                retry = get_yes_no("Intentar otra ruta?", default=True)
                if not retry:
                    print(":!: Cambiando a autenticación por contraseña...")
                    break

        # Si la llave falla y el usuario cambia a contraseña
        if 'key_path' not in config:
            env_password = os.getenv(f"{env_prefix}_PASSWORD")
            if env_password:
                config['password'] = env_password
            else:
                config['password'] = getpass.getpass(f"{server_name} contraseña SSH del servidor: ")

    # Autenticación SSH por contraseña
    else:
        env_password = os.getenv(f"{env_prefix}_PASSWORD")
        if env_password:
            config['password'] = env_password
        else:
            config['password'] = getpass.getpass(f"{server_name} contraseña SSH del servidor: ")

    return config


def display_configuration_summary(source_config: dict, dest_config: dict):
    """
    Muestra un resumen de la configuración recopilada.

    Args:
        source_config: Configuración del servidor de origen.
        dest_config: Configuración del servidor de destino.
    """
    print_section("Resumen de la configuración")
    
    # Servidor origen
    print("\n Servidor Origen:")
    print(f"   Host:     {source_config['host']}")
    print(f"   Puerto:   {source_config['port']}")
    print(f"   Usuario:  {source_config['username']}")
    if 'key_path' in source_config:
        print(f"   Auth:     Llave SSH ({source_config['key_path']})")
    else:
        print(f"   Auth:     Contraseña")
    
    # Servidor destino
    print("\n Servidor Destino:")
    print(f"   Host:     {dest_config['host']}")
    print(f"   Puerto:   {dest_config['port']}")
    print(f"   Usuario:  {dest_config['username']}")
    if 'key_path' in dest_config:
        print(f"   Auth:     Llave SSH ({dest_config['key_path']})")
    else:
        print(f"   Auth:     Contraseña")
    
    print()


def collect_server_configurations() -> tuple:
    """
    Función principal para recopilar de forma interactiva todas las configuraciones
    de los servidores.

    Returns:
        Una tupla con los diccionarios (source_config, dest_config).
    """
    print_banner()
    
    print("Esta herramienta le ayudará a migrar un sitio WordPress desde")
    print("un servidor a otro. Primero, configure la conexión SSH.\n")
    
    # Configuración servidor origen
    source_config = get_server_config("Origen")
    
    # Configuración servidor destino
    dest_config = get_server_config("Destino")
    
    # Mostra resumen
    display_configuration_summary(source_config, dest_config)
    
    # Confirma antes de proceder
    if not get_yes_no("\nProceder con estas opciones?", default=True):
        print("\n:x: Configuración cancelada por el usuario.")
        sys.exit(0)
    
    print("\n✓ Configuración completada!\n")
    
    return source_config, dest_config
